# -*- coding: utf-8 -*-"""
Mesh-space residual texture-artifact scan (for the baked-diffuse color-bleed class).

WHY mesh space: UV islands are scattered, so the texels behind a 3D smudge are
usually NOT near the garment in the image; and a 3D region bounding box mixes
skin + garment faces, so its raw luminance percentiles prove nothing. Sampling
the texture THROUGH the mesh (per-face UV centroid) and clustering over face
adjacency gives exactly what the user sees in the viewport.

USAGE:
  blender -b <model.blend> --python mesh_space_texture_residue_scan.py -- <png> [--dark 80] [--skin 105]

Prints: global sampled-luminance percentiles, then dark clusters whose face
neighborhood is skin-dominant (small clusters = residual bleed candidates;
large clusters = the garment itself). Expect only a few tiny residues after a
correct fix. Pure-Python adjacency loops: ~1-2 min on 300K-face meshes.
"""
import bpy
import sys
import numpy as np
from collections import defaultdict, deque
from PIL import Image

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
png = argv[0] if argv else None
assert png, "usage: blender -b <blend> --python this.py -- <png> [--dark N] [--skin N]"
dark_th = float(argv[argv.index("--dark") + 1]) if "--dark" in argv else 80.0
skin_th = float(argv[argv.index("--skin") + 1]) if "--skin" in argv else 105.0

objs = [o for o in bpy.data.objects if o.type == "MESH"]
low = max(objs, key=lambda o: len(o.data.polygons))  # body = most polygons
me = low.data
N = len(me.polygons)
uvl = me.uv_layers.active
assert uvl is not None, "mesh has no active UV layer"

luv = np.empty(len(me.loops) * 2, np.float32)
uvl.data.foreach_get("uv", luv)
luv = luv.reshape(-1, 2)
lstart = np.empty(N, np.int32)
ltot = np.empty(N, np.int32)
me.polygons.foreach_get("loop_start", lstart)
me.polygons.foreach_get("loop_total", ltot)

img = np.asarray(Image.open(png).convert("RGB"), dtype=np.int16)
H, W = img.shape[:2]
uvc = np.empty((N, 2), np.float64)
for i in range(N):
    uvc[i] = luv[lstart[i]:lstart[i] + ltot[i]].mean(axis=0)
xi = np.clip((uvc[:, 0] * W).astype(int), 0, W - 1)
yi = np.clip(((1.0 - uvc[:, 1]) * H).astype(int), 0, H - 1)
col = img[yi, xi]
lum = 0.30 * col[:, 0] + 0.59 * col[:, 1] + 0.11 * col[:, 2]
empty = (col[:, 0] <= 2) & (col[:, 1] <= 2) & (col[:, 2] <= 2)
print("sampled lum: median=%.0f p10=%.0f p90=%.0f (non-empty faces=%d)"
      % (np.median(lum[~empty]), np.percentile(lum[~empty], 10),
         np.percentile(lum[~empty], 90), int((~empty).sum())), flush=True)

M = np.array(low.matrix_world)
fc = np.empty(N * 3, np.float64)
me.polygons.foreach_get("center", fc)
fc = fc.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]

vert2face = defaultdict(list)
for i, p in enumerate(me.polygons):
    for v in p.vertices:
        vert2face[v].append(i)
nbr = defaultdict(set)
for fs in vert2face.values():
    if len(fs) > 1:
        for a in fs:
            s = nbr[a]
            s.update(fs)
            s.discard(a)

dark_f = (lum < dark_th) & (~empty)
skin_f = (lum > skin_th) & (~empty)
seen = np.zeros(N, bool)
hits = []
for i in range(N):
    if not dark_f[i] or seen[i]:
        continue
    comp, q = [], deque([i])
    seen[i] = True
    while q:
        j = q.popleft()
        comp.append(j)
        for k in nbr[j]:
            if dark_f[k] and not seen[k]:
                seen[k] = True
                q.append(k)
    if not (3 <= len(comp) <= 400):
        continue
    ring = set()
    for j in comp[:30]:
        ring.update(nbr[j])
    ring -= set(comp)
    if not ring:
        continue
    fr = float(skin_f[list(ring)].mean())
    if fr > 0.6:
        hits.append((len(comp), fr, fc[comp].mean(axis=0), uvc[comp].mean(axis=0)))
hits.sort(key=lambda h: -h[0])
print("skin-surrounded dark clusters (residual bleed candidates): %d" % len(hits), flush=True)
for n_, fr, c, uv in hits[:15]:
    print("  faces=%d skin-neighborhood=%.2f 3D=(%.0f,%.0f,%.0f)mm UV=(%.3f,%.3f)"
          % (n_, fr, c[0] * 1000, c[1] * 1000, c[2] * 1000, uv[0], uv[1]), flush=True)
print("RESIDUE_SCAN_DONE", flush=True)
