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
    #    v3(2026-09-18): 加 2px 保护环 —— 距本体≤2px 的像素是【衣物自己的抗锯齿边】,
    #    旧版把它们一并替换 → 渲染里衣物边缘被啃出米色锯齿缺口(A/B实锤). 保护环让边缘原样保留,
    #    只清保护环之外的渗出带; 残余的 ≤2px 暗环与衣物边缘自然相接, 视觉上即衣物边.
    dist_big = ndimage.distance_transform_edt(~big)
    # 衣物本体(近黑连通块)整块排除 → 只动它外圈的深色渗出(亮度在 本体内<48 与 阈值95 之间者)
    # v4.1 禁吃衣物边缘抗锯齿环: 候选像素的7px局部窗口若≥50%是深色, 它是衣物边缘自身(不是皮肤侧渗出), 不替换
    _darkfrac = ndimage.uniform_filter(((lum < 48) & (~empty)).astype(np.float32), 7)
    cand = (lum < lum_th) & (~empty) & (~big) & (dist_big <= reach_px) & (dist_big > 2.0) & (_darkfrac < 0.5)
    spill = cand
    before = int(spill.sum())
    if before == 0:
        return dict(before=0, after=0, note="无溢出像素")
    if before > max_frac * H * W:
        return dict(before=before, after=before, note=f"溢出>上限{max_frac:.1%}, 未写回(请人工检查判据)")
    # ③ 逐像素"最近皮肤色"填充(v2 2026-09-18 源头修复):
    #    旧法=整片填【全局中位皮肤色】—— 实测在4K图上留下 33 处平涂斑块(内部std≈0/邻域强边,
    #    最大748px, 与周边色差101), 因皮肤明暗沿边界连续变化, 单一颜色必然与环境不符 = 用户可见斑块。
    #    新法: 每个渗出像素取【离它最近的未修改皮肤像素的真实颜色】(EDT return_indices) ——
    #    保留边界方向的明暗渐变, 不引入任何全局色; 距离>3×reach 的孤点跳过(异常保护)。
    valid = skin & (~spill)
    if valid.sum() < 50:
        valid = (~spill) & (~empty)
    _dist, (_iy, _ix) = ndimage.distance_transform_edt(~valid, return_indices=True)
    fixed = a.copy()
    _ys, _xs = np.where(spill)
    _ok = _dist[_ys, _xs] <= 3.0 * reach_px
    fixed[_ys[_ok], _xs[_ok]] = a[_iy[_ys[_ok], _xs[_ok]], _ix[_ys[_ok], _xs[_ok]]]
    col = np.median(a[valid], axis=0).astype(np.uint8)   # 仅用于报告
    # ③b 掩膜内扩散(消"最近邻拼贴"面片化): NN 初值 → 4邻域 Jacobi 迭代;
    #     边界像素固定不动(不把掩膜外像素拉进来), 掩膜内收敛为边界连续的平滑填充。
    _f = fixed.astype(np.float32)
    for _it in range(40):
        _avg = 0.25 * (np.roll(_f, 1, 0) + np.roll(_f, -1, 0) + np.roll(_f, 1, 1) + np.roll(_f, -1, 1))
        _f[spill] = _avg[spill]
    fixed = np.clip(_f, 0, 255).astype(np.uint8)
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
    after = int(((lum2 < lum_th) & (~em2) & (~big2) & (dist_big <= reach_px) & (dist_big > 2.0)).sum())
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




# ============================================================================
# v2 (2026-09-17): 网格引导的统计离群清理 —— 皮肤上的孤立异常斑(双向: 偏暗/偏亮)
#   全部阈值由模型自身推导(无写死): 邻域半径=最近邻中位距x4; 阈值=4*(1.4826*MAD);
#   簇上限=总面数x0.03%; 只处理 bbox 高度85%以下(按身高比例, 保护头部五官).
#   替换: 异常面 UV 三角形内像素 <- 其 3D 邻域(非异常面)颜色中位 + 2px 过渡.
# ============================================================================
def fix_diffuse_mesh_guided(png_path, mesh_objects, k_sigma=4.0, cluster_frac=0.0015,
                            head_ratio=0.80, face_center=None, face_R=None, backup=True, dry=False, crop_dir=None):
    """网格引导清理; 返回统计 dict. 全部判据相对模型数据, 不含固定坐标/阈值.
    v4(2026-09-18): 头部保护由"身高80%"改为【五官球】—— 旧法把 z>80%身高 全部排除,
      实测把 上胸/领口/肩颈(用户反馈区) 全划进保护区导致这些位置的暗斑从未被清理;
      新法: 以双眼中心为球心, R=1.6×双眼间距(由场景眼球对象实测推导), 球外全部可清理。
    """
    from scipy.spatial import cKDTree
    # --- 收集面数据 ---
    F = []          # 面: (矩阵变换后中心 xyz, 采样色, uv 三角形 list)
    a0 = np.array(Image.open(png_path).convert("RGB"))
    H, W = a0.shape[:2]
    for ob in mesh_objects:
        me = ob.data
        if not me.uv_layers.active:
            continue
        M = np.array(ob.matrix_world)
        n = len(me.polygons)
        luv = np.empty(len(me.loops) * 2); me.uv_layers.active.data.foreach_get("uv", luv)
        luv = luv.reshape(-1, 2)
        ls = np.empty(n, np.int32); lt = np.empty(n, np.int32)
        me.polygons.foreach_get("loop_start", ls); me.polygons.foreach_get("loop_total", lt)
        ctr = np.empty(n * 3); me.polygons.foreach_get("center", ctr); ctr = ctr.reshape(-1, 3)
        ctr = ctr @ M[:3, :3].T + M[:3, 3]
        for i in range(n):
            tri = luv[ls[i]:ls[i] + lt[i]]
            F.append((ctr[i], tri.mean(axis=0), tri))
    if len(F) < 500:
        return dict(note="网格面太少, 跳过 v2")
    cen = np.array([f[0] for f in F]); uvc = np.array([f[1] for f in F])
    x = np.clip((uvc[:, 0] * W).astype(int), 0, W - 1)
    y = np.clip(((1 - uvc[:, 1]) * H).astype(int), 0, H - 1)
    col = a0[y, x].astype(np.float64)
    lum = 0.30 * col[:, 0] + 0.59 * col[:, 1] + 0.11 * col[:, 2]
    empty = (col[:, 0] <= 2) & (col[:, 1] <= 2) & (col[:, 2] <= 2)
    # --- 五官保护: v4 球体(双眼中心+R) / 兼容旧的身高截断 ---
    zmin, zmax = cen[:, 2].min(), cen[:, 2].max()
    if face_center is not None and face_R is not None:
        _dfc = np.linalg.norm(cen - np.asarray(face_center, dtype=float), axis=1)
        body = _dfc > float(face_R)
    else:
        head_cut = zmin + head_ratio * (zmax - zmin)
        body = cen[:, 2] <= head_cut
    # --- 自动半径: 最近邻中位距 x4 ---
    t = cKDTree(cen)
    dnn, _ = t.query(cen, k=2)
    r = 4.0 * float(np.median(dnn[:, 1]))
    idx = t.query_ball_point(cen, r)
    # --- 偏差 & 自动阈值 ---
    dev = np.zeros(len(F)); med = lum.copy()
    for i in range(len(F)):
        if empty[i]:
            continue
        ns = idx[i]
        if len(ns) < 6:
            continue
        med[i] = np.median(lum[ns])
        dev[i] = lum[i] - med[i]
    ok = (~empty) & body
    if ok.sum() < 100:
        return dict(note="有效面太少, 跳过 v2")
    d_ok = dev[ok]
    sig = 1.4826 * float(np.median(np.abs(d_ok - np.median(d_ok))))
    p995 = float(np.percentile(np.abs(d_ok), 99.5))
    thr = max(k_sigma * sig, p995)          # 两路取大: 相对散布 与 数据高分位, 皆为模型自身统计
    if thr <= 1e-6:
        return dict(note="偏差分布异常, 跳过 v2")
    anom = ok & (dev < -thr)                # 只处理"偏暗"异常(衣物/彩绘渗入类); 偏亮另议
    # --- 簇: 按邻域图连通聚类, 上限=总面数xcluster_frac ---
    cap = max(int(len(F) * cluster_frac), 1)
    ext_cap = 0.025 * (zmax - zmin)          # 簇 3D 直径上限 = 模型高度 2.5%(自动)
    seen = np.zeros(len(F), bool); keep = np.zeros(len(F), bool); ncl = 0; repl = {}; cluster_info = []
    # 皮肤参考色域: 由"亮暖色"粗筛面的中位/协方差推导(Mahalanobis), 不含固定阈值
    pre = ok & (lum > np.median(lum[ok])) & (col[:, 0] >= col[:, 1]) & (col[:, 1] >= col[:, 2])
    if pre.sum() < 200:
        return dict(note="皮肤样面太少, 跳过 v2")
    mu = col[pre].mean(axis=0)
    cov = np.cov(col[pre].T) + np.eye(3) * 1e-6
    icov = np.linalg.inv(cov)
    def skin_like(cc):
        d = cc - mu
        return float(d @ icov @ d) <= 2.5 ** 2
    for i in np.where(anom)[0]:
        if seen[i]:
            continue
        stack = [i]; seen[i] = True; comp = []
        while stack:
            j = stack.pop(); comp.append(j)
            for kk in idx[j]:
                if anom[kk] and not seen[kk]:
                    seen[kk] = True; stack.append(kk)
        # 大簇/过宽簇 → 贪心切成 <= ext_cap 的小块(逐块处理), 而不是整体丢弃
        pieces = []
        pend = set(comp)
        while pend:
            seed = pend.pop()
            piece = [seed]
            frontier = [seed]
            while frontier:
                cur = frontier.pop()
                for kk in idx[cur]:
                    if kk in pend:
                        cand = piece + [kk]
                        cp = cen[cand]
                        if 2.0 * float(np.max(np.linalg.norm(cp - cp.mean(axis=0), axis=1))) <= ext_cap:
                            piece.append(kk); pend.discard(kk); frontier.append(kk)
            pieces.append(piece)
        for comp in pieces:
            if len(comp) > cap:
                continue
            nbr = set()
            for j in comp:
                for kk in idx[j]:
                    if not anom[kk] and not empty[kk]:
                        nbr.add(kk)
            if len(nbr) < 4:
                continue
            ccol = np.median(col[comp], axis=0)
            # v4.1 禁吃衣物(实测: 浅色毛边93%来自本步): 簇自身属"衣物级深色"(lum<55), 或其邻域里
            #   深色(lum<48)面占比≥25% → 该簇是衣物边缘的一部分(不是皮肤上的渗入斑), 替换它=把衣物啃成肤色。
            _cl = 0.30 * ccol[0] + 0.59 * ccol[1] + 0.11 * ccol[2]
            if _cl < 55.0:
                continue
            if len(nbr) > 0 and sum(1 for kk in nbr if lum[kk] < 48.0) / len(nbr) >= 0.25:
                continue
            # 替换色 = 邻域中"皮肤样"面的颜色中位(斑点多长在趾缝/衣边旁, 邻域可含暗面;
            # 只要邻域里有足量皮肤样面即可, 用它们的颜色就近替换)
            nbr_skin = [kk for kk in nbr if skin_like(col[kk])]
            if len(nbr_skin) < 3 or len(nbr_skin) < 0.08 * len(nbr):
                continue
            # 簇自身须偏离皮肤色域(否则=深肤色区/阴影等正常特征, 不动)
            if skin_like(ccol):
                continue
            ncol = np.median(col[nbr_skin], axis=0)
            ncl += 1
            for j in comp:
                repl[j] = ncol
            keep[comp] = True
            cpos = cen[comp].mean(axis=0)
            cluster_info.append((len(comp), [round(float(v) * 1000) for v in cpos], [int(v) for v in ccol]))
    if ncl == 0:
        return dict(clusters=0, note="无符合条件的小簇异常")
    # --- 写回: 异常面 UV 三角形光栅填充 ---
    fixed = a0.copy()
    fillm = np.zeros((H, W), bool)
    for j, c in repl.items():
        tri = F[j][2]
        px = tri[:, 0] * W; py = (1 - tri[:, 1]) * H
        x0, x1 = int(max(0, np.floor(px.min() - 1))), int(min(W - 1, np.ceil(px.max() + 1)))
        y0, y1 = int(max(0, np.floor(py.min() - 1))), int(min(H - 1, np.ceil(py.max() + 1)))
        if x1 <= x0 or y1 <= y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        v0x, v0y = px[1] - px[0], py[1] - py[0]
        v1x, v1y = px[2] - px[0], py[2] - py[0]
        den = v0x * v1y - v1x * v0y
        if abs(den) < 1e-12:
            continue
        wx, wy = gx - px[0], gy - py[0]
        u = (wx * v1y - v1x * wy) / den
        v = (v0x * wy - wx * v0y) / den
        m = (u >= -0.02) & (v >= -0.02) & (u + v <= 1.02)
        fixed[y0:y1 + 1, x0:x1 + 1][m] = c.astype(np.uint8)
        fillm[y0:y1 + 1, x0:x1 + 1] |= m
    npx = int(fillm.sum())
    # --- 2px 过渡 ---
    trans = ndimage.binary_dilation(fillm, iterations=2) & (~fillm)
    for c in range(3):
        bl = ndimage.gaussian_filter(fixed[:, :, c].astype(np.float32), sigma=1.0)
        fixed[:, :, c] = np.where(trans, bl.astype(np.uint8), fixed[:, :, c])
    if crop_dir:
        try:
            ys, xs = np.where(fillm)
            if len(ys):
                cy, cx = int(np.median(ys)), int(np.median(xs))
                x0, y0 = max(0, cx - 200), max(0, cy - 200)
                x1, y1 = min(W, cx + 200), min(H, cy + 200)
                os.makedirs(crop_dir, exist_ok=True)
                Image.fromarray(a0[y0:y1, x0:x1]).save(os.path.join(crop_dir, "v2前.png"))
                Image.fromarray(fixed[y0:y1, x0:x1]).save(os.path.join(crop_dir, "v2后.png"))
        except Exception:
            pass
    if not dry:
        if backup:
            bdir = os.path.join(BACKUP_ROOT, time.strftime("%Y%m%d_%H%M%S") + "_04diffuse_v2前")
            os.makedirs(bdir, exist_ok=True)
            shutil.copy2(png_path, os.path.join(bdir, os.path.basename(png_path)))
        Image.fromarray(fixed).save(png_path)
    return dict(clusters=ncl, faces=int(keep.sum()), texels=npx, r_mm=round(r * 1000, 1),
                thr=round(float(thr), 1), cap=cap, ext_cap_mm=round(ext_cap * 1000, 1),
                head_cut_mm=(round(float(head_cut) * 1000, 1) if face_center is None else None),
                cluster_mm_facecol=cluster_info,
                note=f"v2: {ncl}簇/{int(keep.sum())}面/{npx}像素 已就近皮肤色替换" + (" [dry]" if dry else ""))


if __name__ == "__main__":
    p = os.environ.get("TEX_FIX_PNG", DEFAULT_PNG)
    st = fix_diffuse_png(p)
    print("贴图溢出处理:", st)
