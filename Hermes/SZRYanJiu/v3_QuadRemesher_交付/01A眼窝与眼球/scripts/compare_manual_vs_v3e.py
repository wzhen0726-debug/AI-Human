"""对比: blend内眼球当前位置(用户手动调整后) vs v3e脚本计算位置, 输出差值找规律."""
import bpy, os, sys, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *
from eye002_config import *
import run_eyeball_v2 as rev2

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
cont = json.load(open(EYE_XZ_JSON, encoding="utf-8"))

print("=== 用户手动位置 vs v3e计算位置 ===")
for side in ("L", "R"):
    eye = bpy.data.objects[f"Eye002_{side}"]
    cur = np.array(eye.location[:])
    c = cont[side]["center"]
    pts = np.array(cont[side]["rim_3d"])
    rim_y = float(pts[:, 1].mean())
    z_top, z_bot = float(pts[:, 2].max()), float(pts[:, 2].min())
    corneal = rev2.measure_corneal_dist(eye)
    # v3e公式: cy=rim_y+corneal-PROT, cz=c[2]+Z_OFF
    v3e_y = rim_y + corneal - EYE_PROTRUSION_MM / 1000.0
    v3e_z = c[2] + EYE_Z_OFFSET_MM / 1000.0
    print(f"{side}: 手动=({cur[0]:.4f},{cur[1]:.4f},{cur[2]:.4f}) v3e=({c[0]:.4f},{v3e_y:.4f},{v3e_z:.4f}) "
          f"差mm: x={1000*(cur[0]-c[0]):+.2f} y={1000*(cur[1]-v3e_y):+.2f} z={1000*(cur[2]-v3e_z):+.2f}")
    apex = cur[1] - corneal
    print(f"   手动角膜顶点y={apex:.5f} vs 开口平面y={rim_y:.5f} → 凸出={1000*(apex-rim_y):+.2f}mm")
    print(f"   手动虹膜中心z偏移={1000*(cur[2]-c[2]):+.2f}mm | 上缘z={z_top:.4f} 下缘z={z_bot:.4f} 开口中心z={c[2]:.4f}")
print("done")
