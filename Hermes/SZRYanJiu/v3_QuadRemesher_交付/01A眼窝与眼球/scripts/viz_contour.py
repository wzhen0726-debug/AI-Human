"""可视化: 用户打点(12点) vs 管线用的轮廓(72点) vs 当前01_1模型的ring0边界.
输出screenshots/contour_compare.png, 检查M形来源.
"""
import bpy, os, sys, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

# 1. 用户打点(原始12点, 从blend读)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01A_markers_eyelid.blend"))
r_coll = bpy.data.collections.get("LM_R")
r_objs = sorted([o for o in r_coll.objects], key=lambda o: o.name)
marker_pts = np.array([[o.location.x, o.location.z] for o in r_objs])

# 2. 管线用的轮廓(72点)
d = json.load(open(EYELID_CONTOUR_JSON, encoding="utf-8"))
contour = np.array([[p[0], p[2]] for p in d["R"]["rim_3d"]])

# 3. 当前01_1模型的ring0边界(开放边环)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
mesh = obj.data
mat = obj.matrix_world
C = np.array(json.load(open(DDFA_JSON, encoding="utf-8"))["R"]["center_3d"])
boundary = []
for e in mesh.edges:
    if len(e.link_loops) <= 1:  # 开放边
        p0 = mat @ mesh.vertices[e.vertices[0]].co
        p1 = mat @ mesh.vertices[e.vertices[1]].co
        mx = (p0.x+p1.x)/2; mz = (p0.z+p1.z)/2
        if abs(mx-C[0])<0.030 and abs(mz-C[2])<0.030:
            boundary.append([mx, mz])
boundary = np.array(boundary)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, ax = plt.subplots(1,1, figsize=(10,8))
ax.plot(marker_pts[:,0], marker_pts[:,1], 'ro-', markersize=8, linewidth=2, label='user markers(12)')
ax.plot(contour[:,0], contour[:,1], 'b-', linewidth=1.5, alpha=0.8, label='contour(72 CR spline)')
ax.plot(boundary[:,0], boundary[:,1], 'g.', markersize=2, alpha=0.5, label='current ring0 boundary')
ax.plot(C[0], C[2], 'k+', markersize=15, label='center')
ax.set_xlabel('x'); ax.set_ylabel('z')
ax.set_title('R eye: markers vs contour vs ring0')
ax.legend(); ax.grid(True, alpha=0.3); ax.set_aspect('equal')
# 标注12个点编号
for i,(x,z) in enumerate(marker_pts):
    ax.annotate(str(i), (x,z), fontsize=8, xytext=(3,3), textcoords='offset points')
out = os.path.join(SHOT_DIR, "contour_compare_R.png")
plt.savefig(out, dpi=150, bbox_inches='tight')
print("saved:", out)