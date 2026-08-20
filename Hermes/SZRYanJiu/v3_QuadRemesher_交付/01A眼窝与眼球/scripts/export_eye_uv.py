"""高效导出输入模型眼区顶点的 (x,z,u,v) — 用foreach_get批量, 不逐个polygon循环.
"""
import bpy, os, sys, math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
mesh = obj.data
mat = obj.matrix_world
uv_layer = mesh.uv_layers.active

# 批量读顶点世界坐标 + 顶点UV(每顶点可能多UV, 取loop里第一个)
verts = np.zeros(len(mesh.vertices)*3, dtype=np.float64)
mesh.vertices.foreach_get('co', verts)
verts = verts.reshape(-1,3)
# 世界坐标 (矩阵逐行乘, 避免Matrix@ndarray不兼容)
wverts = np.zeros_like(verts)
for i in range(3):
    wverts[:,i] = (mat[i][0]*verts[:,0] + mat[i][1]*verts[:,1] + mat[i][2]*verts[:,2] + mat[i][3])

# 顶点→UV: 用第一个loop
v_uv = np.full((len(mesh.vertices), 2), -1.0, dtype=np.float64)
loop_vert = np.zeros(len(mesh.loops), dtype=np.int32)
mesh.loops.foreach_get('vertex_index', loop_vert)
uv_all = np.zeros(len(mesh.loops)*2, dtype=np.float64)
uv_layer.data.foreach_get('uv', uv_all)
uv_all = uv_all.reshape(-1,2)
# 每个顶点取第一次出现的loop的uv
first = -np.ones(len(mesh.vertices), dtype=np.int32)
for i in range(len(loop_vert)):
    vi = loop_vert[i]
    if first[vi] < 0:
        first[vi] = i
valid = first >= 0
v_uv[valid] = uv_all[first[valid]]

out = {}
for side, ic in [('L', IRIS_L), ('R', IRIS_R)]:
    cx, cy, cz = ic
    dx = wverts[:,0]-cx; dz = wverts[:,2]-cz
    r = np.sqrt(dx*dx+dz*dz)
    m = (r < 0.022) & (v_uv[:,0] > 0.0) & (v_uv[:,0] < 1.0) & (v_uv[:,1] > 0.0) & (v_uv[:,1] < 1.0)
    data = np.column_stack([wverts[m,0], wverts[m,2], v_uv[m,0], v_uv[m,1]])
    out[side] = data
    print(f"{side}: {len(data)} uv samples, uv范围 x[{v_uv[m,0].min():.3f},{v_uv[m,0].max():.3f}] y[{v_uv[m,1].min():.3f},{v_uv[m,1].max():.3f}]")

np.savez(os.path.join(os.path.dirname(os.path.abspath(__file__)), "eye_uv_cloud.npz"),
         L_uv=out['L'], R_uv=out['R'])
print("saved eye_uv_cloud.npz")