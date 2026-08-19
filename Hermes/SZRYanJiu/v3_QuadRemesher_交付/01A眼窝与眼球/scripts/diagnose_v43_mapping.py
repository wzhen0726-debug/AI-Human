"""diagnose_v43_mapping: 量化眼窝区域UV采样颜色随dxz(距眼中心距离)的分布
目的: 定位v43贴图映射错位根因(rim/碗内/脸颊各采样到什么)
"""
import bpy, os, sys, math
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
    x = min(max(int(u*W),0),W-1); y = min(max(int(v*H),0),H-1)
    i = (y*W+x)*4
    return (px[i],px[i+1],px[i+2])

import json
with open(DDFA_JSON, encoding='utf-8') as f:
    d = json.load(f)

import bmesh
bm = bmesh.new(); bm.from_mesh(obj.data)
uv_layer = bm.loops.layers.uv.active

for side, key in [("L","L"), ("R","R")]:
    c = Vector(d[key]['center_3d'])
    buckets = {}
    for f in bm.faces:
        fc = f.calc_center_median()
        dx = fc.x - c.x; dz = fc.z - c.z
        dxz = math.sqrt(dx*dx+dz*dz)*1000
        if not (c.y - 0.005 < fc.y < c.y + 0.020):
            continue
        if dxz > 24:
            continue
        uvs = [l[uv_layer].uv for l in f.loops]
        au = sum(u.x for u in uvs)/len(uvs)
        av = sum(u.y for u in uvs)/len(uvs)
        rgb = sample(au, av)
        bucket = int(dxz // 2) * 2
        buckets.setdefault(bucket, []).append((au,av,rgb))
    print(f"\n=== {side}眼 UV采样颜色 vs dxz ===")
    print("  (rim半径avg~8.7mm, 倒角带3mm, 眼裂半宽13.4/半高4.85mm)")
    for b in sorted(buckets):
        items = buckets[b]
        au = sum(i[0] for i in items)/len(items)
        av = sum(i[1] for i in items)/len(items)
        r = sum(i[2][0] for i in items)/len(items)
        g = sum(i[2][1] for i in items)/len(items)
        bl = sum(i[2][2] for i in items)/len(items)
        print(f"  dxz {b:>2}-{b+2:>2}mm: n={len(items):>4} UV=({au:.3f},{av:.3f}) RGB=({r:.2f},{g:.2f},{bl:.2f}) 亮度={(r+g+bl)/3:.2f}")
bm.free()
print("\n诊断完成")
