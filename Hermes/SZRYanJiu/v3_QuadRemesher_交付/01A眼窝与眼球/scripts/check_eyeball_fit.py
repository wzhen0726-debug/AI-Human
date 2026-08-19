"""验证眼球摆入几何: 眼球球心 vs 眼窝唇缘/碗面位置关系
检查: 1) 眼球是否被眼睑包裹(球心在唇缘后, 角膜前极在唇缘前)
      2) 左右眼对称性
      3) 球心 x/z 是否与眼窝中心对齐
"""
import bpy, os, sys, json, math
import numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
objs = [o for o in bpy.data.objects if o.type == 'MESH']
print(f"网格对象: {[o.name for o in objs]}")

head = [o for o in objs if 'tripo' in o.name][0]
eyeL = [o for o in objs if 'Eye_R' in o.name][0]
eyeR = [o for o in objs if 'Eye_L' in o.name][0]

# 眼球球心(对象原点=球心, 因为glb以球心为原点)
cL = Vector(eyeL.matrix_world.translation)
cR = Vector(eyeR.matrix_world.translation)
print(f"\n眼球球心: L=({cL.x:.4f},{cL.y:.4f},{cL.z:.4f}) R=({cR.x:.4f},{cR.y:.4f},{cR.z:.4f})")
print(f"眼间距: {(cL-cR).length*1000:.1f}mm (3DDFA 71.7mm)")

# 读3DDFA数据(角膜点/拟合球心)
with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
for side, c in [("L", cL), ("R", cR)]:
    fit = d[side]["fitted_sphere"]["center"]
    r = d[side]["fitted_sphere"]["radius"]
    c3 = d[side]["center_3d"]
    print(f"\n{side}眼:")
    print(f"  拟合虚拟眼球: 球心=({fit[0]:.4f},{fit[1]:.4f},{fit[2]:.4f}) r={r*1000:.1f}mm")
    print(f"  3DDFA角膜点: ({c3[0]:.4f},{c3[1]:.4f},{c3[2]:.4f})")
    print(f"  摆入球心 vs 拟合球心 偏差: {(c-Vector(fit)).length*1000:.2f}mm")
    print(f"  角膜前极(y): 摆入={c.y-EYE_RADIUS:.4f} vs 拟合={fit[1]-r:.4f} 差={abs((c.y-EYE_RADIUS)-(fit[1]-r))*1000:.1f}mm")

# 眼窝唇缘: 找碗面最深点(pole)反推唇缘y (与run_eyeball一致)
import bmesh
bm = bmesh.new(); bm.from_mesh(head.data)
bm.verts.ensure_lookup_table()
V = np.array([v.co for v in bm.verts])
for side, center, eye_c in [("L", Vector(d["L"]["center_3d"]), cL), ("R", Vector(d["R"]["center_3d"]), cR)]:
    # 眼窝区顶点(加y深度限制, 排除后脑壳)
    dxz = np.sqrt((V[:,0]-center.x)**2 + (V[:,2]-center.z)**2)
    y_ok = (V[:,1] > -0.15) & (V[:,1] < -0.05)  # 眼窝深度范围
    sel = (dxz < 0.016) & y_ok
    if sel.sum() == 0:
        print(f"\n{side}: 眼窝区无顶点"); continue
    # 碗底极点(最深入头 = y最大)
    pole_y = V[sel, 1].max()
    rim_y = pole_y - 0.006  # CUP_DEPTH
    # 眼球球心 y 与唇缘 y 的关系
    print(f"\n{side}: 碗底pole_y={pole_y:.4f}, 唇缘rim_y≈{rim_y:.4f}")
    print(f"  眼球球心y={eye_c.y:.4f} vs 唇缘y={rim_y:.4f}: {'✅球心在唇缘后' if eye_c.y > rim_y else '⚠球心在唇缘前!'} (差{abs(eye_c.y-rim_y)*1000:.1f}mm)")
    print(f"  角膜前极y={eye_c.y-EYE_RADIUS:.4f} vs 唇缘y={rim_y:.4f}: {'✅角膜在唇缘前(凸出)' if eye_c.y-EYE_RADIUS < rim_y else '⚠角膜被眼睑完全包住'}")
bm.free()
print("\n验证完成")
