"""定量测眼球前后位置: 角膜前极 vs 眶缘(眉弓/颧骨最前点)
规则: 几何位置用世界坐标定量, 不盲信vision
若角膜前极y < 眶缘y(更靠前=更负), 则眼球突出超过眶缘
"""
import bpy, bmesh, os, sys, json, math
import numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH' and 'tripo' in o.name][0]
eyeL = [o for o in bpy.data.objects if 'Eye_R' in o.name][0]
eyeR = [o for o in bpy.data.objects if 'Eye_L' in o.name][0]

with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

bm = bmesh.new(); bm.from_mesh(obj.data)
V = np.array([v.co for v in bm.verts])

for side, center, eye_obj in [("L", cL, eyeL), ("R", cR, eyeR)]:
    eye_center = Vector(eye_obj.matrix_world.translation)
    cornea_front_y = eye_center.y - EYE_RADIUS  # 角膜前极(眼球最前点)
    
    # 眉弓区: 眼睛上方(z>center.z+3mm), 眼区x范围, 找最前点(min y)
    brow_mask = (V[:,2] > center.z + 0.003) & (V[:,2] < center.z + 0.012) & \
                (np.abs(V[:,0] - center.x) < 0.012) & (V[:,1] < -0.10)
    # 颧骨区: 眼睛下方(z<center.z-6mm), 找最前点
    cheek_mask = (V[:,2] < center.z - 0.006) & (V[:,2] > center.z - 0.020) & \
                 (np.abs(V[:,0] - center.x) < 0.015) & (V[:,1] < -0.10)
    
    brow_front_y = V[brow_mask, 1].min() if brow_mask.sum() > 0 else None
    cheek_front_y = V[cheek_mask, 1].min() if cheek_mask.sum() > 0 else None
    # 眼区皮肤最前点(眼眶整体最前)
    eye_zone_mask = (np.abs(V[:,0]-center.x) < 0.018) & (np.abs(V[:,2]-center.z) < 0.018) & (V[:,1] < -0.10)
    eye_zone_front_y = V[eye_zone_mask, 1].min() if eye_zone_mask.sum() > 0 else None
    
    print(f"\n=== {side}眼 前后位置定量(y越小=越靠前) ===")
    print(f"  角膜前极 y = {cornea_front_y:.4f}")
    print(f"  眼球球心 y = {eye_center.y:.4f}")
    if brow_front_y is not None:
        print(f"  眉弓最前点 y = {brow_front_y:.4f} ({brow_mask.sum()}点)")
        print(f"    角膜 vs 眉弓: 角膜{'更靠前' if cornea_front_y < brow_front_y else '在眉弓后'} {abs(cornea_front_y-brow_front_y)*1000:.1f}mm")
    if cheek_front_y is not None:
        print(f"  颧骨最前点 y = {cheek_front_y:.4f} ({cheek_mask.sum()}点)")
        print(f"    角膜 vs 颧骨: 角膜{'更靠前' if cornea_front_y < cheek_front_y else '在颧骨后'} {abs(cornea_front_y-cheek_front_y)*1000:.1f}mm")
    if eye_zone_front_y is not None:
        print(f"  眼区皮肤最前点 y = {eye_zone_front_y:.4f} ({eye_zone_mask.sum()}点)")
        print(f"    角膜 vs 眼区皮肤: 角膜{'更靠前' if cornea_front_y < eye_zone_front_y else '在皮肤后'} {abs(cornea_front_y-eye_zone_front_y)*1000:.1f}mm")
bm.free()
print("\n定量完成")
