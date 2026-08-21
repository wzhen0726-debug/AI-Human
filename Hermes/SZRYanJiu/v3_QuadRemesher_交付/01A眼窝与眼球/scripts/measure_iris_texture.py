# -*- coding: utf-8 -*-
"""PIL: 从Eye_Hazel_D.tga测可见虹膜(彩色区)半径占比, 结合mesh盘直径得真实可见虹膜直径."""
from PIL import Image
import numpy as np, os, glob

tex_dir = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\眼睛模型002\Textures"
cands = glob.glob(os.path.join(tex_dir, "*Hazel*"))
print("files:", [os.path.basename(c) for c in cands])
p = [c for c in cands if c.lower().endswith((".tga", ".png"))][0]
im = Image.open(p).convert("RGB")
a = np.asarray(im, dtype=np.float32)
h, w = a.shape[:2]
print("texture:", os.path.basename(p), w, "x", h)
# 瞳孔中心(最暗点附近)作为虹膜中心
gray = a.mean(axis=2)
# 在中心1/4区域内找最暗块
cy0, cx0 = h//2, w//2
r_search = min(h, w)//4
yy, xx = np.mgrid[cy0-r_search:cy0+r_search, cx0-r_search:cx0+r_search]
dark = gray.copy(); dark[dark > 60] = 255  # 只保留很暗的瞳孔像素
iy, ix = np.unravel_index(np.argmin(dark), dark.shape)
print(f"瞳孔中心≈({ix},{iy}) 最暗={dark[iy,ix]:.0f}")
# 径向饱和度剖面
mx, my = np.meshgrid(np.arange(w), np.arange(h))
R = np.sqrt((mx-ix)**2 + (my-iy)**2)
sat = a.max(axis=2) - a.min(axis=2)
rmax = int(min(w, h)/2)
prof = []
for r in range(0, rmax, 2):
    m = (R >= r) & (R < r+2)
    prof.append((r, float(sat[m].mean()), float(gray[m].mean())))
# 找饱和度从虹膜彩色跌落到近白(眼白/盘外)的半径
for r, s, g in prof:
    if r > 20 and s < 25 and g > 150:
        print(f"虹膜外缘(饱和度跌落)≈半径{r}px")
        break
else:
    print("未找到明显跌落, 输出剖面采样:")
    for r, s, g in prof[::15]:
        print(f"  r={r}px sat={s:.0f} gray={g:.0f}")
