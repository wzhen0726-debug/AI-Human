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

S1c  EYE_RIM_CANTHUS_CLEAR_MM>0   轮廓眼角留空(源头去贴角): 平滑化后轮廓上距手描角尖
  <clear 的点沿径向推至 clear, 影响弧段 ±EYE_RIM_CANTHUS_CLEAR_FADE_MM(默认6mm) 线性淡出;
  手描原始线(自检基准)一个字节不动。

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


def contour_canthus_clear(poly, side, orig_poly, center=None):
    """S1c: 平滑后轮廓眼角留空。返回新 poly(列表); 未启用/无贴角点 → 原样返回。"""
    clear_mm = _env_f("EYE_RIM_CANTHUS_CLEAR_MM", 0.0)
    if clear_mm <= 0:
        return poly
    eyes = (os.environ.get("EYE_RIM_CANTHUS_CLEAR_EYES", "LR") or "LR").upper()
    if side.upper() not in eyes:
        return poly
    fade_mm = _env_f("EYE_RIM_CANTHUS_CLEAR_FADE_MM", 6.0)
    if not orig_poly:
        print("contour_canthus_clear %s: 缺手描原始线 → 跳过" % side)
        return poly
    P = np.array([[float(a), float(b)] for a, b in poly], dtype=np.float64)
    if len(P) < 8:
        return poly
    m = len(P)
    seg = np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    perim = float(cum[-1])
    if perim < 1e-9:
        return poly
    O = np.array([[float(a), float(b)] for a, b in orig_poly], dtype=np.float64)
    ox = np.abs(O[:, 0])
    tips = {"outer": O[int(np.argmax(ox))], "inner": O[int(np.argmin(ox))]}
    Pn = P.copy()
    moved = 0
    dmax = 0.0
    info = {}
    for kind, tip in tips.items():
        d = np.linalg.norm(P - tip, axis=1)
        i0 = int(np.argmin(d))
        for i in range(m):
            if d[i] >= clear_mm / 1000.0 or d[i] < 1e-9:
                continue
            arcd = abs(cum[i] - cum[i0])
            arcd = min(arcd, perim - arcd)
            w = max(0.0, 1.0 - arcd / (fade_mm / 1000.0))
            if w <= 0.0:
                continue
            u = (P[i] - tip) / d[i]
            tgt = tip + u * (clear_mm / 1000.0)
            newp = P[i] + w * (tgt - P[i])
            dmax = max(dmax, float(np.linalg.norm(newp - P[i])))
            Pn[i] = newp
            moved += 1
        dd = np.linalg.norm(Pn - tip, axis=1)
        info[kind] = (float(d.min()) * 1000.0, float(dd.min()) * 1000.0)
    if moved == 0:
        print("contour_canthus_clear %s: 无 <%.1fmm 贴角点 → 无需推点" % (side, clear_mm))
        return poly
    print("contour_canthus_clear %s: 眼角留空 %.1fmm(±%.0fmm弧段线性淡出) → 推点 %d 个, 最大位移 %.3fmm; "
          "轮廓最近距角尖 内 %.3f→%.3fmm 外 %.3f→%.3fmm" %
          (side, clear_mm, fade_mm, moved, dmax * 1000.0,
           info["inner"][0], info["inner"][1], info["outer"][0], info["outer"][1]))
    return [(float(a), float(b)) for a, b in Pn]
