# -*- coding: utf-8 -*-
"""04 烘焙后贴图溢出处理 — 暗色衣物色渗出到皮肤区域 → 就近替换为皮肤色 + 边缘过渡.
2026-09-17 用户要求("04烘焙后...把溢出的颜色稍微处理一下")。

判据(全部现场计算, 无硬编码区域):
  候选 = 近黑像素 AND 局部窗口内皮肤占比>阈值 AND 距【大块暗色(衣物/裤)】≤reach AND 非UV空白区
  —— 衣物本体(局部窗口内暗色占多数)与眉毛/头发(距离衣物太远)天然被排除。
安全: 处理前自动备份; 溢出超上限(1.5%)时不写回; 打印前后计数。

用法: blender -b --python texture_fix.py            # 处理 04纹理烘焙/输出/04_diffuse_4k.png
     或  import texture_fix; fix_diffuse_png(path)   # 供 04_bake.py 调用
"""
import os
import shutil
import time
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = r"E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu/演示版_终端控制端"
DEFAULT_PNG = os.path.join(ROOT, "04纹理烘焙", "输出", "04_diffuse_4k.png")
BACKUP_ROOT = os.path.join(ROOT, "_备份")


def fix_diffuse_png(path, win=25, skin_frac_th=0.50, reach_px=18, lum_th=95,
                    max_frac=0.015, backup=True, dry=False, crop_dir=None):
    """就地处理 diffuse PNG; 返回统计 dict.
    win: 局部窗口(px)  skin_frac_th: 判定"处在皮肤中"的窗口皮肤占比阈值
    reach_px: 距衣物本体的最大距离(只处理贴着衣物边界的渗出)
    """
    im = Image.open(path).convert("RGB")
    a = np.array(im)
    H, W = a.shape[:2]
    r = a[:, :, 0].astype(np.int16); g = a[:, :, 1].astype(np.int16); b = a[:, :, 2].astype(np.int16)
    empty = (r <= 2) & (g <= 2) & (b <= 2)                      # UV空白(未烘焙) → 不是任何区域
    lum = 0.30 * r + 0.59 * g + 0.11 * b
    dark = (lum < 48) & (~empty)                                # 近黑 = 衣物/毛发本体
    skin = (r > 102) & (g > 64) & (b > 38) & (r > g) & (~empty) # 皮肤(含烘焙过渡边)
    # ① 大块暗色 = 衣物本体(连通块 > 0.5% 暗色像素者)
    lab, n = ndimage.label(dark, structure=np.ones((3, 3)))
    big = np.zeros_like(dark)
    if n > 0:
        sizes = ndimage.sum(dark, lab, index=np.arange(1, n + 1))
        thr = max(sizes.max() * 0.15, np.sum(dark) * 0.005)
        for i in np.where(sizes > thr)[0]:
            big |= (lab == i + 1)
    if not big.any():
        return dict(before=0, after=0, note="未找到衣物类大色块, 跳过")
    # ② 候选渗出: 偏暗(深褐/暗红, 亮度<lum_th) + 紧贴衣物边界(距本体≤reach_px) + 不在衣物本体核心内
    #    渗出贴合衣物边缘(窗口会被暗侧占半) → 不能用"皮肤占比高"判据; 距离+亮度即可.
    #    代价: 衣物本体边缘最外 ~5px 可能被轻微削平(4K 下 ≈0.5mm, 属"稍微处理"允差).
    dist_big = ndimage.distance_transform_edt(~big)
    # 衣物本体(近黑连通块)整块排除 → 只动它外圈的深色渗出(亮度在 本体内<48 与 阈值95 之间者)
    cand = (lum < lum_th) & (~empty) & (~big) & (dist_big <= reach_px)
    spill = cand
    before = int(spill.sum())
    if before == 0:
        return dict(before=0, after=0, note="无溢出像素")
    if before > max_frac * H * W:
        return dict(before=before, after=before, note=f"溢出>上限{max_frac:.1%}, 未写回(请人工检查判据)")
    # ③ 就近皮肤色(取溢出周边皮肤像素中位数, 避免全局偏色)
    near = ndimage.binary_dilation(spill, iterations=6)
    src = skin & near
    col = np.median(a[src], axis=0).astype(np.uint8) if src.sum() > 50 else np.median(a[skin], axis=0).astype(np.uint8)
    fixed = a.copy()
    fixed[spill] = col
    # ④ 边缘过渡(2px 带内做高斯混合, 消除硬界)
    trans = ndimage.binary_dilation(spill, iterations=2) & (~spill)
    for c in range(3):
        bl = ndimage.gaussian_filter(fixed[:, :, c].astype(np.float32), sigma=1.2)
        fixed[:, :, c] = np.where(trans, bl.astype(np.uint8), fixed[:, :, c])
    # 复检
    r2, g2, b2 = fixed[:, :, 0].astype(np.int16), fixed[:, :, 1].astype(np.int16), fixed[:, :, 2].astype(np.int16)
    lum2 = 0.30 * r2 + 0.59 * g2 + 0.11 * b2
    em2 = (r2 <= 2) & (g2 <= 2) & (b2 <= 2)
    skin2 = (r2 > 102) & (g2 > 64) & (b2 > 38) & (r2 > g2)
    lab2, n2 = ndimage.label((lum2 < 48) & (~em2), structure=np.ones((3, 3)))
    big2 = np.zeros_like(dark)
    if n2 > 0:
        sz2 = ndimage.sum((lum2 < 48) & (~em2), lab2, index=np.arange(1, n2 + 1))
        thr2 = max(sz2.max() * 0.15, np.sum(lum2 < 48) * 0.005)
        for i2 in np.where(sz2 > thr2)[0]:
            big2 |= (lab2 == i2 + 1)
    after = int(((lum2 < lum_th) & (~em2) & (~big2) & (dist_big <= reach_px)).sum())
    # 预览裁图(供人工核对, 只读输出)
    if crop_dir:
        try:
            ys, xs = np.where(spill)
            if len(ys) > 0:
                cy, cx = int(np.median(ys)), int(np.median(xs))
                x0, y0 = max(0, cx - 200), max(0, cy - 200)
                x1, y1 = min(W, cx + 200), min(H, cy + 200)
                os.makedirs(crop_dir, exist_ok=True)
                Image.fromarray(a[y0:y1, x0:x1]).save(os.path.join(crop_dir, "溢出处理_前.png"))
                Image.fromarray(fixed[y0:y1, x0:x1]).save(os.path.join(crop_dir, "溢出处理_后.png"))
        except Exception:
            pass
    if not dry:
        if backup:
            bdir = os.path.join(BACKUP_ROOT, time.strftime("%Y%m%d_%H%M%S") + "_04diffuse_处理前")
            os.makedirs(bdir, exist_ok=True)
            shutil.copy2(path, os.path.join(bdir, os.path.basename(path)))
        Image.fromarray(fixed).save(path)
    return dict(before=before, after=after, color=col.tolist(),
                note=f"{before} → {after} 像素 ({(1-after/max(before,1))*100:.1f}% 清除)" + (" [dry]" if dry else ""))


if __name__ == "__main__":
    p = os.environ.get("TEX_FIX_PNG", DEFAULT_PNG)
    st = fix_diffuse_png(p)
    print("贴图溢出处理:", st)
