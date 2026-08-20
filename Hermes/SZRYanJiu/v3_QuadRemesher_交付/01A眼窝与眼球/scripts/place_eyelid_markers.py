"""在输入高模上放置眼睑缘标记点 - 只R眼. 用户调好后镜像到L.

每眼12个标记点, 初始位置=3DDFA眼裂轮廓(加密12点).
Shrinkwrap约束吸附表面, show_in_front=True穿模可见.
输出: models/01A_markers_eyelid.blend
"""
import bpy, os, sys, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

NAMES = [
    ("外眼角", "outer_canthus"),
    ("上睑外", "upper_outer"),
    ("上睑中外", "upper_mid_outer"),
    ("上睑中", "upper_mid"),
    ("上睑中内", "upper_mid_inner"),
    ("上睑内", "upper_inner"),
    ("内眼角", "inner_canthus"),
    ("下睑内", "lower_inner"),
    ("下睑中内", "lower_mid_inner"),
    ("下睑中", "lower_mid"),
    ("下睑中外", "lower_mid_outer"),
    ("下睑外", "lower_outer"),
]
N_PTS = 12

def load_3ddfa_resampled(side, n=N_PTS):
    d = json.load(open(EYELID_CONTOUR_3DDFA_JSON, encoding="utf-8"))
    rim = [r for r in d[side]["rim_3d"] if r is not None]
    pts = np.array(rim, dtype=np.float64)
    M = len(pts)
    seg = [np.linalg.norm(pts[(i+1)%M]-pts[i]) for i in range(M)]
    total = sum(seg)
    out = []
    acc = 0.0; i = 0
    for k in range(n):
        target = total*k/n
        while acc+seg[i] < target and i < M:
            acc += seg[i]; i = (i+1)%M
        t = (target-acc)/seg[i] if seg[i] > 1e-12 else 0
        out.append(pts[i] + (pts[(i+1)%M]-pts[i])*t)
    return out

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]

# 清除旧标记集合
for cname in ["LM_L", "LM_R"]:
    c = bpy.data.collections.get(cname)
    if c:
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(c)

# 只做R眼
pts = load_3ddfa_resampled('R')
coll = bpy.data.collections.new("LM_R")
bpy.context.scene.collection.children.link(coll)
for k, (cn, en) in enumerate(NAMES):
    x, y, z = pts[k]
    e = bpy.data.objects.new(f"LM_{k+1:02d}_{cn}_{en}_R", None)
    e.empty_display_type = 'SPHERE'
    e.empty_display_size = 0.0025
    e.location = (x, y, z)
    e.show_in_front = True
    e.color = (0.3, 0.6, 1.0, 1.0)  # 蓝色
    coll.objects.link(e)
    sw = e.constraints.new(type='SHRINKWRAP')
    sw.target = obj
    sw.shrinkwrap_type = 'NEAREST_SURFACE'
    sw.distance = 0.0

# 清空L眼集合(如果存在)
lc = bpy.data.collections.get("LM_L")
if lc:
    for o in list(lc.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(lc)
# 创建空的L眼集合(供镜像脚本填充)
lcoll = bpy.data.collections.new("LM_L")
bpy.context.scene.collection.children.link(lcoll)

out = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01A_markers_eyelid.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print(f"R眼: {len(NAMES)}个标记点, 集合 LM_R")
print("L眼: 空集合 LM_L (等待镜像)")
print("saved:", out)