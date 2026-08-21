"""测量: 眼开口上下缘z + 虹膜实际直径(缩放后), 用于计算"上睑压虹膜/下睑露虹膜"的理想摆位."""
import bpy, os, sys, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *
from eye002_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)

# 1) 手动轮廓的上下眼睑缘(开口最高/最低点)
cont = json.load(open(EYE_XZ_JSON, encoding="utf-8"))
for side in ("L", "R"):
    pts = np.array(cont[side]["rim_3d"])
    c = np.array(cont[side]["center"])
    z_top = pts[:, 2].max(); z_bot = pts[:, 2].min()
    print(f"{side}: 开口中心z={c[2]:.4f} 上缘z={z_top:.4f}(中心+{z_top-c[2]:+.4f}m) 下缘z={z_bot:.4f}(中心{z_bot-c[2]:+.4f}m) 开口高={z_top-z_bot:.4f}m={1000*(z_top-z_bot):.1f}mm")

# 2) 虹膜几何尺寸(Eye002_L里的虹膜部分: 找角膜隆起区)
eye = bpy.data.objects["Eye002_L"]
import bmesh
bm = bmesh.new(); bm.from_mesh(eye.data); bm.transform(eye.matrix_world)
vs = np.array([v.co[:] for v in bm.verts])
# 眼球前部: y最小的10%顶点(角膜区, 脸朝-Y)
ymin = vs[:, 1].min(); yspan = vs[:, 1].max() - ymin
front = vs[vs[:, 1] < ymin + 0.15 * yspan]
print(f"角膜区顶点数={len(front)} x范围={np.ptp(front[:,0]):.4f} z范围={np.ptp(front[:,2]):.4f}")
# 虹膜直径≈角膜区横向宽度的主要部分: 用x和z跨度的较大者估计虹膜盘直径
print(f"估算虹膜可见直径≈{1000*max(np.ptp(front[:,0]), np.ptp(front[:,2])):.1f}mm")
bm.free()
print("done")
