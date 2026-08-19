"""精确测量 rim 环顶点位置(从管线日志反推)
rim 半径 avg=8.3mm 是错的, 实际应该在 6-14mm(3DDFA眼裂范围)
"""
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
bm.verts.ensure_lookup_table()

# 找 rim 顶点: 眼窝区最浅(y≈center.y)且半径在 5-15mm 的顶点
for side, center in [("L", cL), ("R", cR)]:
    rim_verts = []
    for v in bm.verts:
        dxz = math.sqrt((v.co.x-center.x)**2 + (v.co.z-center.z)**2)
        depth = abs(v.co.y - center.y)
        if 0.005 < dxz < 0.016 and depth < 0.001:  # 5-16mm, 深度±1mm
            ang = math.degrees(math.atan2(v.co.z-center.z, v.co.x-center.x))
            rim_verts.append((ang, dxz*1000))
    rim_verts.sort()
    print(f"\n{side}: rim顶点数={len(rim_verts)}")
    # 每30度统计
    for deg in range(-180, 180, 30):
        lo, hi = deg-15, deg+15
        rs = [r for a, r in rim_verts if lo <= a < hi]
        if rs:
            print(f"  {deg:>4}°: {min(rs):.1f}~{max(rs):.1f}mm avg={sum(rs)/len(rs):.1f}mm (n={len(rs)})")
    all_r = [r for _, r in rim_verts]
    print(f"  总范围: {min(all_r):.1f}~{max(all_r):.1f}mm avg={sum(all_r)/len(all_r):.1f}mm")
bm.free()
print("\n诊断完成")
