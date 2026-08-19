"""对比眼窝区最浅面片 vs 3DDFA眼裂轮廓"""
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

# 找眼窝区最浅面片(y最接近center.y) = 皮肤与倒角带交界
for side, center in [("L", cL), ("R", cR)]:
    # 收集眼窝区面片
    faces = []
    for f in bm.faces:
        fc = f.calc_center_median()
        dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2)
        if dxz < 0.020:
            faces.append((fc, dxz*1000, (fc.y-center.y)*1000))
    # 按深度排序, 找最浅的10%
    faces.sort(key=lambda x: abs(x[2]))
    shallow = faces[:max(10, len(faces)//10)]
    print(f"\n{side}: 眼窝区总面片={len(faces)}, 最浅10%={len(shallow)}")
    for fc, r, d in shallow[:5]:
        print(f"  面: ({(fc.x-center.x)*1000:+.1f}, {(fc.z-center.z)*1000:+.1f})mm 半径={r:.1f}mm 深度={d:+.1f}mm")
    # 最浅面片的半径范围
    rs = [r for _, r, _ in shallow]
    print(f"  最浅10%半径范围: {min(rs):.1f}~{max(rs):.1f}mm avg={sum(rs)/len(rs):.1f}mm")

# 3DDFA 眼裂轮廓(原始6点)
print("\n=== 3DDFA 眼裂轮廓(原始) ===")
with open(EYELID_CONTOUR_JSON, encoding="utf-8") as f:
    d = json.load(f)
for side in ["L", "R"]:
    rim = [r for r in d[side]["rim_3d"] if r is not None]
    c = d[side]["center"]
    print(f"{side}: 中心=({c[0]:.4f},{c[1]:.4f},{c[2]:.4f})")
    for i, r in enumerate(rim):
        dx = (r[0]-c[0])*1000; dz = (r[2]-c[2])*1000
        rad = math.sqrt(dx*dx + dz*dz)
        print(f"  顶点{i}: ({dx:+.1f},{dz:+.1f})mm 半径={rad:.1f}mm")

bm.free()
print("\n诊断完成")
