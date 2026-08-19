"""check_bowl_uv: 检查v42b新blend的碗面avg_uv实际值+采样颜色"""
import bpy, bmesh, os, sys, json, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH' and 'tripo' in o.name][0]

tex_img = None
for mat in obj.data.materials:
    if mat and mat.use_nodes:
        for n in mat.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                tex_img = n.image
W, H = tex_img.size
px = tex_img.pixels[:]
def sample(u, v):
    x = min(max(int(u*W), 0), W-1); y = min(max(int(v*H), 0), H-1)
    i = (y*W + x)*4
    return (px[i], px[i+1], px[i+2])

with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

bm = bmesh.new(); bm.from_mesh(obj.data)
uv_layer = bm.loops.layers.uv.active

# 碗面: dxz<15mm的深区面
for side, center in [("L", cL), ("R", cR)]:
    bowl_uvs = []
    for f in bm.faces:
        fc = f.calc_center_median()
        dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2)
        if dxz < 0.015 and center.y - 0.001 < fc.y < center.y + 0.02:
            for l in f.loops:
                bowl_uvs.append(l[uv_layer].uv.copy())
    if bowl_uvs:
        au = sum(u.x for u in bowl_uvs)/len(bowl_uvs)
        av = sum(u.y for u in bowl_uvs)/len(bowl_uvs)
        c = sample(au, av)
        print(f"{side} 碗面: {len(bowl_uvs)}loops avg_uv=({au:.4f},{av:.4f}) RGB=({c[0]:.2f},{c[1]:.2f},{c[2]:.2f}) 亮度={sum(c)/3:.2f}")
bm.free()
print("完成")
