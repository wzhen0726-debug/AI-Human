# -*- coding: utf-8 -*-
"""rim 环重标定 (S1b) + 轮廓眼角留空 (S1c) —— AB17C 规格落地 (AB17E, 2026-09-30)。

全部 env 开关, 默认关 → 行为与历史完全一致; 由 socket_ops.make_eye_socket 以
try/except 调用, 失败只打印不阻塞管线。

S1b  EYE_RIM_RING_RECAL=1   rim 主环点距重标定回 09-21/22 旧口径 (~0.55mm / ~160~180 点/环)。
  根因(AB17C 因果直证, logs/_ab17/c2/AB17C_REPORT.txt §2~§3): 环点距 0.22mm 远小于
  QR 引擎目标边长(~2mm) 的尺度失配 → QR 在眼角高曲率处多点聚合 → 长直弦/扇簇/窄长面。
  算法 = AB17C 沙箱验证同款 (c2/scripts/resample_ring.py dec 模式, 逐组并点):
    取该侧主环(单闭环开放边界; x<0=L / x>=0=R, 与既有口径一致) → 累计 3D 弧长 →
    N = clamp(round(周长/步长), 100, 320) 个弧长槽 → 每组(同槽)并点, 并点位置 =
    该组弧段中点处的线性插值(落在原环折线上) → bmesh.ops.weld_verts。
  步长 = clamp(0.0145×眼宽mm, 0.45, 0.70); EYE_RIM_RING_RECAL_MM 可用 mm 值显式覆盖。
  自检(逐条打印): 主环单闭环 / 非流形边数不增 / 最短边>1e-6 / 碎边签名不变 /
    周长变化(报告, ≤0.2%) / 合并位置偏差(旧点↔新环折线 max, 预期 ≤~0.04mm) /
    贴角点(距角尖<3mm)计数。完整性主检查失败 → 回滚(obj.data 回快照), 不生效并打印原因。

S1c  EYE_RIM_CANTHUS_CLEAR_MM>0   轮廓眼角留空(源头去贴角): 平滑化后轮廓与手描角尖之间
  保留 ~0.95×clear 的近距; AB18d(2026-10-08) 起改为【与两侧相切的 fillet 圆弧】整体替换角部
  (C1 平滑/单弯; 旧"径向硬推+弧长淡出"在眼角产生亚毫米尖点与 S 型折返, 已弃)。
  EYE_RIM_CANTHUS_CLEAR_FADE_MM 兼容保留(过渡宽度由相切几何决定); 手描原始线(自检基准)一个字节不动。

开关取值: EYE_RIM_RING_RECAL_EYES / EYE_RIM_CANTHUS_CLEAR_EYES = "LR"|"L"|"R"(默认 LR)。
"""
import bpy
import bmesh
import json
import os
import time
import functools
import numpy as np
from mathutils import Vector

print = functools.partial(print, flush=True)
_EPS = 1e-12


def _env_on(name):
    v = os.environ.get(name, "")
    return str(v).strip().lower() not in ("", "0", "false", "off", "no")


def _env_f(name, default):
    try:
        return float(os.environ.get(name, default) or default)
    except Exception:
        return float(default)


def _contour_json_path():
    try:
        import eye_socket_config as _cfg
        return _cfg.EYELID_CONTOUR_JSON
    except Exception:
        return os.environ.get("EYE_CONTOUR_JSON") or ""


def canthus_tips(side):
    """该侧内/外眼角尖点(世界系, 米)。与 logs/_ab16/morph_lib.canthi_m 同口径(rim_3d;
    L: 外=min x / 内=max x; R: 外=max x / 内=min x)。失败返回 {}。"""
    try:
        with open(_contour_json_path(), encoding="utf-8") as f:
            J = json.load(f)
        pts = [np.array([float(x) for x in p]) for p in J[side]["rim_3d"] if p is not None]
        if not pts:
            return {}
        xs = np.array([p[0] for p in pts])
        io = int(np.argmin(xs)) if side == "L" else int(np.argmax(xs))
        ii = int(np.argmax(xs)) if side == "L" else int(np.argmin(xs))
        return {"outer": pts[io], "inner": pts[ii]}
    except Exception:
        return {}


def _loops_from_pairs(pairs):
    """开链提取: 返回 [(顶点id列表, closed_bool)], 按长度降序。"""
    dg = {}
    for a, b in pairs:
        dg.setdefault(a, []).append(b)
        dg.setdefault(b, []).append(a)
    seen = set()
    out = []
    for k in dg:
        if k in seen or len(dg[k]) != 2:
            continue
        ring = [k]
        seen.add(k)
        prev, cur = -1, k
        closed = False
        while True:
            nxt = [q for q in dg[cur] if q != prev]
            if not nxt:
                break
            q = nxt[0]
            if q == ring[0]:
                closed = True
                break
            if q in seen:
                break
            ring.append(q)
            seen.add(q)
            prev, cur = cur, q
        out.append((ring, closed))
    out.sort(key=lambda r: len(r[0]), reverse=True)
    return out


def _extract_side_rings(me, obj, cv, side):
    """该侧边界环提取(与 02/AB17C 同口径: 单面边 + 半边 x 号 + 眼区窗口)。
    返回 dict(main, closed, extras, nm, coW)。"""
    nv = len(me.vertices)
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    MW = np.array(obj.matrix_world)
    coW = co @ MW[:3, :3].T + MW[:3, 3]
    ne = len(me.edges)
    ev = np.empty(ne * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", ev)
    ev = ev.reshape(-1, 2)
    nl = len(me.loops)
    le = np.empty(nl, dtype=np.int64)
    me.loops.foreach_get("edge_index", le)
    cnt = np.bincount(le, minlength=ne)
    nm = int((cnt > 2).sum())
    mids = coW[ev].mean(axis=1)
    side_m = (mids[:, 0] < 0) if side == "L" else (mids[:, 0] >= 0)
    near = ((np.hypot(mids[:, 0] - cv.x, mids[:, 2] - cv.z) < 0.050)
            & (mids[:, 1] < cv.y + 0.020))
    m = (cnt == 1) & side_m & near
    pairs = [(int(ev[i, 0]), int(ev[i, 1])) for i in np.where(m)[0]]
    loops = _loops_from_pairs(pairs)
    n_noloop = int(m.sum()) - sum(len(r) for r, _ in loops)
    main, closed = (list(loops[0][0]), bool(loops[0][1])) if loops else ([], False)
    extras = [len(r) for r, _ in loops[1:]] + [n_noloop]
    return dict(main=main, closed=closed, extras=extras, nm=nm, coW=coW)


def _ring_stats(P, tips):
    seg = np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1)
    st = dict(M=len(P), perim_mm=float(seg.sum()) * 1000.0,
              elen_min_mm=float(seg.min()) * 1000.0,
              elen_med_mm=float(np.median(seg)) * 1000.0,
              elen_max_mm=float(seg.max()) * 1000.0)
    for k, tip in tips.items():
        d = np.linalg.norm(P - tip, axis=1)
        st["d_" + k + "_min_mm"] = round(float(d.min()) * 1000.0, 3)
        st["n_" + k + "_lt3"] = int((d < 0.003).sum())
    return st, seg


def _pt2poly_dist(P, T):
    """P 每点到 T 折线(闭环)的最近距离数组。"""
    A, B = T, np.roll(T, -1, axis=0)
    AB = B - A
    L2 = np.maximum((AB * AB).sum(axis=1), 1e-18)
    d = np.full(len(P), 1e9)
    for k in range(len(A)):
        t = np.clip(((P - A[k]) @ AB[k]) / L2[k], 0.0, 1.0)
        foot = A[k] + t[:, None] * AB[k]
        d = np.minimum(d, np.linalg.norm(P - foot, axis=1))
    return d


def recalibrate_rim_ring(obj, center, side, eye_w=None):
    """S1b: 该侧 rim 主环点距重标定。返回 info dict / None(未启用/跳过/回滚)。"""
    if not _env_on("EYE_RIM_RING_RECAL"):
        return None
    eyes = (os.environ.get("EYE_RIM_RING_RECAL_EYES", "LR") or "LR").upper()
    if side.upper() not in eyes:
        return None
    t0 = time.time()
    cv = Vector((float(center[0]), float(center[1]), float(center[2])))
    me = obj.data
    try:
        if obj.mode != "OBJECT":
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass
    step_mm = _env_f("EYE_RIM_RING_RECAL_MM", 0.0)
    src = "env覆盖"
    if step_mm <= 0:
        if eye_w and float(eye_w) > 0:
            step_mm = min(0.70, max(0.45, 0.0145 * float(eye_w) * 1000.0))
            src = "自动 0.0145×眼宽%.2fmm" % (float(eye_w) * 1000.0)
        else:
            step_mm = 0.55
            src = "兜底0.55(eye_w未知)"
    # ---- before ----
    E0 = _extract_side_rings(me, obj, cv, side)
    if not E0["main"]:
        print("rim_ring_recalibrate %s: 眼区窗口内未找到边界主环 → 跳过" % side)
        return None
    ring0 = E0["main"]
    P0 = E0["coW"][np.array(ring0)]
    tips = canthus_tips(side)
    st0, seg0 = _ring_stats(P0, tips)
    perim = float(seg0.sum())
    M = len(ring0)
    N = int(min(320, max(100, int(round(perim / (step_mm / 1000.0))))))
    if M <= N + 1:
        print("rim_ring_recalibrate %s: 环 %d 点已≤目标 %d 点(步长%.3fmm, %s) → no-op 跳过"
              % (side, M, N, step_mm, src))
        return None
    # ---- bmesh 并点(位置=组弧段中点插值; 与 AB17C 沙箱验证版逐行同款) ----
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    vs = [bm.verts[i] for i in ring0]
    cum = np.concatenate([[0.0], np.cumsum(seg0)])
    slot = np.minimum(N - 1, (cum[:M] * N / perim).astype(np.int64))
    starts = list(np.where(np.diff(slot) != 0)[0] + 1)
    groups = np.split(np.arange(M), starts)
    MWI = obj.matrix_world.inverted()
    tmap = {}
    for g in groups:
        if len(g) < 2:
            continue
        s0 = float(cum[g[0]])
        s1 = float(cum[g[-1] + 1])
        sm = 0.5 * (s0 + s1)
        k = int(np.searchsorted(cum, sm, side="right") - 1)
        k = max(0, min(M - 1, k))
        f = 0.0 if cum[k + 1] <= cum[k] else (sm - cum[k]) / (cum[k + 1] - cum[k])
        tgt_w = P0[k] * (1.0 - f) + P0[(k + 1) % M] * f
        tgt_l = MWI @ Vector((float(tgt_w[0]), float(tgt_w[1]), float(tgt_w[2])))
        ks = int(g[int(np.argmin(np.abs(cum[g] - sm)))])
        vs[ks].co = tgt_l
        for i in g:
            if int(i) != ks:
                tmap[vs[int(i)]] = vs[ks]
    if not tmap:
        bm.free()
        print("rim_ring_recalibrate %s: 无需合并组(M=%d/N=%d) → no-op" % (side, M, N))
        return None
    snap = me.copy()
    snap.name = "_rimRecal_snap"
    bmesh.ops.weld_verts(bm, targetmap=tmap)
    bm.to_mesh(me)
    bm.free()
    me.update()
    # ---- after + 自检 ----
    E1d = _extract_side_rings(me, obj, cv, side)
    ring1 = E1d["main"]
    fail = []
    if not ring1:
        fail.append("主环消失")
    if not E1d["closed"]:
        fail.append("主环非闭环")
    if ring1 and abs(len(ring1) - N) > max(2, int(0.05 * N)):
        fail.append("环点数异常(%d≠%d)" % (len(ring1), N))
    if E1d["nm"] > E0["nm"]:
        fail.append("非流形边数增 %d→%d" % (E0["nm"], E1d["nm"]))
    if E1d["extras"] != E0["extras"]:
        fail.append("碎边签名变化 %s→%s" % (E0["extras"], E1d["extras"]))
    P1w = E1d["coW"][np.array(ring1)] if ring1 else np.zeros((0, 3))
    st1, seg1 = _ring_stats(P1w, tips) if ring1 else ({}, np.zeros(0))
    if len(seg1) and float(seg1.min()) <= 1e-6:
        fail.append("存在退化边<%g" % 1e-6)
    if st1 and abs(st1["perim_mm"] - st0["perim_mm"]) / max(st0["perim_mm"], 1e-9) > 0.01:
        fail.append("周长变化>1%")
    if fail:
        _keep = me.name
        obj.data = snap
        snap.name = _keep
        try:
            bpy.data.meshes.remove(me)
        except Exception:
            pass
        print("rim_ring_recalibrate %s: 自检失败 → 回滚(S1b不生效): %s" % (side, "; ".join(fail)))
        return None
    dev = 0.0
    if len(P1w):
        dev = float(max(_pt2poly_dist(P0, P1w).max(), _pt2poly_dist(P1w, P0).max()))
    try:
        bpy.data.meshes.remove(snap)
    except Exception:
        pass
    _cor = lambda k: "%.3f→%.3f" % (st0.get("d_" + k + "_min_mm", -1), st1.get("d_" + k + "_min_mm", -1))
    _cn = lambda k: "%d→%d" % (st0.get("n_" + k + "_lt3", -1), st1.get("n_" + k + "_lt3", -1))
    dper = (st1["perim_mm"] - st0["perim_mm"]) / max(st0["perim_mm"], 1e-9) * 100.0
    devw = "✓" if dev * 1000.0 <= 0.040 else ("提示" if dev * 1000.0 <= 0.080 else "偏大")
    perw = "✓" if abs(dper) <= 0.2 else "偏大"
    print("rim_ring_recalibrate %s: 环 %d→%d 点, 步长%.3fmm(%s) | 中位 %.3f→%.3f 最短 %.3f→%.3f 最大 %.3f→%.3f mm | "
          "周长 %.2f→%.2fmm(%+.2f%% %s) | 贴角点 内 %s(最近 %s) 外 %s(最近 %s) | 合并位置偏差max %.3fmm %s | "
          "非流形 %d→%d 单闭环=%s 碎边签名不变=%s | %.1fs" %
          (side, M, len(ring1), step_mm, src,
           st0["elen_med_mm"], st1["elen_med_mm"], st0["elen_min_mm"], st1["elen_min_mm"],
           st0["elen_max_mm"], st1["elen_max_mm"],
           st0["perim_mm"], st1["perim_mm"], dper, perw,
           _cn("inner"), _cor("inner"), _cn("outer"), _cor("outer"),
           dev * 1000.0, devw,
           E0["nm"], E1d["nm"], E1d["closed"], E1d["extras"] == E0["extras"],
           time.time() - t0))
    return dict(M_before=M, M_after=len(ring1), step_mm=step_mm, dev_max_mm=dev * 1000.0,
                dper_pct=dper, st_before=st0, st_after=st1)


# ===================== AB18d(2026-10-08): 眼角留空 —— 平滑 fillet 桥接 helpers =====================
#   历史实现(径向硬推+弧长线性淡出)在眼角处产生亚毫米尖点与 S 型折返(实测角部 rmin 2.91→0.34mm、
#   转角序列反复折返): 距角尖<clear 的点被逐一沿径向推至 clear 圆, 推量与淡出权重互不协调 → 折返。
#   新实现: 求与两侧轮廓相切(折线口径)的 fillet 圆 —— 圆心=两侧偏移链交点; 半径扫描+二分, 使
#   |O-tip|-R 命中目标(0.9×clear, 与修前实测 2.689~2.719mm 同口径, env 值 3.0 不动);
#   再用该圆弧整体替换两侧切点之间的角部(角部点按弧长切窗删除, 弧按轮廓同名点距均匀重采样)。
#   切线相切 → C1 平滑、单弯、rmin=R(>=1.5mm); 自交/无解 → 该角不改(安全兜底)。
#   环境变量: EYE_RIM_CANTHUS_CLEAR_MM>0 开启(未设/<=0 原样返回); _EYES="LR"|"L"|"R";
#   _FADE_MM 兼容保留(新实现过渡宽度由相切几何决定); EYE_RIM_CANTHUS_CLEAR_DBG=1 打细节。


def _cac_out_chains(P, tip, Rext):
    """自相距角尖最近点起向两侧走出两条侧链(索引; 由角尖向外), 直到 ρ>=Rext 或半环上限。"""
    m = len(P)
    i0 = int(np.argmin(np.linalg.norm(P - tip, axis=1)))
    def walk(step):
        idx = [i0]; j = i0
        while True:
            if len(idx) >= m // 3:
                break
            j2 = j + step
            if float(np.linalg.norm(P[j2 % m] - tip)) >= Rext:
                break
            j = j2; idx.append(j % m)
        return idx
    return i0, walk(-1), walk(+1)


def _cac_seg_inters(Qa, Qb):
    """两条折线的所有线段交点(闭区间, 含端点相接)。"""
    A, B = Qa[:-1], Qa[1:]
    C, D = Qb[:-1], Qb[1:]
    if len(A) == 0 or len(C) == 0:
        return []
    d1 = (B - A)[:, None, :]
    d2 = (D - C)[None, :, :]
    den = d1[..., 0] * d2[..., 1] - d1[..., 1] * d2[..., 0]
    ok = np.abs(den) > 1e-16
    den = np.where(ok, den, 1.0)
    r = C - A[:, None, :]
    t = (r[..., 0] * d2[..., 1] - r[..., 1] * d2[..., 0]) / den
    u = (r[..., 0] * d1[..., 1] - r[..., 1] * d1[..., 0]) / den
    mm = ok & (t >= -1e-9) & (t <= 1.0 + 1e-9) & (u >= -1e-9) & (u <= 1.0 + 1e-9)
    ii, jj = np.where(mm)
    return [A[i] + t[i, j] * (B[i] - A[i]) for i, j in zip(ii, jj)]


def _cac_solve(P, tip, R, Aidx, Bidx):
    """与两侧链相切(折线口径)、半径 R 的圆: 圆心=两侧偏移链交点(取离角尖最近且切点误差合格者)。"""
    def _off(idx, sgn):
        Q = P[np.array(idx)]
        t = np.gradient(Q, axis=0)
        t = t / (np.linalg.norm(t, axis=1, keepdims=True) + 1e-12)
        n = np.stack([-t[:, 1], t[:, 0]], axis=1)
        return Q + sgn * R * n
    cands = []
    for sA in (1, -1):
        oA = _off(Aidx, sA)
        for sB in (1, -1):
            cands.extend(_cac_seg_inters(oA, _off(Bidx, sB)))
    if not cands:
        return None
    cands.sort(key=lambda p: float(np.linalg.norm(p - tip)))
    Qa = P[np.array(Aidx)]; Qb = P[np.array(Bidx)]
    for O in cands:
        cl = float(np.linalg.norm(O - tip)) - R
        if cl <= 1e-4:
            continue
        dA = np.linalg.norm(Qa - O, axis=1); iA = int(np.argmin(dA))
        dB = np.linalg.norm(Qb - O, axis=1); iB = int(np.argmin(dB))
        if abs(dA[iA] - R) > 0.4e-3 or abs(dB[iB] - R) > 0.4e-3:
            continue
        return dict(O=O, Ta=Qa[iA], Tb=Qb[iB], clear=cl)
    return None


def _cac_keep_mask(Q, T):
    """链点中对 T 投影弧长之后(= 切点外侧)的掩码; T 恰为链点时排除之(避免重复点/零长段)。"""
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    best = 1e18; s_t = 0.0
    for k in range(len(Q) - 1):
        A, B = Q[k], Q[k + 1]; AB = B - A
        L2 = float(AB @ AB)
        tt = 0.0 if L2 <= 0 else float(np.clip(float((T - A) @ AB) / L2, 0.0, 1.0))
        dd = float(np.linalg.norm(T - (A + tt * AB)))
        if dd < best:
            best = dd; s_t = s[k] + tt * float(np.linalg.norm(AB))
    return s > s_t + 1e-9


def _cac_self_int(P):
    """闭环折线 XZ 自交计数(相邻段除外)。"""
    n = len(P)
    if n < 4:
        return 0
    Bqq = np.roll(P, -1, axis=0)
    iu = np.triu_indices(n, k=1)
    ai, aj = iu[0], iu[1]
    keep = ~((aj == ai + 1) | ((ai == 0) & (aj == n - 1)))
    ai, aj = ai[keep], aj[keep]
    p1, p2, p3, p4 = P[ai], Bqq[ai], P[aj], Bqq[aj]
    d1 = p2 - p1; d2 = p4 - p3
    den = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]
    ok = np.abs(den) > 1e-16
    den = np.where(ok, den, 1.0)
    r = p3 - p1
    t = (r[:, 0] * d2[:, 1] - r[:, 1] * d2[:, 0]) / den
    u = (r[:, 0] * d1[:, 1] - r[:, 1] * d1[:, 0]) / den
    m = ok & (t > 1e-9) & (t < 1.0 - 1e-9) & (u > 1e-9) & (u < 1.0 - 1e-9)
    return int(m.sum())


def contour_canthus_clear(poly, side, orig_poly, center=None):
    """S1c(AB18d 重写): 平滑 fillet 桥接的轮廓眼角留空。返回新 poly(列表); 未启用/无贴角点 → 原样返回。
    细节见本节头注释; env 语义: EYE_RIM_CANTHUS_CLEAR_MM 开关+clear 值, _EYES 侧开关,
    _FADE_MM 兼容保留, EYE_RIM_CANTHUS_CLEAR_DBG=1 打细节。"""
    clear_mm = _env_f("EYE_RIM_CANTHUS_CLEAR_MM", 0.0)
    if clear_mm <= 0:
        return poly
    eyes = (os.environ.get("EYE_RIM_CANTHUS_CLEAR_EYES", "LR") or "LR").upper()
    if side.upper() not in eyes:
        return poly
    _ = _env_f("EYE_RIM_CANTHUS_CLEAR_FADE_MM", 6.0)   # 兼容保留(见 docstring)
    _dbg = _env_on("EYE_RIM_CANTHUS_CLEAR_DBG")
    if not orig_poly:
        print("contour_canthus_clear %s: 缺手描原始线 → 跳过" % side)
        return poly
    P = np.array([[float(a), float(b)] for a, b in poly], dtype=np.float64)
    if len(P) < 8:
        return poly
    O = np.array([[float(a), float(b)] for a, b in orig_poly], dtype=np.float64)
    ox = np.abs(O[:, 0])
    tips = {"outer": O[int(np.argmax(ox))], "inner": O[int(np.argmin(ox))]}
    Rc = clear_mm / 1000.0
    target = 0.95 * Rc                    # 目标最近距 = 0.95×clear(验收带 2.4~3.2mm 内; 环贴面 max 更优)
    Rext = max(0.016, 3.0 * Rc)
    Pn = P.copy()
    info = {}
    for kind, tip in tips.items():
        m = len(Pn)
        d = np.linalg.norm(Pn - tip, axis=1)
        i0 = int(np.argmin(d))
        if d[i0] >= Rc:
            info[kind] = ("skip", "无 <%.1fmm 贴角点(最近 %.3fmm)" % (clear_mm, d[i0] * 1000.0))
            if _dbg:
                print("contour_canthus_clear %s[DBG]: %s %s → 不改" % (side, kind, info[kind][1]))
            continue
        s0 = float(np.median(np.linalg.norm(np.roll(Pn, -1, axis=0) - Pn, axis=1)))
        _i0c, Aidx, Bidx = _cac_out_chains(Pn, tip, Rext)
        if len(Aidx) < 5 or len(Bidx) < 5:
            info[kind] = ("fail", "侧链太短(%d/%d)" % (len(Aidx), len(Bidx)))
            print("contour_canthus_clear %s: %s %s → 该角不改" % (side, kind, info[kind][1]))
            continue
        grid = np.arange(0.5, 16.01, 0.25) / 1000.0
        cl = []
        for Rf in grid:
            _s = _cac_solve(Pn, tip, float(Rf), Aidx, Bidx)
            cl.append(np.nan if _s is None else _s["clear"] * 1000.0)
        pick = None
        for k in range(len(grid) - 1):
            c0, c1 = cl[k], cl[k + 1]
            if np.isnan(c0) or np.isnan(c1):
                continue
            if (c0 - target * 1000.0) * (c1 - target * 1000.0) <= 0 and c1 > c0:
                pick = (float(grid[k]), float(grid[k + 1])); break
        if pick is None:
            best = None
            for k, c in enumerate(cl):
                if not np.isnan(c) and (best is None or c > best[1]):
                    best = (float(grid[k]), float(c))
            info[kind] = ("fail", ("fillet 无解(最优 R=%.2fmm 可及最近距 %.3fmm)" %
                                   (best[0] * 1000.0, best[1])) if best else "fillet 无解(无交点)")
            print("contour_canthus_clear %s: %s %s → 该角不改" % (side, kind, info[kind][1]))
            continue
        lo, hi = pick
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            _s = _cac_solve(Pn, tip, mid, Aidx, Bidx)
            if _s is None or _s["clear"] < target:
                lo = mid
            else:
                hi = mid
        _s = _cac_solve(Pn, tip, hi, Aidx, Bidx)
        if _s is None:
            info[kind] = ("fail", "二分后无解")
            print("contour_canthus_clear %s: %s %s → 该角不改" % (side, kind, info[kind][1]))
            continue
        O_c, R, Ta, Tb = _s["O"], hi, _s["Ta"], _s["Tb"]
        th_a = np.arctan2(Ta[1] - O_c[1], Ta[0] - O_c[0])
        th_b = np.arctan2(Tb[1] - O_c[1], Tb[0] - O_c[0])
        th_t = np.arctan2(tip[1] - O_c[1], tip[0] - O_c[0])
        _norm = lambda a: (a + np.pi) % (2.0 * np.pi) - np.pi
        s1 = _norm(th_b - th_a)
        s2 = s1 - 2.0 * np.pi * np.sign(s1)
        sweep = None
        for cand in (s1, s2):
            f = _norm(th_t - th_a)
            if f * cand >= 0 and abs(f) <= abs(cand) + 1e-9:
                sweep = cand; break
        if sweep is None:
            sweep = s1
        n_arc = max(3, int(round(R * abs(sweep) / max(s0, 1e-9))))
        ths = th_a + sweep * np.arange(1, n_arc) / n_arc
        arc = np.stack([O_c[0] + R * np.cos(ths), O_c[1] + R * np.sin(ths)], axis=1)
        Qa = Pn[np.array(Aidx)]; Qb = Pn[np.array(Bidx)]
        mA = _cac_keep_mask(Qa, Ta); mB = _cac_keep_mask(Qb, Tb)
        keepA = [Aidx[k] for k in range(len(Aidx)) if mA[k]]
        keepB = [Bidx[k] for k in range(len(Bidx)) if mB[k]]
        if not keepA or not keepB:
            info[kind] = ("fail", "保留段为空")
            print("contour_canthus_clear %s: %s %s → 该角不改" % (side, kind, info[kind][1]))
            continue
        revA = list(reversed(keepA))
        _start = (Bidx[-1] + 1) % m
        _stop = (Aidx[-1] - 1) % m
        n_unt = (_stop - _start) % m + 1
        seg1 = Pn[[(_start + k) % m for k in range(n_unt)]]
        newP = np.vstack([seg1, Pn[np.array(revA)], Ta[None, :], arc, Tb[None, :], Pn[np.array(keepB)]])
        _si = _cac_self_int(newP)
        if _si:
            info[kind] = ("fail", "拼接自交 %d 处" % _si)
            print("contour_canthus_clear %s: %s %s → 该角不改" % (side, kind, info[kind][1]))
            continue
        info[kind] = ("ok", float(R) * 1000.0,
                      float(np.linalg.norm(Ta - tip)) * 1000.0,
                      float(np.linalg.norm(Tb - tip)) * 1000.0,
                      int(len(arc)), float(d[i0]) * 1000.0, float(_s["clear"]) * 1000.0)
        Pn = newP
        if _dbg:
            print("contour_canthus_clear %s[DBG]: %s fillet R=%.3fmm 切点距角尖 %.3f/%.3fmm | "
                  "clearance %.3f→%.3fmm | 点 %d→%d 弧%d" %
                  (side, kind, R * 1000.0, info[kind][2], info[kind][3],
                   info[kind][5], info[kind][6], m, len(Pn), len(arc)))
    _cn = {"outer": "外", "inner": "内"}
    _parts = []
    _cd = {}
    for kind in ("outer", "inner"):
        it = info.get(kind)
        if it and it[0] == "ok":
            _parts.append("%s R=%.2fmm(切点距角尖 %.2f/%.2fmm, 弧%d点)" % (_cn[kind], it[1], it[2], it[3], it[4]))
            _cd[kind] = (it[5], it[6])
        elif it:
            _parts.append("%s 跳过(%s)" % (_cn[kind], it[1]))
    if not _cd:
        print("contour_canthus_clear %s: 眼角留空 %.1fmm(平滑 fillet) → 两位角均未改" % (side, clear_mm))
        return [(float(a), float(b)) for a, b in Pn]
    _ii = _cd.get("inner", (float("nan"), float("nan")))
    _oo = _cd.get("outer", (float("nan"), float("nan")))
    print("contour_canthus_clear %s: 眼角留空 %.1fmm(平滑 fillet 桥接) → %s; 轮廓最近距角尖 内 %.3f→%.3fmm 外 %.3f→%.3fmm; 点数 %d→%d" %
          (side, clear_mm, "; ".join(_parts), _ii[0], _ii[1], _oo[0], _oo[1], len(P), len(Pn)))
    return [(float(a), float(b)) for a, b in Pn]
# ===================== AB18d helpers 结束 =====================
