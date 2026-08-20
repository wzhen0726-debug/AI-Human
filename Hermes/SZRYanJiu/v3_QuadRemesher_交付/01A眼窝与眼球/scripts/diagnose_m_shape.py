"""诊断M形线的3D位置: 眼窝区沿Y轴(深度)扫描, 按径向距离分带统计Y分布.
法线突变环线 = 某径向带的Y分布突跳(折角). 找出折角在哪个径向带.
"""
import bpy, os, sys, math, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
mesh = obj.data
mat = obj.matrix_world

ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))
C = np.array(ddfa["L"]["center_3d"])

# 收集眼窝区顶点(不是面, 顶点更精确): (r, theta, y)
verts = []
for v in mesh.vertices:
    co = mat @ v.co
    dx = co[0]-C[0]; dz = co[2]-C[2]
    r = math.sqrt(dx*dx+dz*dz)
    th = math.atan2(dz, dx)
    if r < 0.028 and co[1] < C[1]+0.03:
        verts.append((r, th, co[1]))
verts = np.array(verts)
print(f"眼窝区顶点: {len(verts)}")

# 按径向分带, 统计Y均值/标准差 (折角处Y突跳)
bands = [(0,3),(3,6),(6,9),(9,12),(12,15),(15,18),(18,21),(21,25),(25,28)]
print("径向分带 Y分布 (找突跳=折角):")
prev_mean = None
for lo,hi in bands:
    m = (verts[:,0]*1000>=lo)&(verts[:,0]*1000<hi)
    if m.sum()<5: continue
    y = verts[m,2]*1000  # mm
    mean_y = y.mean()
    jump = mean_y - prev_mean if prev_mean is not None else 0
    print(f"  r{lo:2d}-{hi:2d}mm: n={m.sum():4d} Y均值={mean_y:7.2f}mm std={y.std():.2f} 跳变={jump:+.2f}mm")
    prev_mean = mean_y