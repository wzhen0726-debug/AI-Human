"""诊断M形线性质: 检查倒角带/碗面UV分配, 看是否是UV(0,0)残留或贴图区突变.
同时检查实体着色下的法线连续性(确认几何无问题).
"""
import bpy, os, sys, math, json, bmesh
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
mesh = obj.data

ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))
C = np.array(ddfa["R"]["center_3d"])

# 检查tag层的UV: 倒角带(1)和碗面(2)的UV分布
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(mesh)
bm.faces.ensure_lookup_table()

tag_l = bm.faces.layers.int.get("v44tag_R")
uv_layer = bm.loops.layers.uv.active

for tag_val, name in [(0, "原始皮肤"), (1, "倒角带"), (2, "碗面")]:
    uvs = []
    for f in bm.faces:
        if tag_l and f[tag_l] == tag_val:
            for loop in f.loops:
                uv = loop[uv_layer].uv
                uvs.append((uv.x, uv.y))
    if uvs:
        uvs = np.array(uvs)
        print(f"{name} (tag={tag_val}): {len(uvs)} loops, u[{uvs[:,0].min():.3f},{uvs[:,0].max():.3f}] v[{uvs[:,1].min():.3f},{uvs[:,1].max():.3f}]")
        # 检查是否有(0,0)或异常UV
        zero = ((uvs[:,0]<0.01)&(uvs[:,1]<0.01)).sum()
        if zero: print(f"  WARNING: {zero} loops UV=(0,0)!")

# 检查法线连续性: 倒角带与碗面交界处
mat = obj.matrix_world
n_rot = mat.to_3x3()
# 找倒角带(tag=1)和碗面(tag=2)的面, 按角度分上下
upper_ny = []; lower_ny = []
for f in bm.faces:
    if tag_l and f[tag_l] in [1, 2]:
        fc = mat @ f.calc_center_median()
        dz = fc[2] - C[2]
        wn = n_rot @ f.normal
        if dz > 0.003:  # 上半
            upper_ny.append(wn.y)
        elif dz < -0.003:  # 下半
            lower_ny.append(wn.y)

print(f"\n上半部倒角带+碗面: {len(upper_ny)}面, normal.y均值={np.mean(upper_ny):.3f}")
print(f"下半部倒角带+碗面: {len(lower_ny)}面, normal.y均值={np.mean(lower_ny):.3f}")