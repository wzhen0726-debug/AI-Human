"""debug: 测原始高模眼部区域的表面几何, 找出是否有眼球鼓包及其顶点位置
目的: 判断 rim_front_y=-0.1193 是真实脸面还是鼓包裙边, 决定眼球深度基准"""
import bpy, sys, os
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import IN_BLEND as REPAIR_BLEND
from eyeball_config import DDFA_JSON
import json

bpy.ops.wm.open_mainfile(filepath=REPAIR_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
mesh = obj.data
nv = len(mesh.vertices)
V = np.empty(nv * 3, dtype=np.float32)
mesh.vertices.foreach_get("co", V)
V = V.reshape(nv, 3)

d = json.load(open(DDFA_JSON, encoding="utf-8"))
for side, key in [("L", "L"), ("R", "R")]:
    c = np.array(d[key]["center_3d"], dtype=np.float32)
    print(f"=== {side} eye, 3DDFA center={c} ===")
    # 眼区局部: x/z距中心25mm内的所有顶点
    dx = V[:, 0] - c[0]
    dz = V[:, 2] - c[2]
    near = (dx*dx + dz*dz) < 0.025**2
    sub = V[near]
    # 最前顶点(apex)
    i_apex = np.argmin(sub[:, 1])
    apex = sub[i_apex]
    print(f"  local apex (most -y): {apex}  ({np.linalg.norm(apex[:2]-c[:2])*1000:.1f}mm off-center in xz)")
    # 按y分层的顶点分布(看鼓包形态)
    ys = sub[:, 1]
    for pctl in [0, 1, 5, 25, 50]:
        print(f"  y p{pctl}: {np.percentile(ys, pctl):.4f}")
    # 鼓包顶点数: y比3DDFA中心更靠前的顶点
    n_bump = int((ys < c[1]).sum())
    print(f"  verts in-front-of-3DDFA-center: {n_bump}/{len(sub)}")
    # 这些更靠前顶点的xz散布(鼓包范围)
    bump = sub[ys < c[1]]
    if len(bump) > 10:
        bmin, bmax = bump[:, [0,2]].min(0), bump[:, [0,2]].max(0)
        print(f"  bump xz extent: x[{bmin[0]:.4f},{bmax[0]:.4f}] z[{bmin[1]:.4f},{bmax[1]:.4f}]")
        print(f"  bump radius approx: {max(bmax[0]-bmin[0], bmax[1]-bmin[1])/2*1000:.1f}mm")
