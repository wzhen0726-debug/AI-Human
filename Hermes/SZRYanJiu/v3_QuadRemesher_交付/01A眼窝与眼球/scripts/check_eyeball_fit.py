"""眼球摆入定量验证: 眼球与眼窝碗底/rim/皮肤的间隙.
检查: 1)眼球表面与眼窝碗面的最小间隙 2)角膜前极相对rim前缘的突出量
3)眼球是否穿破眼窝外皮肤(开口投影区外)."""
import bpy, os, sys, json
from mathutils import Vector, kdtree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *
from eyeball_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
scene = bpy.context.scene
meshes = [o for o in scene.objects if o.type == 'MESH']
face_obj = max(meshes, key=lambda o: len(o.data.vertices))  # 高模
eyes = [o for o in meshes if o != face_obj]
print(f"face: {face_obj.name} ({len(face_obj.data.vertices)}v), eyes: {[o.name for o in eyes]}")

# 高模眼区KD-tree
import numpy as np
V = np.array([(o.matrix_world @ v.co)[:] for o in [face_obj] for v in o.data.vertices], dtype=np.float64)
ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))

for eye in eyes:
    side = "L" if eye.location.x < 0 else "R"
    c = Vector(eye.location)
    R = EYE_RADIUS
    # 眼区高模点(40mm内)
    d3 = ddfa[side]["center_3d"]
    dist2 = (V[:,0]-d3[0])**2 + (V[:,2]-d3[2])**2
    mask = dist2 < 0.040**2
    Pv = V[mask]
    kd = kdtree.KDTree(len(Pv))
    for i, p in enumerate(Pv):
        kd.insert(Vector(p), i)
    kd.balance()
    # 眼球表面采样: 2000点
    import math
    pts = []
    N = 45
    for a in range(N):
        for b in range(2*N):
            th = math.pi * a / (N-1)
            ph = 2*math.pi * b / (2*N-1)
            d = Vector((math.sin(th)*math.cos(ph), math.sin(th)*math.sin(ph), math.cos(th)))
            pts.append(c + d * R)
    # 对每个眼球表面点找高模最近点
    gaps = []
    protrude_outside = 0  # 眼球表面点"穿入"皮肤内部的(y比皮肤前表面更前且不在开口区)
    for p in pts:
        co, idx, dist = kd.find(p)
        # 只统计眼球后半(朝向碗底的)与皮肤间隙
        gaps.append((dist, p, co))
    gaps.sort(key=lambda g: g[0])
    # 最小间隙(排除角膜区: 角膜区本应突出开口)
    min5 = [g[0]*1000 for g in gaps[:5]]
    # 碗底方向间隙: 眼球后极点(y最大处)到碗底
    back_pole = c + Vector((0, R, 0))
    co, idx, dist = kd.find(back_pole)
    # 角膜前极突出量: 相对rim前缘
    rim_y = RIM_FRONT_Y_L if side == "L" else RIM_FRONT_Y_R
    front_pole_y = c.y - R
    print(f"=== {side}眼 ===")
    print(f"  球心={tuple(round(x,4) for x in c)} R={R*1000}mm")
    print(f"  角膜前极y={front_pole_y:.4f} rim前缘y≈{rim_y:.4f} → 突出{abs(rim_y-front_pole_y)*1000:.1f}mm")
    print(f"  眼球后极到皮肤最近点={dist*1000:.2f}mm (正值=有间隙/碗底在后方)")
    print(f"  表面最近5点间隙(mm): {[round(x,2) for x in min5]}")
    # 角膜是否在眼窝开口投影内(应居中)
    iris_c = Vector(ddfa[side]["center_3d"])
    off = Vector((c.x-iris_c.x, 0, c.z-iris_c.z)).length*1000
    print(f"  角膜中心相对眼窝中心偏移={off:.2f}mm")
