"""面级UV采样: 眼区内(面心r<22mm)的每个面, 输出面心世界(x,z)+面心UV+该面平均贴图亮度.
正确做法: 遍历面, 取面的loop_indices拿真实UV(不取顶点第一次loop, 避免seam错).
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

# 批量: loop顶点索引, loop uv, 顶点坐标
loop_vert = np.zeros(len(mesh.loops), dtype=np.int32)
mesh.loops.foreach_get('vertex_index', loop_vert)
uv_all = np.zeros(len(mesh.loops)*2, dtype=np.float64)
uv_layer.data.foreach_get('uv', uv_all)
uv_all = uv_all.reshape(-1,2)
verts = np.zeros(len(mesh.vertices)*3, dtype=np.float64)
mesh.vertices.foreach_get('co', verts)
verts = verts.reshape(-1,3)
# 世界坐标
wverts = np.zeros_like(verts)
for i in range(3):
    wverts[:,i] = (mat[i][0]*verts[:,0]+mat[i][1]*verts[:,1]+mat[i][2]*verts[:,2]+mat[i][3])

# 面循环索引(每面首个loop)和面顶点数
pls = np.zeros(len(mesh.polygons), dtype=np.int32)
mesh.polygons.foreach_get('loop_start', pls)
ptot = np.zeros(len(mesh.polygons), dtype=np.int32)
mesh.polygons.foreach_get('loop_total', ptot)

out = {}
for side, ic in [('L', IRIS_L), ('R', IRIS_R)]:
    cx,cy,cz = ic
    rows = []
    for pi in range(len(mesh.polygons)):
        ls = pls[pi]; lt = ptot[pi]
        # 面心(世界)
        lv = loop_vert[ls:ls+lt]
        fc = wverts[lv].mean(axis=0)
        dx = fc[0]-cx; dz = fc[2]-cz
        r = math.sqrt(dx*dx+dz*dz)
        if r > 0.022: continue
        # 面心UV
        fu = uv_all[ls:ls+lt,0].mean()
        fv = uv_all[ls:ls+lt,1].mean()
        if not (0.0 < fu < 1.0 and 0.0 < fv < 1.0): continue
        rows.append((fc[0], fc[2], fu, fv))
    out[side] = np.array(rows)
    if len(rows):
        u = out[side][:,2]; v = out[side][:,3]
        print(f"{side}: {len(rows)} faces, uv u[{u.min():.3f},{u.max():.3f}] v[{v.min():.3f},{v.max():.3f}]")

np.savez(os.path.join(os.path.dirname(os.path.abspath(__file__)), "eye_face_uv.npz"),
         L_uv=out['L'], R_uv=out['R'])
print("saved eye_face_uv.npz")
