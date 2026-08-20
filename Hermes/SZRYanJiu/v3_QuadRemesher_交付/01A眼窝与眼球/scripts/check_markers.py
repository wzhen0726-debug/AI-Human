"""读取当前标记点位置, 确认左右眼状态, 然后镜像."""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

MARKERS = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01A_markers_eyelid.blend")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=MARKERS)

# 获取depsgraph(约束评估后)
dg = bpy.context.evaluated_depsgraph_get()

for side in ['L', 'R']:
    coll = bpy.data.collections.get(f"LM_{side}")
    if not coll: continue
    objs = sorted([o for o in coll.objects], key=lambda o: o.name)
    pts = []
    for o in objs:
        eo = o.evaluated_get(dg)
        p = eo.matrix_world.translation
        pts.append((p.x, p.y, p.z))
    print(f"{side}眼 ({len(pts)}点):")
    for i, (x,y,z) in enumerate(pts):
        print(f"  {objs[i].name}: x={x:.4f} y={y:.4f} z={z:.4f}")

# 打印左右眼z范围对比
import numpy as np
for side in ['L','R']:
    coll = bpy.data.collections.get(f"LM_{side}")
    if not coll: continue
    objs = sorted([o for o in coll.objects], key=lambda o: o.name)
    pts = [np.array(o.evaluated_get(dg).matrix_world.translation) for o in objs]
    pts = np.array(pts)
    print(f"\n{side} bbox: x[{pts[:,0].min():.4f},{pts[:,0].max():.4f}] z[{pts[:,2].min():.4f},{pts[:,2].max():.4f}]")