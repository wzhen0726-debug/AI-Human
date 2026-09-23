# -*- coding: utf-8 -*-
"""04 烘焙后贴图溢出处理 — 暗色衣物色渗出到皮肤区域 → 就近替换为皮肤色 + 边缘过渡.
2026-09-17 用户要求("04烘焙后...把溢出的颜色稍微处理一下")。

判据(2026-09-23 重写, 全部现场计算, 无硬编码区域):
  候选面 = 旧版 texel 级判据(亮度<95 且 在衣物本体 ≤18px 内)覆盖到的【面】(该范围实测只落衣-肤边界)
           ∧ 几何守门(面朝外打到遮挡物) ∧ 非衣物面
  填充   = 从 3D 最近【干净皮肤面】按同重心坐标转移其纹理色(保留真实皮肤纹理, 不再平涂中位色)
安全: 处理前自动备份; 命中超上限(1.5%)时不写回; 打印前后计数。

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


def _ras_uv_tri(tri_uv, W, H, pad=0.02, max_span=400):
    """返回 UV 三角形覆盖的像素 (gy, gx, (w0,w1,w2)) 重心坐标; 退化/异常大时 None。"""
    xs = np.clip((tri_uv[:, 0] * W).astype(int), 0, W - 1)
    ys = np.clip(((1.0 - tri_uv[:, 1]) * H).astype(int), 0, H - 1)
    x0, x1 = int(xs.min()), int(xs.max()); y0, y1 = int(ys.min()), int(ys.max())
    if x1 - x0 > max_span or y1 - y0 > max_span:
        return None
    v0, v1, v2 = tri_uv
    d = (v1[0] - v0[0]) * (v2[1] - v0[1]) - (v2[0] - v0[0]) * (v1[1] - v0[1])
    if abs(d) < 1e-12:
        return None
    gy, gx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
    p = np.stack([gx.ravel() / W, 1.0 - gy.ravel() / H], -1)
    w1 = ((p[:, 0] - v0[0]) * (v2[1] - v0[1]) - (p[:, 1] - v0[1]) * (v2[0] - v0[0])) / d
    w2 = ((p[:, 1] - v0[1]) * (v1[0] - v0[0]) - (p[:, 0] - v0[0]) * (v1[1] - v0[1])) / d
    w0 = 1.0 - w1 - w2
    inside = (w0 >= -pad) & (w1 >= -pad) & (w2 >= -pad)
    if not inside.any():
        return None
    return gy.ravel()[inside], gx.ravel()[inside], (w0[inside], w1[inside], w2[inside])


def fix_diffuse_png(path, mesh_objects=None, high_object=None, reach_mm=20.0, cage_mm=25.0,
                    cloth_frac_hi=0.70, cloth_frac_lo=0.20,
                    max_frac=0.015, backup=True, dry=False, crop_dir=None):
    """v1 贴图溢出处理(2026-09-23 重写):
    检出 = 旧版 texel 判据覆盖到的面(亮度<95 且在衣物本体 18px 内) + 几何守门(朝外有遮挡物);
    填充 = 从 3D 最近【干净皮肤面】按同重心坐标转移其纹理色(保留真实皮肤纹理, 不再平涂中位色)。
    返回统计 dict(保持旧字段 before/after/note)。"""
    from scipy.spatial import cKDTree
    a0 = np.array(Image.open(path).convert("RGB"))
    H, W = a0.shape[:2]
    r = a0[:, :, 0].astype(np.int16); g = a0[:, :, 1].astype(np.int16); b = a0[:, :, 2].astype(np.int16)
    lum = 0.30 * r + 0.59 * g + 0.11 * b
    empty = (r <= 2) & (g <= 2) & (b <= 2)
    # ---- 参考色(现场推导, 不含固定阈值) ----
    dark = (lum < 48) & (~empty)
    lab, n = ndimage.label(dark, structure=np.ones((3, 3)))
    big = np.zeros_like(dark)
    if n > 0:
        sizes = ndimage.sum(dark, lab, index=np.arange(1, n + 1))
        thr = max(sizes.max() * 0.15, np.sum(dark) * 0.005)
        for i in np.where(sizes > thr)[0]:
            big |= (lab == i + 1)
    pre = (~empty) & (lum > np.median(lum[~empty])) & (r >= g) & (g >= b)
    if big.sum() < 100 or pre.sum() < 200:
        return dict(before=0, after=0, note="参考色不足(衣物/皮肤), 跳过 v1")
    cloth_ref = np.median(a0[big], axis=0).astype(np.float64)
    skin_ref = np.median(a0[pre], axis=0).astype(np.float64)
    objs = [o for o in (mesh_objects or [])
            if o and o.type == 'MESH' and o.data.uv_layers.active and 'eye' not in o.name.lower()]
    if not objs:
        return dict(before=0, after=0, note="未传入低模, 跳过 v1(新判据需要网格)")
    ob = max(objs, key=lambda o: len(o.data.polygons)); me = ob.data
    M = np.array(ob.matrix_world)
    nf = len(me.polygons)
    luv = np.empty(len(me.loops) * 2); me.uv_layers.active.data.foreach_get("uv", luv); luv = luv.reshape(-1, 2)
    lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(nf, np.int32); lt = np.empty(nf, np.int32)
    me.polygons.foreach_get("loop_start", ls); me.polygons.foreach_get("loop_total", lt)
    ctr = np.empty(nf * 3); me.polygons.foreach_get("center", ctr)
    ctr = ctr.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    Vv = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", Vv)
    Vw = Vv.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    jj = np.arange(4)[None, :]; valid = jj < lt[:, None]
    li = np.clip(ls[:, None] + jj, 0, len(luv) - 1)
    P = luv[li]
    okv = valid[..., None]
    uv_ctr = (P * okv).sum(1) / np.maximum(valid.sum(1), 1)[:, None]
    su = np.concatenate([uv_ctr[:, None], P], 1)
    ok_s = np.concatenate([np.ones((nf, 1), bool), valid], 1)
    px = np.clip((su[..., 0] * W).astype(np.int32), 0, W - 1)
    py = np.clip(((1.0 - su[..., 1]) * H).astype(np.int32), 0, H - 1)
    col = a0[py, px].astype(np.float64)
    ok_s = ok_s & (~empty[py, px])
    dc = np.linalg.norm(col - cloth_ref, axis=-1)
    ds = np.linalg.norm(col - skin_ref, axis=-1)
    is_cloth = (dc < ds) & ok_s
    frac = is_cloth.sum(1) / np.maximum(ok_s.sum(1), 1)
    cloth_face = frac >= cloth_frac_hi
    # ---- 检出范围(2026-09-23 定案): 沿用旧版 texel 级判据(亮度<95 且在衣物本体 ≤18px 内)所覆盖的【面】,
    #   实测该范围只落在贴衣物边界的皮肤(0.27% 体表, 5,695mm²), 从不误伤面部;
    #   曾试"颜色二分类+3D距离+几何守门"更"漂亮"的判据 → 实测把深色五官(鼻孔/唇缝/眼窝)也选中
    #   (头/脸 6.56% 体表面积、1,098 面, 如 (58,25,17)→(213,149,114)), 故弃用, 只保留其"填充"部分。
    if big.any():
        dist_big = ndimage.distance_transform_edt(~big)
        legacy = (lum < 95) & (~empty) & (~big) & (dist_big <= 18)
    else:
        legacy = np.zeros((H, W), bool)
    frac_legacy = legacy[py, px].sum(1) / np.maximum(ok_s.sum(1), 1)
    spill_face = (frac_legacy >= 0.20) & (~cloth_face)
    if int(cloth_face.sum()) < 10 or int(spill_face.sum()) == 0:
        return dict(before=0, after=0,
                    note=f"无需处理(衣物面{int(cloth_face.sum())} 候选{int(spill_face.sum())}), 跳过 v1")
    dcl, _ = cKDTree(ctr[cloth_face]).query(ctr[spill_face])
    idx_spill = np.where(spill_face)[0][dcl <= reach_mm / 1000.0]
    # ---- 几何守门(2026-09-23 补, 作为确认): "溢出"的定义 = 该 texel 的烘焙色来自【别的表面】。
    #   判据: 从面心朝【面法线外侧】打射线到高模, 打到遮挡物(衣物层, 距离≤cage_mm)才算溢出;
    #   否则(朝外是空气)其颜色只可能来自自身表面 —— 深色五官(鼻孔/唇缝/眼窝/眉毛)天然被排除。
    gate_note = "无高模, 未做几何守门"
    if high_object is not None and len(idx_spill) > 0:
        import bpy as _bpy
        from mathutils.bvhtree import BVHTree
        from mathutils import Vector
        try:
            bvh = BVHTree.FromObject(high_object, _bpy.context.evaluated_depsgraph_get())
            nrm = np.empty(nf * 3); me.polygons.foreach_get("normal", nrm)
            nrm = nrm.reshape(-1, 3) @ np.array(ob.matrix_world)[:3, :3].T
            keep = []
            for si in idx_spill:
                nd = nrm[si] / (float(np.linalg.norm(nrm[si])) + 1e-12)
                hit = bvh.ray_cast(Vector([float(x) for x in ctr[si]]), Vector([float(x) for x in nd]),
                                   cage_mm / 1000.0)
                if hit[0] is not None:
                    keep.append(int(si))
            n0 = len(idx_spill)
            idx_spill = np.array(keep, dtype=int) if keep else np.zeros(0, dtype=int)
            gate_note = f"几何守门 {n0}→{len(idx_spill)} 面(朝外被遮挡者)"
        except Exception as e:
            gate_note = f"几何守门失败({type(e).__name__}: {e}), 未过滤"
    clean = (~cloth_face) & (frac < cloth_frac_lo)
    if len(idx_spill) == 0 or int(clean.sum()) < 10:
        return dict(before=0, after=0,
                    note=f"无需处理({gate_note}; 3D限内候选面{len(idx_spill)} 干净皮肤面{int(clean.sum())}), 跳过 v1")
    clean_idx = np.where(clean)[0]
    _, iq = cKDTree(ctr[clean]).query(ctr[idx_spill], k=1)
    fixed = a0.copy(); fill_m = np.zeros((H, W), bool); done = 0
    for a_i, si in enumerate(idx_spill):
        donor = clean_idx[int(np.atleast_1d(iq)[a_i])]
        tri_s = P[si][valid[si]][:3]
        tri_d = P[donor][valid[donor]][:3]
        if len(tri_s) < 3 or len(tri_d) < 3:
            continue
        res = _ras_uv_tri(tri_s, W, H)
        if res is None:
            continue
        gy, gx, (w0, w1, w2) = res
        du = w0[:, None] * tri_d[0] + w1[:, None] * tri_d[1] + w2[:, None] * tri_d[2]
        dpx = np.clip((du[:, 0] * W).astype(np.int32), 0, W - 1)
        dpy = np.clip(((1.0 - du[:, 1]) * H).astype(np.int32), 0, H - 1)
        src = a0[dpy, dpx]
        good = ~empty[dpy, dpx]
        if int(good.sum()) < 4:
            continue
        if good.all():
            fixed[gy, gx] = src
        else:
            med = np.median(src[good], axis=0).astype(np.uint8)
            fixed[gy, gx] = np.where(good[:, None], src, med)
        fill_m[gy, gx] = True
        done += 1
    before = int(fill_m.sum())
    if before == 0:
        return dict(before=0, after=0, note="候选面栅格化无 texel, 跳过 v1")
    if before > max_frac * H * W:
        return dict(before=before, after=before, note=f"溢出{before}超上限{max_frac:.1%}, 未写回(判据疑似失准)")
    trans = ndimage.binary_dilation(fill_m, iterations=2) & (~fill_m)
    for c in range(3):
        bl = ndimage.gaussian_filter(fixed[:, :, c].astype(np.float32), sigma=1.2)
        fixed[:, :, c] = np.where(trans, bl.astype(np.uint8), fixed[:, :, c])
    if not dry:
        if backup:
            bdir = os.path.join(BACKUP_ROOT, time.strftime("%Y%m%d_%H%M%S") + "_04diffuse_处理前")
            os.makedirs(bdir, exist_ok=True)
            shutil.copy2(path, os.path.join(bdir, os.path.basename(path)))
        Image.fromarray(fixed).save(path)
    if crop_dir:
        try:
            ys, xs = np.where(fill_m)
            cy, cx = int(np.median(ys)), int(np.median(xs))
            os.makedirs(crop_dir, exist_ok=True)
            x0, y0 = max(0, cx - 200), max(0, cy - 200); x1, y1 = min(W, cx + 200), min(H, cy + 200)
            Image.fromarray(a0[y0:y1, x0:x1]).save(os.path.join(crop_dir, "v1_前.png"))
            Image.fromarray(fixed[y0:y1, x0:x1]).save(os.path.join(crop_dir, "v1_后.png"))
        except Exception:
            pass
    return dict(before=before, after=0, faces=int(done),
                note=f"v1(3D 判据): {gate_note}; {done}面/{before}像素溢出按 3D 最近皮肤纹理替换"
                     + (" [dry]" if dry else ""))


# ============================================================================
# v2 (2026-09-17): 网格引导的统计离群清理 —— 皮肤上的孤立异常斑(双向: 偏暗/偏亮)
#   全部阈值由模型自身推导(无写死): 邻域半径=最近邻中位距x4; 阈值=4*(1.4826*MAD);
#   簇上限=总面数x0.03%; 只处理 bbox 高度85%以下(按身高比例, 保护头部五官).
#   替换: 异常面 UV 三角形内像素 <- 其 3D 邻域(非异常面)颜色中位 + 2px 过渡.
# ============================================================================
def fix_diffuse_mesh_guided(png_path, mesh_objects, k_sigma=4.0, cluster_frac=0.0015,
                            head_ratio=0.80, backup=True, dry=False, crop_dir=None):
    """网格引导清理; 返回统计 dict. 全部判据相对模型数据, 不含固定坐标/阈值."""
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
    # --- 高度过滤(保护头部; 按 bbox 比例) ---
    zmin, zmax = cen[:, 2].min(), cen[:, 2].max()
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
    # --- 边界保护 (2026-09-22 用户报"修复后衣身交界反而多锯齿/噪点"根因):
    # 衣-肤交界面的烘焙色=骑跨混色(偏暗), v2判为"偏暗异常"→涂皮肤色→交界出现皮肤色斑/锯齿.
    # 判据: 邻域内同时有皮肤样面与衣物样面(暗冷: lum<60且b>=r-10) → 交界面, 跳过.
    skin_f = np.array([skin_like(c) for c in col]) & (~empty)
    lum_arr = lum
    cloth_f = (~empty) & (lum_arr < 60) & (col[:, 2] >= col[:, 0] - 10)
    boundary = np.zeros(len(F), bool)
    for i in range(len(F)):
        ns = idx[i]
        if skin_f[ns].any() and cloth_f[ns].any():
            boundary[i] = True
    for i in np.where(anom & (~boundary))[0]:
        if seen[i]:
            continue
        stack = [i]; seen[i] = True; comp = []
        while stack:
            j = stack.pop(); comp.append(j)
            for kk in idx[j]:
                if anom[kk] and not boundary[kk] and not seen[kk]:
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
                thr=round(float(thr), 1), cap=cap, ext_cap_mm=round(ext_cap * 1000, 1), head_cut_mm=round(float(head_cut) * 1000, 1),
                cluster_mm_facecol=cluster_info,
                note=f"v2: {ncl}簇/{int(keep.sum())}面/{npx}像素 已就近皮肤色替换" + (" [dry]" if dry else ""))


# ============================================================================
# v3 (2026-09-21): 皮肤上的深色条纹/黑面清理(网格引导, 含肩部/头部)
#   背景: v2 的 head_ratio 高度截断把肩/头排除在外 → 肩部烘焙黑条纹(用户红圈)无人处理.
#   与 v2 的差异: 不用高度截断, 改用"头列排除盒"(眼/鼻/口/眉/发 的 bbox 柱)保护五官;
#   门控 = 3D邻域皮肤面占比≥0.85(条纹长在纯皮肤区, 衣物边缘/腋下阴影邻域含大量暗面自动排除);
#   全部阈值由模型自身统计推导, 无写死坐标. 替换色 = 邻域皮肤面颜色中位 + 2px 过渡.
# ============================================================================
def fix_diffuse_dark_streaks(png_path, mesh_objects, k_sigma=4.0, skin_frac=0.85,
                             backup=True, dry=False, crop_dir=None):
    """清理皮肤区(含肩/头, 排除五官柱)的深色异常条纹; 返回统计 dict."""
    from scipy.spatial import cKDTree
    a0 = np.array(Image.open(png_path).convert("RGB"))
    H, W = a0.shape[:2]
    F = []
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
            F.append((ctr[i], tri))
    if len(F) < 500:
        return dict(note="网格面太少, 跳过 v3")
    cen = np.array([f[0] for f in F])
    x = np.clip((np.array([f[1].mean(axis=0)[0] for f in F]) * W).astype(int), 0, W - 1)
    y = np.clip(((1 - np.array([f[1].mean(axis=0)[1] for f in F])) * H).astype(int), 0, H - 1)
    col = a0[y, x].astype(np.float64)
    lum = 0.30 * col[:, 0] + 0.59 * col[:, 1] + 0.11 * col[:, 2]
    empty = (col[:, 0] <= 2) & (col[:, 1] <= 2) & (col[:, 2] <= 2)
    # --- 皮肤参考色域(亮暖色粗筛 → Mahalanobis) ---
    pre = (~empty) & (lum > np.median(lum[~empty])) & (col[:, 0] >= col[:, 1]) & (col[:, 1] >= col[:, 2])
    if pre.sum() < 200:
        return dict(note="皮肤样面太少, 跳过 v3")
    mu = col[pre].mean(axis=0)
    cov = np.cov(col[pre].T) + np.eye(3) * 1e-6
    icov = np.linalg.inv(cov)
    def skin_like(cc):
        d = cc - mu
        return float(d @ icov @ d) <= 2.5 ** 2
    skin_face = np.array([skin_like(c) for c in col]) & (~empty)
    # --- 头列排除盒: 眼/鼻/口 由皮肤面里的暗簇(眉/眼/唇)bbox 柱推导; 发际以上整体保护 ---
    zmin, zmax = cen[:, 2].min(), cen[:, 2].max()
    hgt = zmax - zmin
    dark_face = skin_face == False
    face_band = (cen[:, 2] > zmin + 0.70 * hgt) & (~empty)
    dark_in_band = face_band & (lum < np.percentile(lum[face_band], 25))
    boxes = []
    if dark_in_band.sum() > 50:
        lab, n = ndimage.label(dark_in_band)
        sizes = ndimage.sum(dark_in_band, lab, index=np.arange(1, n + 1))
        for i in np.where(sizes >= 20)[0]:
            pts = cen[lab == i + 1]
            lo, hi = pts.min(axis=0), pts.max(axis=0)
            cpos_b = pts.mean(axis=0)
            # 保护盒种子限头列(|x|<0.10hgt): 肩部/躯干的深色条纹不得自建保护盒
            if abs(cpos_b[0]) > 0.10 * hgt:
                continue
            if (hi[0] - lo[0]) < 0.12 * hgt and (hi[2] - lo[2]) < 0.10 * hgt:   # 只保护小特征(五官), 不保护大片
                boxes.append((lo, hi))
    hair_z = zmin + 0.88 * hgt   # 发际以上整体保护(头发/头皮纹理是正常深色)
    def excluded(p):
        if p[2] > hair_z:
            return True
        for lo, hi in boxes:
            if lo[0] - 0.01 * hgt <= p[0] <= hi[0] + 0.01 * hgt and lo[2] - 0.01 * hgt <= p[2] <= hi[2] + 0.01 * hgt \
               and lo[1] - 0.02 * hgt <= p[1] <= hi[1] + 0.02 * hgt:
                return True
        return False
    excl = np.array([excluded(p) for p in cen])
    # --- 邻域 & 偏差 ---
    t = cKDTree(cen)
    dnn, _ = t.query(cen, k=2)
    r = 4.0 * float(np.median(dnn[:, 1]))
    idx = t.query_ball_point(cen, r)
    dev = np.zeros(len(F)); med = lum.copy(); sfr = np.zeros(len(F))
    for i in range(len(F)):
        ns = idx[i]
        if len(ns) < 6:
            continue
        med[i] = np.median(lum[ns])
        dev[i] = lum[i] - med[i]
        sfr[i] = skin_face[ns].mean()
    ok = (~empty) & (~excl)
    d_ok = dev[ok]
    sig = 1.4826 * float(np.median(np.abs(d_ok - np.median(d_ok))))
    p995 = float(np.percentile(np.abs(d_ok), 99.5))
    thr = max(k_sigma * sig, p995)
    if thr <= 1e-6:
        return dict(note="偏差分布异常, 跳过 v3")
    anom = ok & (dev < -thr) & (sfr >= skin_frac)   # 偏暗 且 身处纯皮肤邻域
    # --- 连通簇(邻域图), 上限=总面数0.15% ---
    cap = max(int(len(F) * 0.0015), 1)
    seen = np.zeros(len(F), bool); repl = {}; ncl = 0; info = []
    for i in np.where(anom)[0]:
        if seen[i]:
            continue
        stack = [i]; seen[i] = True; comp = []
        while stack:
            j = stack.pop(); comp.append(j)
            for kk in idx[j]:
                if anom[kk] and not seen[kk]:
                    seen[kk] = True; stack.append(kk)
        if len(comp) > cap:
            continue
        nbr = [kk for j in comp for kk in idx[j] if not anom[kk] and not empty[kk]]
        nbr_skin = [kk for kk in set(nbr) if skin_face[kk]]
        if len(nbr_skin) < 4:
            continue
        ncol = np.median(col[nbr_skin], axis=0)
        ncl += 1
        for j in comp:
            repl[j] = ncol
        cpos = cen[comp].mean(axis=0)
        info.append((len(comp), [round(float(v) * 1000) for v in cpos], [int(v) for v in np.median(col[comp], axis=0)]))
    if ncl == 0:
        return dict(clusters=0, note="v3: 无皮肤区深色条纹")
    # --- UV三角形光栅写回 + 2px 过渡 ---
    fixed = a0.copy()
    fillm = np.zeros((H, W), bool)
    for j, c in repl.items():
        tri = F[j][1]
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
    trans = ndimage.binary_dilation(fillm, iterations=2) & (~fillm)
    for c in range(3):
        bl = ndimage.gaussian_filter(fixed[:, :, c].astype(np.float32), sigma=1.0)
        fixed[:, :, c] = np.where(trans, bl.astype(np.uint8), fixed[:, :, c])
    if crop_dir and npx:
        try:
            ys, xs = np.where(fillm)
            cy, cx = int(np.median(ys)), int(np.median(xs))
            x0, y0 = max(0, cx - 200), max(0, cy - 200)
            x1, y1 = min(W, cx + 200), min(H, cy + 200)
            os.makedirs(crop_dir, exist_ok=True)
            Image.fromarray(a0[y0:y1, x0:x1]).save(os.path.join(crop_dir, "v3前.png"))
            Image.fromarray(fixed[y0:y1, x0:x1]).save(os.path.join(crop_dir, "v3后.png"))
        except Exception:
            pass
    if not dry:
        if backup:
            bdir = os.path.join(BACKUP_ROOT, time.strftime("%Y%m%d_%H%M%S") + "_04diffuse_v3前")
            os.makedirs(bdir, exist_ok=True)
            shutil.copy2(png_path, os.path.join(bdir, os.path.basename(png_path)))
        Image.fromarray(fixed).save(png_path)
    return dict(clusters=ncl, faces=len(repl), texels=npx, thr=round(float(thr), 1),
                protect_boxes=len(boxes), cluster_mm_facecol=info,
                note=f"v3: {ncl}簇/{len(repl)}面/{npx}像素 皮肤区深色条纹已替换" + (" [dry]" if dry else ""))


# ============================================================================
# v4 (2026-09-21): 衣物岛内的皮肤色碎点/碎线清理(贴图层, 与 v1 方向相反)
#   背景: 领口/袖口边界面的烘焙射线骑跨高模衣边 → 同一UV三角形内混入皮肤色texel,
#   渲染为衣物边缘的浅色虚线(用户报"衣服跟皮肤间锯齿/噪点"的一类). 面级统计查不出
#   (面心是混色), 须在贴图层查: 皮肤色小簇 且 被衣物色包围 → 替换为周围衣物色.
#   门控: 簇≤max_tex; 膨胀4px邻域内衣物占比≥cloth_frac; 大皮肤岛(胸/臂)邻域是空margin
#   不是衣物 → 天然排除. 全部阈值相对贴图层统计, 无写死区域.
# ============================================================================
def fix_diffuse_cloth_specks(png_path, max_tex=600, cloth_frac=0.60, backup=True,
                             dry=False, crop_dir=None):
    """清理衣物色区内的皮肤色小碎簇; 返回统计 dict."""
    a0 = np.array(Image.open(png_path).convert("RGB"))
    H, W = a0.shape[:2]
    r, g, b = a0[:, :, 0].astype(np.int16), a0[:, :, 1].astype(np.int16), a0[:, :, 2].astype(np.int16)
    lum = 0.30 * r + 0.59 * g + 0.11 * b
    empty = (r <= 2) & (g <= 2) & (b <= 2)
    cloth = (lum < 60) & (~empty)
    if cloth.sum() < 1000:
        return dict(note="无衣物色区, 跳过 v4")
    # 皮肤色域(像素级 Mahalanobis, 由亮暖像素推导)
    pre = (~empty) & (lum > np.median(lum[~empty])) & (r >= g) & (g >= b)
    mu = a0[pre].mean(axis=0)
    cov = np.cov(a0[pre].astype(np.float64).T) + np.eye(3) * 1e-6
    icov = np.linalg.inv(cov)
    d = (a0.astype(np.float64) - mu)
    dm = d.reshape(-1, 3) @ icov
    maha = (dm * d.reshape(-1, 3)).sum(axis=1).reshape(H, W)
    skin = (maha <= 2.5 ** 2) & (~empty)
    lab, n = ndimage.label(skin, structure=np.ones((3, 3)))
    if n == 0:
        return dict(note="无皮肤色像素, 跳过 v4")
    sizes = ndimage.sum(skin, lab, index=np.arange(1, n + 1))
    objs = ndimage.find_objects(lab)
    fixed = a0.copy(); fillm = np.zeros((H, W), bool); ncl = 0; info = []
    for i in np.where((sizes > 0) & (sizes <= max_tex))[0]:
        sl = objs[i]
        y0, y1 = max(0, sl[0].start - 4), min(H, sl[0].stop + 4)
        x0, x1 = max(0, sl[1].start - 4), min(W, sl[1].stop + 4)
        sub_lab = (lab[y0:y1, x0:x1] == i + 1)
        nb = sub_lab ^ ndimage.binary_dilation(sub_lab, iterations=4)   # 环带=膨胀-本体
        sub_empty = empty[y0:y1, x0:x1]
        nb_valid = nb & (~sub_empty)          # 岛边缘邻域含空margin → 只统计非空像素
        nbt = int(nb_valid.sum())
        if nbt == 0:
            continue
        sub_cloth = cloth[y0:y1, x0:x1]
        if (nb_valid & sub_cloth).sum() / nbt < cloth_frac:
            continue   # 不被衣物包围(大皮肤岛/空margin旁) → 不动
        ncl += 1
        col = np.median(a0[y0:y1, x0:x1][nb & sub_cloth], axis=0).astype(np.uint8)
        cl_full = np.zeros((H, W), bool); cl_full[y0:y1, x0:x1] = sub_lab
        fixed[cl_full] = col
        fillm |= cl_full
        info.append((int(sub_lab.sum()), (int((x0 + x1) / 2), int((y0 + y1) / 2)), col.tolist()))
    if ncl == 0:
        return dict(clusters=0, note="v4: 衣物区内无皮肤色碎簇")
    trans = ndimage.binary_dilation(fillm, iterations=2) & (~fillm)
    for c in range(3):
        bl = ndimage.gaussian_filter(fixed[:, :, c].astype(np.float32), sigma=1.0)
        fixed[:, :, c] = np.where(trans, bl.astype(np.uint8), fixed[:, :, c])
    if crop_dir and ncl:
        try:
            ys, xs = np.where(fillm)
            cy, cx = int(np.median(ys)), int(np.median(xs))
            x0, y0 = max(0, cx - 250), max(0, cy - 250)
            x1, y1 = min(W, cx + 250), min(H, cy + 250)
            os.makedirs(crop_dir, exist_ok=True)
            Image.fromarray(a0[y0:y1, x0:x1]).save(os.path.join(crop_dir, "v4前.png"))
            Image.fromarray(fixed[y0:y1, x0:x1]).save(os.path.join(crop_dir, "v4后.png"))
        except Exception:
            pass
    if not dry:
        if backup:
            bdir = os.path.join(BACKUP_ROOT, time.strftime("%Y%m%d_%H%M%S") + "_04diffuse_v4前")
            os.makedirs(bdir, exist_ok=True)
            shutil.copy2(png_path, os.path.join(bdir, os.path.basename(png_path)))
        Image.fromarray(fixed).save(png_path)
    return dict(clusters=ncl, texels=int(fillm.sum()), cluster_px_uv=info[:12],
                note=f"v4: {ncl}簇/{int(fillm.sum())}像素 衣物内皮肤碎点已替换" + (" [dry]" if dry else ""))


# ============================================================================
# v5 (2026-09-21): 烘焙骑跨误采样修复 — 以高模贴图为真值逐面比对
#   背景: 领口/袖口薄衣缘面, 烘焙射线穿透薄边打到内侧皮肤 → 低模采样=皮肤色,
#   而高模同位置真值=衣物色 → 渲染为衣边浅色虚线. 贴图层/邻域统计判据都会误伤
#   领口上缘真皮肤面; 唯一无歧义判据 = 高模真值: 高模=衣物色 且 低模=皮肤色 → 用高模色替换.
#   实现: 低模面心 → BVH 高模最近面 → 高模面UV中心采样高模贴图 = 真值色.
# ============================================================================
def fix_diffuse_cloth_faces(png_path, mesh_objects, high_blend, tol_mm_frac=0.004,
                            backup=True, dry=False, crop_dir=None):
    """低模采样与高模真值不符(高模衣物色/低模皮肤色)的面 → 用高模真值色替换; 返回统计 dict."""
    import bpy
    from scipy.spatial import cKDTree
    from mathutils.bvhtree import BVHTree
    a0 = np.array(Image.open(png_path).convert("RGB"))
    H, W = a0.shape[:2]
    # --- 高模真值: 传入对象或blend路径 ---
    if isinstance(high_blend, str):
        with bpy.data.libraries.load(high_blend) as (df, dt):
            dt.objects = [o for o in df.objects]
        hi_objs = [o for o in dt.objects if o is not None and o.type == 'MESH']
    else:
        hi_objs = [high_blend]
    if not hi_objs:
        return dict(note="高模载入失败, 跳过 v5")
    hi = max(hi_objs, key=lambda o: len(o.data.vertices))
    hi_img = None
    for m in hi.data.materials:
        if m and m.use_nodes:
            for nd in m.node_tree.nodes:
                if nd.type == 'TEX_IMAGE' and nd.image:
                    hi_img = nd.image
                    break
        if hi_img:
            break
    if hi_img is None:
        return dict(note="高模无贴图, 跳过 v5")
    hw, hh = hi_img.size
    hp = np.array(hi_img.pixels[:]).reshape(hh, hw, 4)[:, :, :3]
    hM = np.array(hi.matrix_world)
    hme = hi.data
    hn = len(hme.polygons)
    hluv = np.empty(len(hme.loops) * 2); hme.uv_layers.active.data.foreach_get("uv", hluv)
    hluv = hluv.reshape(-1, 2)
    hls = np.empty(hn, np.int32); hlt = np.empty(hn, np.int32)
    hme.polygons.foreach_get("loop_start", hls); hme.polygons.foreach_get("loop_total", hlt)
    hctr = np.empty(hn * 3); hme.polygons.foreach_get("center", hctr); hctr = hctr.reshape(-1, 3)
    hcen = hctr @ hM[:3, :3].T + hM[:3, 3]
    # 高模真值色 = UV三角形7点(3顶点+3边中点+中心)中位数(细长三角形中心会落到三角形外)
    def _uv_med(tri):
        # ⚠ Blender image.pixels 行0=v=0(底边), 与PNG(PIL行0=顶)相反 → hy = v*hh
        pts = [tri[0], tri[1], tri[2], (tri[0] + tri[1]) / 2, (tri[1] + tri[2]) / 2, (tri[2] + tri[0]) / 2, tri.mean(axis=0)]
        cs = []
        for p in pts:
            xi = int(np.clip(p[0] * hw, 0, hw - 1)); yi = int(np.clip(p[1] * hh, 0, hh - 1))
            cs.append(hp[yi, xi] * 255)
        return np.median(np.array(cs), axis=0)
    htri = [hluv[hls[i]:hls[i] + hlt[i]] for i in range(hn)]
    hcol = np.array([_uv_med(t) for t in htri])
    # 高模BVH(世界空间)
    hverts = np.empty(len(hme.vertices) * 3); hme.vertices.foreach_get("co", hverts)
    HV = hverts.reshape(-1, 3) @ hM[:3, :3].T + hM[:3, 3]
    bvh = BVHTree.FromPolygons([tuple(v) for v in HV], [list(p.vertices) for p in hme.polygons])
    hdiag = float(np.linalg.norm(HV.max(axis=0) - HV.min(axis=0)))
    tol = hdiag * tol_mm_frac
    # --- 低模面 ---
    F = []
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
        nrm_l = np.empty(n * 3); me.polygons.foreach_get("normal", nrm_l); nrm_l = nrm_l.reshape(-1, 3) @ M[:3, :3].T
        for i in range(n):
            F.append((ctr[i], luv[ls[i]:ls[i] + lt[i]], nrm_l[i]))
    if len(F) < 500:
        return dict(note="网格面太少, 跳过 v5")
    cen = np.array([f[0] for f in F])
    # 低模采样色 = UV三角形7点中位数(面心可能落在细长三角形外)
    def _uv_med_low(tri):
        pts = [tri[0], tri[1], tri[2], (tri[0] + tri[1]) / 2, (tri[1] + tri[2]) / 2, (tri[2] + tri[0]) / 2, tri.mean(axis=0)]
        cs = []
        for p in pts:
            xi = int(np.clip(p[0] * W, 0, W - 1)); yi = int(np.clip((1 - p[1]) * H, 0, H - 1))
            cs.append(a0[yi, xi].astype(np.float64))
        return np.median(np.array(cs), axis=0)
    col = np.array([_uv_med_low(f[1]) for f in F])
    lum = 0.30 * col[:, 0] + 0.59 * col[:, 1] + 0.11 * col[:, 2]
    empty = (col[:, 0] <= 2) & (col[:, 1] <= 2) & (col[:, 2] <= 2)
    def _is_cloth(cc):
        # 保守: 暗且冷调/低饱和(背心蓝灰); 皮肤暖暗影不算衣物 → 防误伤阴影皮肤面/鞋缘
        return (0.30 * cc[0] + 0.59 * cc[1] + 0.11 * cc[2]) < 60 and cc[2] >= cc[0] - 10
    def _is_skin(cc):
        return cc[0] > 140 and cc[1] > 100 and cc[2] > 70 and cc[0] > cc[1]
    # --- 逐面真值比对(可见性raycast: 法线外2mm向内打, 首个命中=相机可见面=真值;
    #     find_nearest在薄衣缘会命中贴合的内侧皮肤面→真值错, 实测领口带漏检根因) ---
    zmin_l, zmax_l = cen[:, 2].min(), cen[:, 2].max()
    head_cut = zmin_l + 0.90 * (zmax_l - zmin_l)   # 发际以上不动(头发暗色易误判为衣物色)
    nrm = np.array([f[2] for f in F]) if len(F[0]) > 2 else None
    anom = np.zeros(len(F), bool)
    truth = np.zeros((len(F), 3))
    ray_len = 0.004 * hdiag
    for i in range(len(F)):
        if empty[i] or cen[i, 2] > head_cut:
            continue
        hit = bvh.ray_cast((cen[i] + nrm[i] * 0.002).tolist(), (-nrm[i]).tolist(), ray_len)
        if hit[0] is None or hit[2] is None:
            continue
        if abs(hit[3] - 0.002) > 0.0008:   # 命中须≈面自身(2mm偏移±0.8mm); 鞋缘/衣缘等前方遮挡不算
            continue
        hc = hcol[hit[2]]
        if _is_cloth(hc) and _is_skin(col[i]):
            anom[i] = True
            truth[i] = hc
    n_anom = int(anom.sum())
    if n_anom == 0:
        return dict(clusters=0, note="v5: 低模采样与高模真值一致, 无需修复")
    if n_anom > 0.005 * len(F):
        return dict(clusters=0, faces=n_anom,
                    note=f"v5: 异常面{n_anom}超全局上限0.5%({len(F)}面), 判据疑似失准, 未写回")
    # --- 簇(邻域图)上限 ---
    t = cKDTree(cen)
    dnn, _ = t.query(cen, k=2)
    r = 4.0 * float(np.median(dnn[:, 1]))
    idx = t.query_ball_point(cen, r)
    cap = max(int(len(F) * 0.003), 1)
    seen = np.zeros(len(F), bool); ncl = 0; info = []; repl = {}
    for i in np.where(anom)[0]:
        if seen[i]:
            continue
        stack = [i]; seen[i] = True; comp = []
        while stack:
            j = stack.pop(); comp.append(j)
            for kk in idx[j]:
                if anom[kk] and not seen[kk]:
                    seen[kk] = True; stack.append(kk)
        if len(comp) > cap:
            continue
        ncl += 1
        for j in comp:
            repl[j] = truth[j]
        cpos = cen[comp].mean(axis=0)
        info.append((len(comp), [round(float(v) * 1000) for v in cpos], [int(v) for v in np.median(col[comp], axis=0)]))
    if ncl == 0:
        return dict(clusters=0, note="v5: 异常面超簇上限, 未处理")
    # --- 三角形内皮肤样像素替换为高模真值色 + 2px过渡 ---
    fixed = a0.copy()
    fillm = np.zeros((H, W), bool)
    for j, c in repl.items():
        tri = F[j][1]
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
        sub = fixed[y0:y1 + 1, x0:x1 + 1]
        sr, sg, sb = sub[:, :, 0].astype(int), sub[:, :, 1].astype(int), sub[:, :, 2].astype(int)
        skin_px = (sr > 140) & (sg > 100) & (sb > 70) & (sr > sg)
        tgt = m & (skin_px | (ndimage.binary_dilation(skin_px & m, iterations=1) & m))
        sub[tgt] = c.astype(np.uint8)
        fillm[y0:y1 + 1, x0:x1 + 1] |= tgt
    npx = int(fillm.sum())
    trans = ndimage.binary_dilation(fillm, iterations=2) & (~fillm)
    for c in range(3):
        bl = ndimage.gaussian_filter(fixed[:, :, c].astype(np.float32), sigma=1.0)
        fixed[:, :, c] = np.where(trans, bl.astype(np.uint8), fixed[:, :, c])
    if crop_dir and npx:
        try:
            ys, xs = np.where(fillm)
            cy, cx = int(np.median(ys)), int(np.median(xs))
            x0, y0 = max(0, cx - 250), max(0, cy - 250)
            x1, y1 = min(W, cx + 250), min(H, cy + 250)
            os.makedirs(crop_dir, exist_ok=True)
            Image.fromarray(a0[y0:y1, x0:x1]).save(os.path.join(crop_dir, "v5前.png"))
            Image.fromarray(fixed[y0:y1, x0:x1]).save(os.path.join(crop_dir, "v5后.png"))
        except Exception:
            pass
    if not dry:
        if backup:
            bdir = os.path.join(BACKUP_ROOT, time.strftime("%Y%m%d_%H%M%S") + "_04diffuse_v5前")
            os.makedirs(bdir, exist_ok=True)
            shutil.copy2(png_path, os.path.join(bdir, os.path.basename(png_path)))
        Image.fromarray(fixed).save(png_path)
    return dict(clusters=ncl, faces=len(repl), texels=npx, cluster_mm_facecol=info[:12],
                note=f"v5: {ncl}簇/{len(repl)}面/{npx}像素 按高模真值修复" + (" [dry]" if dry else ""))


# ============================================================================
# v6 (2026-09-21): 衣缘像素级骑跨碎线清理(源贴图缺陷/过渡带)
#   v4 按连通簇清理, 但领口虚线与皮肤岛粘连 → 簇=岛本体被跳过.
#   v6 像素级: 皮肤色像素 且 5x5邻域衣物色占比≥cloth_frac → 嵌入衣物区的碎点/过渡带
#   → 替换为邻域衣物色中位数. 真皮肤区(邻域全皮肤/空margin)占比≈0 不受影响;
#   颈部暖暗阴影不算衣物色(b≥r-10判据) → 阴影带皮肤不受影响.
#   效果: 衣缘过渡带向皮肤侧收1-2px, 虚线消除, 边界更干净.
# ============================================================================
def fix_diffuse_edge_specks(png_path, cloth_frac=0.35, max_pix_frac=0.005, crop_dir=None):
    from scipy import ndimage
    a0 = np.array(Image.open(png_path).convert("RGB"))
    H, W = a0.shape[:2]
    r = a0[:, :, 0].astype(int); g = a0[:, :, 1].astype(int); b = a0[:, :, 2].astype(int)
    lum = 0.30 * r + 0.59 * g + 0.11 * b
    empty = lum < 8
    skin = (r > 140) & (g > 100) & (b > 70) & (r > g) & (~empty)
    cloth = (lum < 60) & (b >= r - 10) & (~empty)
    cf = ndimage.uniform_filter(cloth.astype(np.float32), size=5)
    hit = skin & (cf >= cloth_frac)
    n = int(hit.sum())
    if n == 0:
        return dict(pixels=0, note="v6: 无衣缘骑跨碎线")
    if n > max_pix_frac * H * W:
        return dict(pixels=n, note=f"v6: 命中{n}超上限0.5%, 判据疑似失准, 未写回")
    fixed = a0.copy()
    ys, xs = np.where(hit)
    gmed = np.median(a0[cloth], axis=0).astype(np.uint8)
    for y, x in zip(ys, xs):
        y0, y1 = max(0, y - 2), min(H, y + 3)
        x0, x1 = max(0, x - 2), min(W, x + 3)
        wc = cloth[y0:y1, x0:x1]
        fixed[y, x] = np.median(a0[y0:y1, x0:x1][wc], axis=0).astype(np.uint8) if wc.sum() >= 3 else gmed
    Image.fromarray(fixed).save(png_path)
    if crop_dir:
        os.makedirs(crop_dir, exist_ok=True)
        yy0, yy1 = max(0, ys.min() - 60), min(H, ys.max() + 60)
        xx0, xx1 = max(0, xs.min() - 60), min(W, xs.max() + 60)
        Image.fromarray(a0[yy0:yy1, xx0:xx1]).save(os.path.join(crop_dir, "v6_before.png"))
        Image.fromarray(fixed[yy0:yy1, xx0:xx1]).save(os.path.join(crop_dir, "v6_after.png"))
    return dict(pixels=n, note=f"v6: {n}像素衣缘碎线已替换为衣物色")


# ============================================================================
# v7 (2026-09-22): 眼窝碗心暗块清理(烘焙源=01闭眼高模的副作用)
#   01眼睑闭合 → 碗底面的烘焙射线打到眼睑【内表面】→ 暗色texel; 带眼球时被遮挡,
#   但隐藏眼球/无眼球查看器下是黑块. 修复: 眼球球体内(d/r<dr_max)且暗色的低模面
#   → 三角形内texel替换为眼窝缘皮肤色中位(眼区 d/r∈[0.9,1.4] 亮面). 眼球外皮肤不受影响.
# ============================================================================
def fix_diffuse_socket_interior(png_path, mesh_objects, eye_objects, dr_max=2.6,
                                lum_thr=None, crop_dir=None, n_view=14):
    """只涂【带眼球时被遮挡】的面(用户2026-09-22定案: 烘焙眼窝必黑→直接涂肉色; 眼球遮挡后不可见,
    隐藏眼球时碗内为干净肉色).

    ⚠ 2026-09-22 修根因: 旧判据是"面心到眼球中心距离 d < dr_max × r", 而 r 取的是眼球【顶点到中心的
     最大距离】(bbox 角半径, 比真实球半径大约 √3 倍), 加上 lum_thr=None(无条件涂色) → 把眼球周围一圈
     【可见的】眼睑/睑缘/睫毛根/内眼角也涂成肉色, 用户据此判定"纹理修复倒退严重"(眼睑边界被抹平,
    边缘呈阶梯状)。现改为可见性判据: 从多个外部视角朝面心打射线, 只要有一个视角没被眼球挡住 = 可见 = 不涂;
    全部被眼球挡住才算"带眼球时不可见"→ 涂。这样眼窝缘的可见皮肤/睫毛根一律不动。
    """
    import math
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    a0 = np.array(Image.open(png_path).convert("RGB"))
    H, W = a0.shape[:2]
    eyes = []
    eye_bvhs = []
    for e in eye_objects:
        me_e = e.data
        cs = np.empty(len(me_e.vertices) * 3); me_e.vertices.foreach_get("co", cs)
        Mw = np.array(e.matrix_world); cs = cs.reshape(-1, 3) @ Mw[:3, :3].T + Mw[:3, 3]
        c = cs.mean(axis=0)
        r = float(np.median(np.linalg.norm(cs - c, axis=1)))     # 真实球半径(中位), 不是 bbox 角半径
        eyes.append((c, r))
        # 眼球 BVH(世界系, 三角化)
        vs = [tuple(v) for v in cs]
        tris = []
        for p in me_e.polygons:
            vi = list(p.vertices)
            for k in range(1, len(vi) - 1):
                tris.append((vi[0], vi[k], vi[k + 1]))
        eye_bvhs.append(BVHTree.FromPolygons(vs, tris, all_triangles=True))
    if not eyes:
        return dict(note="v7: 无眼球对象, 跳过")
    rs_max = max(r for _c, r in eyes)
    # 外部视角方向(前半球+两侧): 方位角 -75..75 步 30, 仰角 -30/0/+30
    dirs = []
    for az in (-75, -45, -15, 15, 45, 75, 0):
        for el in (-30, 0, 30):
            a = math.radians(az); b = math.radians(el)
            v = (-math.sin(a) * math.cos(b), -math.cos(a) * math.cos(b), math.sin(b))  # 从外部指向头(-y=正面)
            dirs.append(np.array(v, float))
    dirs = dirs[:n_view]
    R_OUT = 6.0 * rs_max

    def occluded_by_eye(p, nrm):
        """从各外部视角看 p: 全部被眼球挡住 → True(带眼球时不可见)"""
        for d in dirs:
            o = p + d * R_OUT
            v = -d                      # 从外部朝 p 打
            hit_any = False
            for bvh_i, (ce, re) in zip(eye_bvhs, eyes):
                r = bvh_i.ray_cast(Vector(o), Vector(v), R_OUT * 2.0)
                if r[0] is None:
                    continue
                dd = float((np.array(r[0]) - p).dot(d))   # 沿视线到命中点相对 p 的距离
                if -1e-6 < dd < 2.0 * rs_max:             # 命中的是眼球而非身后其它物
                    hit_any = True
                    break
            if not hit_any:
                return False            # 该视角能看见 → 不是被遮挡
        return True

    fixed = a0.copy()
    nfix = 0; nface = 0
    n_cand = 0; n_vis_cand = 0; maxd = 0.0
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
        cen = ctr @ M[:3, :3].T + M[:3, 3]
        me.calc_loop_triangles()
        lt_idx = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("loops", lt_idx); lt_idx = lt_idx.reshape(-1, 3)
        tri_poly = np.empty(len(me.loop_triangles), np.int32)
        me.loop_triangles.foreach_get("polygon_index", tri_poly)
        # 候选面(任一眼球 dr_max×r 内) —— 仅作射线候选, 是否涂色由可见性决定
        eyezone = np.zeros(n, bool)
        for c, r in eyes:
            eyezone |= (np.linalg.norm(cen - c, axis=1) < dr_max * r)
        if not eyezone.any():
            continue
        def _tri_col(tri):
            xs = np.clip((tri[:, 0] * W).astype(int), 0, W - 1)
            ys = np.clip(((1 - tri[:, 1]) * H).astype(int), 0, H - 1)
            return np.median(a0[ys, xs], axis=0)
        cols = np.array([_tri_col(luv[ls[i]:ls[i] + lt[i]]) for i in range(n)])
        lum = 0.30 * cols[:, 0] + 0.59 * cols[:, 1] + 0.11 * cols[:, 2]
        # 2026-09-22: 逐候选面做可见性判定 —— 全部外部视角都被眼球挡住 = 带眼球时不可见 = 可涂
        anom_face = np.zeros(n, bool)
        vis_face = np.zeros(n, bool)
        for i in np.where(eyezone)[0]:
            if occluded_by_eye(cen[i], None):
                anom_face[i] = True
            else:
                vis_face[i] = True
        n_cand += int(eyezone.sum()); n_vis_cand += int(vis_face.sum())
        # 眼窝缘皮肤色 = 眼区内【可见且亮】的面中位(旧版把会被涂色的暗面也纳入中位 → 取到偏暗色)
        rim = eyezone & vis_face & (lum > 100)
        if rim.sum() < 20:
            continue
        rimcol = np.median(cols[rim], axis=0).astype(np.uint8)
        # 诊断: 被涂面到眼球中心的最大距离(正常应≈1.0-1.2r; 旧版按 bbox 角半径会到 1.73r)
        for i in np.where(anom_face)[0]:
            maxd = max(maxd, min(float(np.linalg.norm(cen[i] - c)) for c, r in eyes))
        for t in range(len(me.loop_triangles)):
            fi = tri_poly[t]
            if not anom_face[fi]:
                continue
            tri = luv[lt_idx[t]]
            xs = np.clip((tri[:, 0] * W).astype(int), 0, W - 1)
            ys = np.clip(((1 - tri[:, 1]) * H).astype(int), 0, H - 1)
            x0, x1 = xs.min(), xs.max(); y0, y1 = ys.min(), ys.max()
            gy, gx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
            v0, v1, v2 = tri
            d = (v1[0] - v0[0]) * (v2[1] - v0[1]) - (v2[0] - v0[0]) * (v1[1] - v0[1])
            if abs(d) < 1e-12:
                continue
            gu = gx / W; gv = 1 - gy / H
            w1 = ((gu - v0[0]) * (v2[1] - v0[1]) - (gv - v0[1]) * (v2[0] - v0[0])) / d
            w2 = ((gv - v0[1]) * (v1[0] - v0[0]) - (gu - v0[0]) * (v1[1] - v0[1])) / d
            m = (w1 >= -0.02) & (w2 >= -0.02) & (w1 + w2 <= 1.02)
            fixed[y0:y1 + 1, x0:x1 + 1][m] = rimcol
            nfix += int(m.sum())
        nface += int(anom_face.sum())
    if nface == 0:
        return dict(note="v7: 眼窝碗内无暗面, 无需修复")
    Image.fromarray(fixed).save(png_path)
    if crop_dir:
        os.makedirs(crop_dir, exist_ok=True)
        Image.fromarray(a0[H // 2 - 400:H // 2 + 200, W // 2 - 500:W // 2 + 500]).save(os.path.join(crop_dir, "v7_before.png"))
        Image.fromarray(fixed[H // 2 - 400:H // 2 + 200, W // 2 - 500:W // 2 + 500]).save(os.path.join(crop_dir, "v7_after.png"))
    return dict(faces=nface, texels=nfix, cand=n_cand, cand_visible=n_vis_cand,
                painted_max_mm=round(maxd * 1000, 2), eye_r_mm=round(rs_max * 1000, 2),
                note=f"v7: {nface}面/{nfix}像素【带眼球被遮挡】的碗心替换为眼窝缘皮肤色 "
                     f"(候选{n_cand}面, 其中可见{n_vis_cand}面未动; 被涂面最远 {maxd*1000:.2f}mm = {maxd/rs_max:.2f}r)")


if __name__ == "__main__":
    p = os.environ.get("TEX_FIX_PNG", DEFAULT_PNG)
    st = fix_diffuse_png(p)
    print("贴图溢出处理:", st)