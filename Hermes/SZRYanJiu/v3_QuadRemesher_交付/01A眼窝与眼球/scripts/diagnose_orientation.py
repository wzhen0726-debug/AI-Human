"""诊断01_1模型眼窝面朝向: 用3DDFA center_3d(与管线一致), 按z分带统计 normal.y."""
import bpy, os, sys, math, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

# 用3DDFA center_3d(与管线make_eye_cup的center一致)
ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))
C = {'L': np.array(ddfa["L"]["center_3d"]), 'R': np.array(ddfa["R"]["center_3d"])}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
mesh = obj.data
mat = obj.matrix_world
n_rot = mat.to_3x3()

for side in ['L', 'R']:
    cx, cy, cz = C[side]
    rows = []
    for f in mesh.polygons:
        fc = mat @ f.center
        dx = fc[0]-cx; dz = fc[2]-cz
        dxz = math.sqrt(dx*dx+dz*dz)
        if dxz < 0.025 and fc[1] < cy + 0.02:
            wn = n_rot @ f.normal
            rows.append((fc[1], fc[2], dxz, wn.y))
    rows = np.array(rows)
    if len(rows) == 0:
        print(f"{side}: 无眼窝面"); continue
    upper = rows[rows[:,1] >= cz]
    lower = rows[rows[:,1] < cz]
    print(f"\n=== {side}眼 眼窝面朝向 (n={len(rows)}, center_3d z={cz:.4f} y={cy:.4f}) ===")
    for label, band in [("上半(z>=中心)", upper), ("下半(z<中心)", lower)]:
        if len(band) == 0: continue
        wrong = (band[:,3] > 0.05).sum()
        total = len(band)
        print(f"  {label}: {total}面, 反向(normal.y>0.05)={wrong}面 ({wrong/total*100:.1f}%)")
        if wrong > 0:
            wb = band[band[:,3] > 0.05]
            print(f"    反向面 y[{wb[:,0].min():.4f},{wb[:,0].max():.4f}] z[{wb[:,1].min():.4f},{wb[:,1].max():.4f}] dxz[{wb[:,2].min():.4f},{wb[:,2].max():.4f}]")