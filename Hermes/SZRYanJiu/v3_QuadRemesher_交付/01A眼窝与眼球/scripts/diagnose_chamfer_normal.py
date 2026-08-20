"""诊断倒角带两端(ring0皮肤侧/ring1碗面侧)的法线方向, 设计正确过渡曲线."""
import bpy, os, sys, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
mesh = obj.data
mat = obj.matrix_world
n_rot = mat.to_3x3()

# 读tag层: 0=皮肤 1=倒角带 2=碗面
tag_layer = None
for name in mesh.attributes.keys() if hasattr(mesh.attributes, 'keys') else []:
    pass
# 用 face 的 v44tag 属性
tag_names = [a for a in dir(mesh) if 'tag' in a.lower()]
print("mesh属性:", [a for a in dir(mesh) if 'layer' in a.lower() or 'attribute' in a.lower()][:10])

# 直接用面法线 + 顶点邻接分类
# 找眼窝区, 用3DDFA中心
import json
ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))
C = np.array(ddfa["L"]["center_3d"])

# 收集面: 眼窝区 xz<25mm, 分类
faces = []
for f in mesh.polygons:
    fc = mat @ f.center
    dx = fc[0]-C[0]; dz = fc[2]-C[2]
    dxz = math.sqrt(dx*dx+dz*dz)
    if dxz < 0.028:
        wn = n_rot @ f.normal
        faces.append((dxz, fc[2], fc[1], wn.y, f.index))

faces = np.array(faces)
print(f"眼窝区面数: {len(faces)}")
# 按径向距离分带
for lo,hi,label in [(0,0.005,'碗底'),(0.005,0.012,'碗中'),(0.012,0.015,'碗口'),(0.015,0.020,'倒角带/皮肤过渡'),(0.020,0.028,'皮肤')]:
    band = faces[(faces[:,0]>=lo)&(faces[:,0]<hi)]
    if len(band)==0: continue
    ny = band[:,3]
    print(f"  {label} (r{lo*1000:.0f}-{hi*1000:.0f}mm): {len(band)}面, normal.y均值={ny.mean():.3f} 中位={np.median(ny):.3f} 朝-Y占比={(ny<0).mean()*100:.0f}%")