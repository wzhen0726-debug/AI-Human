"""导出眼区顶点云到npz, 供纯Python分析眼窝rim.
含: 每顶点(x,y,z) + 顶点法线 + 虹膜中心. 半径25mm.
"""
import bpy, os, sys, math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
mesh = obj.data
# 世界空间顶点+法线
mat = obj.matrix_world
n_rot = mat.to_3x3()
out = {}
for side, ic in [('L', IRIS_L), ('R', IRIS_R)]:
    center = np.array(ic)
    coords, norms = [], []
    for v in mesh.vertices:
        co = mat @ v.co
        dx = co[0]-center[0]; dz = co[2]-center[2]
        if math.sqrt(dx*dx+dz*dz) < 0.025 and co[1] < center[1]+0.02:
            coords.append([co[0], co[1], co[2]])
            norms.append(list(n_rot @ v.normal))
    out[side] = {"coords": np.array(coords), "normals": np.array(norms), "center": center.tolist()}
    print(f"{side}: {len(coords)} verts")

np.savez(os.path.join(os.path.dirname(os.path.abspath(__file__)), "eye_region_cloud.npz"),
         L_coords=out['L']['coords'], L_normals=out['L']['normals'], L_center=out['L']['center'],
         R_coords=out['R']['coords'], R_normals=out['R']['normals'], R_center=out['R']['center'])
print("saved eye_region_cloud.npz")
