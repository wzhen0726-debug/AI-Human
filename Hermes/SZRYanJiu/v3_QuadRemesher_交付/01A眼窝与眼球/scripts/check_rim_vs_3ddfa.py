"""对比 rim 实际位置 vs 3DDFA 眼裂轮廓"""
import bpy, os, sys, json, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

import bmesh
bm = bmesh.new(); bm.from_mesh(obj.data)

# 找眼窝区最浅的一圈顶点(y≈center.y)
for side, center in [("L", cL), ("R", cR)]:
    rim_verts = []
    for v in bm.verts:
        dxz = math.sqrt((v.co.x-center.x)**2 + (v.co.z-center.z)**2)
        depth = abs(v.co.y - center.y)
        if 0.003 < dxz < 0.018 and depth < 0.0005:  # 3-18mm, 深度±0.5mm
            ang = math.degrees(math.atan2(v.co.z-center.z, v.co.x-center.x))
            rim_verts.append((ang, dxz*1000, v.co.copy()))
    rim_verts.sort()
    print(f"\n{side}: rim顶点数={len(rim_verts)}")
    
    # 3DDFA 轮廓
    with open(EYELID_CONTOUR_JSON, encoding="utf-8") as f:
        dd = json.load(f)
    rim_3ddfa = [r for r in dd[side]["rim_3d"] if r is not None]
    c = dd[side]["center"]
    
    # 对比每个rim顶点到3DDFA轮廓的距离
    dists = []
    for ang, rad, co in rim_verts:
        best = min((co - Vector((r[0], r[1], r[2]))).length for r in rim_3ddfa)
        dists.append((ang, rad, best*1000))
    
    # 找出偏差最大的区域
    print(f"  rim→3DDFA距离: min={min(d[2] for d in dists):.1f} max={max(d[2] for d in dists):.1f} avg={sum(d[2] for d in dists)/len(dists):.1f}mm")
    
    # 按角度统计偏差
    print(f"  按角度统计:")
    for deg in range(-180, 180, 60):
        lo, hi = deg-30, deg+30
        ds = [item for item in dists if lo <= item[0] < hi]
        if ds:
            rads = [item[1] for item in ds]; devs = [item[2] for item in ds]
            print(f"    {deg:>4}°: rim半径{min(rads):.1f}~{max(rads):.1f}mm, 偏差{min(devs):.1f}~{max(devs):.1f}mm (n={len(ds)})")
bm.free()
print("\n诊断完成")
