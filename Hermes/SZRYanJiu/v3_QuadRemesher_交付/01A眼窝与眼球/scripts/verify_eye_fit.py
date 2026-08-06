"""定量验证眼球装配: 球体与眼睑皮肤的穿透量 + 角膜前极相对开口平面的深度
判据:
1. 球面在开口椭圆内超出睑缘皮肤的量(应为负=在皮肤后, 眼睑才能盖住)
2. 角膜前极 y vs 唇缘 y (前极应在唇缘后0~2mm)
3. 球体在上下睑缘处相对皮肤的前凸量(正值=穿出皮肤=穿帮)
"""
import bpy, sys, os
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *
from eye_socket_config import HOLE_RX, HOLE_RZ
import json

d = json.load(open(DDFA_JSON, encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
# 头部 = 顶点最多的mesh (blend里还有2个眼球mesh, 不能取[0])
obj = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices))
print(f"head mesh: {obj.name}, verts={len(obj.data.vertices)}")
mesh = obj.data
nv = len(mesh.vertices)
V = np.empty(nv*3, dtype=np.float32)
mesh.vertices.foreach_get("co", V)
V = V.reshape(nv, 3).astype(np.float64)

R = EYE_RADIUS
for side, key in [("L","L"),("R","R")]:
    eye = next(o for o in bpy.data.objects if o.type=='MESH' and 'Eye' in o.name
               and (o.location.x < 0) == (side == "L"))
    c = np.array(eye.location[:], dtype=np.float64)
    rim_y = c[1] - R + CORNEA_PROTRUDE if False else None  # 不用
    print(f"=== {side} eye center={np.round(c,4)} r={R*1000:.1f}mm ===")
    front_pole_y = c[1] - R
    back_pole_y = c[1] + R
    print(f"  front pole y={front_pole_y:.4f}, back pole y={back_pole_y:.4f}")
    # 唇缘(碗口平面) = pole_y - CUP_DEPTH 已测, 这里用球心反推: rim = c[1] - R - CORNEA_PROTRUDE... 
    # 直接用eye_socket_config记录: rim_y从pole反推不可得, 用开孔椭圆边界顶点
    c3 = np.array(d[key]["center_3d"], dtype=np.float64)
    dx = (V[:,0]-c3[0])/HOLE_RX; dz = (V[:,2]-c3[2])/HOLE_RZ
    r2 = dx*dx + dz*dz
    # 碗内顶点(开口椭圆内, 且在球心后方区域)
    in_hole = (r2 < 1.0)
    hole_verts = V[in_hole]
    if len(hole_verts):
        # 碗表面在球心前/后的分布: 眼睑皮肤(碗内面)与球面的关系
        # 球面方程: |p - c| = R. 碗内面顶点到球心距离 < R => 皮肤穿进球体(穿帮)
        dist_to_center = np.linalg.norm(hole_verts - c, axis=1)
        n_pen = int((dist_to_center < R).sum())
        if n_pen:
            pen_depth = (R - dist_to_center[dist_to_center < R])
            print(f"  !! {n_pen} eyelid verts INSIDE eyeball, max penetration={pen_depth.max()*1000:.2f}mm, mean={pen_depth.mean()*1000:.2f}mm")
        else:
            # 最小间隙
            gap = (dist_to_center - R).min()
            print(f"  no penetration; min skin-to-sphere gap={gap*1000:.2f}mm")
    # 球体在开口平面(z方向上下缘)处相对脸表面的前凸
    # 取开口上缘(z=cz+rz)与下缘(z=cz-rz)处的脸表面最前y
    for zlabel, zoff in [("upper_lid", +HOLE_RZ), ("lower_lid", -HOLE_RZ)]:
        band = (np.abs(V[:,2]-(c3[2]+zoff)) < 0.002) & (np.abs(V[:,0]-c3[0]) < HOLE_RX)
        if band.sum():
            skin_front_y = V[band,1].min()
            # 球面在该z处的最前y: c_y - sqrt(R^2 - zoff^2)
            sphere_front_y = c[1] - np.sqrt(max(R*R - zoff*zoff, 0))
            print(f"  {zlabel}: skin_front_y={skin_front_y:.4f}, sphere_front_y={sphere_front_y:.4f}, sphere-protrude={(skin_front_y-sphere_front_y)*1000:+.2f}mm (+ = sphere in front of skin)")
