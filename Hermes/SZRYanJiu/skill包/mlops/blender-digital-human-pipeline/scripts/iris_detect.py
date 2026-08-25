"""Auto-localize iris centers on a textured head mesh via texture dark-pixel clustering.
Edit BLEND_PATH below. Requires head upright (feet down), face toward -Y, meters scale.
Tune the eye-band mask (z range, |x|, y) per model; defaults fit a ~1.8m standing human.
Run: blender --background --factory-startup --python iris_detect.py
Output: LEFT/RIGHT iris ~ center=(x,y,z) lines.
"""
import bpy
import numpy as np

BLEND_PATH = r"E:\...\01_highpoly_repair.blend"  # EDIT ME

bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
mesh = obj.data

# vertex coords (fast foreach_get — never Python-loop over verts)
nv = len(mesh.vertices)
V = np.empty(nv * 3, dtype=np.float32)
mesh.vertices.foreach_get("co", V)
V = V.reshape(nv, 3)
zmax = V[:, 2].max()

# loop data vectorized
uv = mesh.uv_layers.active.data
nloop = len(mesh.loops)
loop_vid = np.empty(nloop, dtype=np.int64)
loop_uv = np.empty(nloop * 2, dtype=np.float32)
mesh.loops.foreach_get("vertex_index", loop_vid)
uv.foreach_get("uv", loop_uv)
loop_uv = loop_uv.reshape(nloop, 2)

# eye-band vertex mask (tune per model): head-top front strip
vband_mask = (
    (V[:, 2] > zmax - 0.20) & (V[:, 2] < zmax - 0.125)
    & (np.abs(V[:, 0]) < 0.06) & (V[:, 1] < -0.08)
)
# aggregate UV only for band loops (avoid full-mesh aggregation)
band_loops = vband_mask[loop_vid]
bvid = loop_vid[band_loops]
buv = loop_uv[band_loops]
uvsum = np.zeros((nv, 2), dtype=np.float64)
uvcnt = np.zeros(nv, dtype=np.int64)
np.add.at(uvsum, bvid, buv)
np.add.at(uvcnt, bvid, 1)
Ib = np.where(vband_mask & (uvcnt > 0))[0]
UVb = uvsum[Ib] / uvcnt[Ib, None]

# texture pixels via foreach_get (img.pixels[:] times out on 8K textures)
img = None
for m in mesh.materials:
    if m and m.node_tree:
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                img = n.image
                break
W, H = img.size
buf = np.empty(W * H * 4, dtype=np.float32)
img.pixels.foreach_get(buf)
px = buf.reshape(H, W, 4)
print(f"tex {W}x{H}")

# sample brightness, dark threshold, split by x sign
xx = (UVb[:, 0] * (W - 1)).clip(0, W - 1).astype(int)
yy = (UVb[:, 1] * (H - 1)).clip(0, H - 1).astype(int)
bright = px[yy, xx, :3].mean(axis=1)
print(f"band verts {len(Ib)} bright mean {bright.mean():.3f}")
dark = Ib[bright < np.percentile(bright, 12)]
Vd = V[dark]
for name, msk in [("LEFT", Vd[:, 0] < 0), ("RIGHT", Vd[:, 0] > 0)]:
    P = Vd[msk]
    if len(P) > 30:
        c = P.mean(axis=0)
        print(f"{name} iris ~ center=({c[0]:.4f},{c[1]:.4f},{c[2]:.4f}) n={len(P)}")
    else:
        print(f"{name} iris ~ too few dark verts ({len(P)}) — widen band or lower threshold")
