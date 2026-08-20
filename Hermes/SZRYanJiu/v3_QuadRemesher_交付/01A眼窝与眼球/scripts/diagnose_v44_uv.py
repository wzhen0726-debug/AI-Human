"""diagnose_v44_uv.py - v44验证: 原始皮肤UV是否恢复变化(不再常数), 眼区亮度分桶
对比v43b基线: 15-21mm带 1139/1139面常数UV → v44应≈0
"""
import bpy, bmesh, os, sys, json, math
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

with open(DDFA_JSON, encoding="utf-8") as f:
    dd = json.load(f)
centers = {"L": Vector(dd["L"]["center_3d"]), "R": Vector(dd["R"]["center_3d"])}

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
me = obj.data
tex_img = None
for m in obj.data.materials:
    if m and m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                tex_img = n.image
px = np.array(tex_img.pixels[:], dtype=np.float32).reshape(tex_img.size[1], tex_img.size[0], 4)
TW, TH = tex_img.size

def sample_lum(u, v):
    xi = min(max(int(u*TW), 0), TW-1); yi = min(max(int(v*TH), 0), TH-1)
    return float(px[yi, xi, :3].mean())

for side in ("L", "R"):
    c = centers[side]
    bm = bmesh.new(); bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.active
    tag_l = bm.faces.layers.int.get("v44tag_" + side)

    def is_const_uv(f):
        uvs = [loop[uv_layer].uv for loop in f.loops]
        u0 = uvs[0]
        return all((u - u0).length < 0.002 for u in uvs[1:])

    # 1. 15-21mm带常数UV统计(v43b时1139/1139, v44应≈0)
    band_const = 0; band_total = 0
    # 2. 亮度分桶: dxz x 区域(上睑dz>0/下睑dz<0/眼角|dx|>10mm)
    buckets = {}
    for f in bm.faces:
        fc = f.calc_center_median()
        dx = fc.x - c.x; dz = fc.z - c.z
        dxz = math.hypot(dx, dz)
        if dxz > 0.025 or abs(fc.y - c.y) > 0.02: continue
        if 0.015 < dxz < 0.021:
            band_total += 1
            if is_const_uv(f): band_const += 1
        # 亮度取样(面loop UV均值)
        uvs = [loop[uv_layer].uv for loop in f.loops]
        u = sum(v.x for v in uvs)/len(uvs); v = sum(v.y for v in uvs)/len(uvs)
        if not (0.001 < u < 0.999 and 0.001 < v < 0.999): continue
        lum = sample_lum(u, v)
        if dz > 0.004: zone = "upper_lid"
        elif dz < -0.004: zone = "lower_lid"
        else: zone = "corner_band"
        b = int(dxz*1000/2)*2  # 2mm桶
        buckets.setdefault(zone, {}).setdefault(b, []).append(lum)
    print(f"=== {side} ===")
    print(f"15-21mm band: {band_const}/{band_total} constant-UV faces (v43b was 1139/1139)")
    tagged = sum(1 for f in bm.faces if tag_l and f[tag_l] > 0)
    print(f"tagged faces (bowl+chamfer): {tagged}")
    for zone in ("upper_lid", "lower_lid", "corner_band"):
        if zone not in buckets: continue
        row = []
        for b in sorted(buckets[zone]):
            ls = buckets[zone][b]
            row.append(f"{b}-{b+2}mm:{np.mean(ls):.2f}({len(ls)})")
        print(f"  {zone}: " + " ".join(row))
    bm.free()
print("V44 DIAG DONE")
