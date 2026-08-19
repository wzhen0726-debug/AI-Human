"""检查倒角带范围: rim(眼裂边缘) + 3mm倒角带 是否超出眼睑皮肤范围"""
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

# 找倒角带面片: 眼窝区最浅(y最接近center.y)的面
for side, center in [("L", cL), ("R", cR)]:
    chamfer_faces = []
    for f in bm.faces:
        fc = f.calc_center_median()
        dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2)
        depth = fc.y - center.y
        # 倒角带: y在center.y±3mm内, 半径在rim+3mm范围内
        if abs(depth) < 0.003 and 0.005 < dxz < 0.018:
            chamfer_faces.append((fc, dxz*1000))
    if chamfer_faces:
        radii = [r for _, r in chamfer_faces]
        print(f"{side}: 倒角带面片={len(chamfer_faces)}, 半径{min(radii):.1f}~{max(radii):.1f}mm avg={sum(radii)/len(radii):.1f}mm")
        # 按角度分布
        for deg in range(0, 360, 30):
            lo, hi = math.radians(deg-15), math.radians(deg+15)
            rs = []
            for fc, r in chamfer_faces:
                ang = math.atan2(fc.z-center.z, fc.x-center.x)
                if lo <= ang < hi:
                    rs.append(r)
            if rs:
                print(f"  {deg:3d}°: {min(rs):.1f}~{max(rs):.1f}mm (n={len(rs)})")
    else:
        print(f"{side}: 未找到倒角带面片")
bm.free()
print("\n诊断完成")
