"""PIL定量对比v46i/v46j线框图: 黑像素占比+径向分布. 排除vision误读."""
from PIL import Image
import math

def analyze(path, label):
    im = Image.open(path).convert("L")
    w, h = im.size
    px = im.load()
    total = w * h
    dark = 0
    # 以图像中心为参考, 径向分带统计黑像素
    cx, cy = w / 2, h / 2
    maxr = math.sqrt(cx*cx + cy*cy)
    bands = [0] * 8
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if px[x, y] < 100:
                dark += 1
                r = math.sqrt((x-cx)**2 + (y-cy)**2)
                b = min(int(r / maxr * 8), 7)
                bands[b] += 1
    sample = (w//2) * (h//2)
    print(f"{label}: {w}x{h} 暗像素占比={dark/sample*100:.2f}%")
    print(f"  径向分布(中心→边缘8带): {['%.1f' % (b/sample*100) for b in bands]}%")

base = "../screenshots/"
analyze(base + "v46i_R_wireframe.png", "v46i")
analyze(base + "v46j_R_wireframe.png", "v46j")
