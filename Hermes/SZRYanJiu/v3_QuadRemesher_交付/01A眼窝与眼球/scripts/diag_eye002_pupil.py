"""诊断eye002瞳孔(系统python+PIL): 读Hazel_D贴图, 在虹膜UV区域内找瞳孔质心, 算盘面偏移."""
import os, json
import numpy as np
from PIL import Image

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\眼睛模型002"

uvr = json.load(open(os.path.join(SCRIPTS, "logs", "iris_uv_range.json")))
umin, umax, vmin, vmax = uvr["umin"], uvr["umax"], uvr["vmin"], uvr["vmax"]
uc, vc = (umin+umax)/2, (vmin+vmax)/2

tex = os.path.join(MODEL_DIR, "Textures", "Eye_Hazel_D.tga")
im = Image.open(tex).convert("RGB")
im = im.transpose(Image.FLIP_TOP_BOTTOM)  # GL(左下原点)→图像坐标(左上原点)
W, H = im.size
px = np.asarray(im).astype(np.float32)
lum = px.mean(axis=2)

u0, u1 = max(0, int(umin*W)), min(W, int(umax*W))
v0, v1 = max(0, int(vmin*H)), min(H, int(vmax*H))
sub = lum[v0:v1, u0:u1]
thr = np.percentile(sub.flatten(), 15)
mask = sub <= thr
ys, xs = np.where(mask)
pup_u = (u0 + xs.mean()) / W
pup_v = (v0 + ys.mean()) / H
print(f"贴图={W}x{H} 虹膜UV区域=({umin:.4f},{vmin:.4f})~({umax:.4f},{vmax:.4f})")
print(f"瞳孔UV质心(最暗15%)=({pup_u:.4f},{pup_v:.4f})")
print(f"虹膜UV中心=({uc:.4f},{vc:.4f})")
print(f"UV偏移: du={pup_u-uc:+.4f} dv={pup_v-vc:+.4f}")

# 盘面换算: 虹膜盘直径实测11.3mm (Eye_Iris bbox xz)
D = 11.3
shift_x = (pup_u - uc) / (umax - umin) * D
shift_y = (pup_v - vc) / (vmax - vmin) * D
print(f"盘面瞳孔偏移(缩放前): 水平{shift_x:+.2f}mm 垂直{shift_y:+.2f}mm")
print(f"  → 瞳孔不在虹膜中心! 眼睛模型002的虹膜贴图瞳孔偏{('下' if shift_y<0 else '上')}, "
      f"若要正视需旋转眼球补偿, 或接受瞳孔偏位")
