"""debug: 钉死坐标朝向 + 量化眼球凸出方向
1. 鼻尖应是脸区最靠前的点 -> 确定哪个轴/符号是"前"
2. 对比: 当前球心 vs 拟合虚拟球心 vs 角膜交点 的y关系
"""
import bpy, sys, os
import numpy as np
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import DDFA_JSON
from eye_socket_config import IN_BLEND as REPAIR_BLEND

bpy.ops.wm.open_mainfile(filepath=REPAIR_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
mesh = obj.data
nv = len(mesh.vertices)
V = np.empty(nv*3, dtype=np.float32)
mesh.vertices.foreach_get("co", V)
V = V.reshape(nv, 3).astype(np.float64)

# 脸区: 眼带z附近(1.55~1.75), x小(中线附近±0.06)
face = (V[:,2] > 1.50) & (V[:,2] < 1.80) & (np.abs(V[:,0]) < 0.06)
F = V[face]
# 鼻尖 = 脸区最"前"的点. 前=? 先看y的极值
i_min_y = np.argmin(F[:,1]); i_max_y = np.argmax(F[:,1])
print(f"face region: {len(F)} verts")
print(f"  min y vert (most -Y): {np.round(F[i_min_y],4)}  <- if nose, then -Y=forward")
print(f"  max y vert (most +Y): {np.round(F[i_max_y],4)}")

d = json.load(open(DDFA_JSON, encoding="utf-8"))
for side in ("L","R"):
    c3 = np.array(d[side]["center_3d"], dtype=np.float64)
    # 当前摆入球心 (run_eyeball最后一次: rim_y + r - protrude + 0.0021)
    print(f"=== {side} ===")
    print(f"  3DDFA cornea point y = {c3[1]:.4f}")
