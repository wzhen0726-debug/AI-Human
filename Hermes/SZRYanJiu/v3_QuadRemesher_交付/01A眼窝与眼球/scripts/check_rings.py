"""检查当前01_1模型R眼窝区的环线结构: 打印tag层面的径向距离分布, 找M形线对应的几何环."""
import bpy, os, sys, math, json, bmesh
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]

ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))
C = np.array(ddfa["R"]["center_3d"])

bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(obj.data)
bm.faces.ensure_lookup_table()

tag_l = bm.faces.layers.int.get("v44tag_R")
# 收集每个tag层面的面心径向距离
for tag_val, name in [(0, "原始皮肤"), (1, "倒角带"), (2, "碗面")]:
    rs = []
    for f in bm.faces:
        if tag_l and f[tag_l] == tag_val:
            fc = f.calc_center_median()
            dx = fc.x - C[0]; dz = fc.z - C[2]
            r = math.sqrt(dx*dx + dz*dz)
            rs.append(r)
    if rs:
        rs = np.array(rs) * 1000  # mm
        print(f"{name} (tag={tag_val}): {len(rs)}面, r范围[{rs.min():.1f},{rs.max():.1f}]mm, 均值{rs.mean():.1f}mm")
        # 分带统计
        for lo, hi in [(0,5),(5,10),(10,15),(15,20),(20,25)]:
            cnt = ((rs>=lo)&(rs<hi)).sum()
            if cnt: print(f"  r{lo:2d}-{hi:2d}mm: {cnt}面")