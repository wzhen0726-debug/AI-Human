# -*- coding: utf-8 -*-
"""8.9 rim 环恢复 v2 (2026-09-28) —— 可测试模块, 供 02QR拓扑/scripts/02_qr_auto.py 调用.

背景(v1 实测 2026-09-28 A/B, logs/_ab03/):
  - v1(QR_RIM_RESTORE=1) 把低模 rim 环按高模真值环补密, 眼角转角 68.7°→~25°;
    但【引入新的眼区自交】: 同输入 A/B 关=0 对 / 开=1 对(右眼外眼角);
    09-28 正式跑 =3 对(左眼外眼角) —— 插入点被搬到真值折线时戳进折返处 1.28mm 外的对侧面。
  - v1 的 RDP 容差 0.10mm 在折返处允许弦转角 ~27°, 达不到"眼角 ≤20°"的验收指标。

v2 设计(相对 v1 的强制改进):
  1. 【单调自交门】每个点(插入点+存活顶点)试位后, 眼区局部"同口径"自交对数不得增加,
     否则该点回退到弦上位置 → 对数全程单调不增, 结构上保证"不引入新自交"。
  2. 【自适应加密】目标: 环上所有顶点 XZ 转角 ≤ ang_target(默认 15°, 验收≤20°留余量);
     初始 RDP(tol=0.10mm), 不达标就对相关段按 tol/3, gap/2.5 迭代加密(≤max_iter 轮, 点数≤max_ins)。
  3. 【存活顶点回真值折线】(可关): 低模原有 rim 顶点投影到真值折线最近点, 位移上限 max_move_mm。
  4. 【阶段复核】插点先落弦上(几何不变)复核; 拓扑阶段变差/非流形增加 → 整眼回退。
  5. 只动眼孔 rim 边界环, 其它区域零改动; 结果环必须仍是单一闭环, 否则回退。

用法:
    from rim_restore import restore_rim
    rep = restore_rim(obj, HIw, center_w, ...)   # 就地改 obj.data; 返回中文键报告
"""
import math
import numpy as np
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree


# ---------------- 基础几何 ----------------
def _seg_dev(P, A, B):
    AB = B - A
    n = float(np.linalg.norm(AB))
    if n < 1e-12:
        return float(np.linalg.norm(P - A, axis=1).max())
    return float(np.linalg.norm(np.cross(P - A, AB / n), axis=1).max())


def _rdp(P, tol):
    keep = [0, len(P) - 1]
    st = [(0, len(P) - 1)]
    while st:
        i0, i1 = st.pop()
        if i1 - i0 < 2:
            continue
        A, B = P[i0], P[i1]
        AB = B - A
        n = float(np.linalg.norm(AB))
        if n > 1e-12:
            d = np.linalg.norm(np.cross(P[i0 + 1:i1] - A, AB / n), axis=1)
        else:
            d = np.linalg.norm(P[i0 + 1:i1] - A, axis=1)
        k = int(np.argmax(d))
        if d[k] > tol:
            keep.append(i0 + 1 + k)
            st.append((i0, i0 + 1 + k))
            st.append((i0 + 1 + k, i1))
    return sorted(set(keep))


def ring_indices_of(bm, c3l, margin_y=0.02, radius=0.05):
    """按开放边(degree1)+眼心邻域过滤, 返回该眼 rim 环的有序顶点索引列表(bmesh 索引)。
    与 restore_rim 内部的初始环提取同判据(半径 0.05 / y<c3+margin)。"""
    oe = [e for e in bm.edges if len(e.link_faces) == 1
          and (e.verts[0].co - Vector(c3l)).xz.length < radius and e.verts[0].co.y < c3l[1] + margin_y]
    dg = {}
    for e in oe:
        a, b = e.verts
        dg.setdefault(a.index, []).append(b.index)
        dg.setdefault(b.index, []).append(a.index)
    if len(oe) < 10 or any(len(v) != 2 for v in dg.values()):
        return None
    st = next(iter(dg))
    ring = [st]
    pv, cu = None, st
    while True:
        nx = [x for x in dg.get(cu, []) if x != pv]
        if not nx or nx[0] == st:
            break
        pv, cu = cu, nx[0]
        ring.append(cu)
    if len(ring) != len(dg):
        return None
    return ring


def _xz_angles(P3):
    """闭合折线每个顶点的 XZ 转角(度)。全部顶点都算(v1 口径少算环起点, 这里更严)"""
    n = len(P3)
    out = np.zeros(n)
    if n < 3:
        return out
    Q = P3[:, [0, 2]]
    for i in range(n):
        a1 = Q[i] - Q[(i - 1) % n]
        a2 = Q[(i + 1) % n] - Q[i]
        n1 = float(np.linalg.norm(a1))
        n2 = float(np.linalg.norm(a2))
        if n1 < 1e-12 or n2 < 1e-12:
            continue
        out[i] = math.degrees(math.acos(float(np.clip(np.dot(a1, a2) / (n1 * n2), -1.0, 1.0))))
    return out


def ring_metrics_str(P3):
    """与 02_qr_auto.py 8.9 / audit_rim 同口径串(v1 风格: 环起点不计)"""
    if len(P3) < 3:
        return "点<3"
    seg = np.linalg.norm(np.diff(np.vstack([P3, P3[:1]]), axis=0), axis=1)
    Q = np.vstack([P3[:, [0, 2]], P3[:1, [0, 2]]])
    ang = []
    for i in range(1, len(Q) - 1):
        a1 = Q[i] - Q[i - 1]
        a2 = Q[i + 1] - Q[i]
        n1, n2 = float(np.linalg.norm(a1)), float(np.linalg.norm(a2))
        if n1 < 1e-12 or n2 < 1e-12:
            continue
        ang.append(math.degrees(math.acos(float(np.clip(np.dot(a1, a2) / (n1 * n2), -1, 1)))))
    ang = np.array(ang)
    return ("点=%d 边长中位=%.3f max=%.3fmm CV=%.1f%% | 转角中位=%.2f° 均值=%.2f° max=%.2f° >15°=%d >25°=%d"
            % (len(P3), np.median(seg) * 1000, seg.max() * 1000, seg.std() / seg.mean() * 100,
               np.median(ang), ang.mean(), ang.max(), int((ang > 15).sum()), int((ang > 25).sum())))


# ---------------- 网格数组 / 同口径自交计数 ----------------
def mesh_arrays(me):
    npo = len(me.polygons)
    nl = len(me.loops)
    ps = np.empty(npo, dtype=np.int64); me.polygons.foreach_get("loop_start", ps)
    pt = np.empty(npo, dtype=np.int64); me.polygons.foreach_get("loop_total", pt)
    LV = np.empty(nl, dtype=np.int64); me.loops.foreach_get("vertex_index", LV)
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    return ps, pt, LV, co


def box_tris(ps, pt, LV, co, lo, hi):
    """盒内(任一项点在盒内)面的扇形三角化 —— 与 selfint_clean._local_count 同口径"""
    inside = np.all((co >= lo) & (co <= hi), axis=1)
    fid = np.searchsorted(ps, np.arange(len(LV)), side='right') - 1
    faces = np.unique(fid[inside[LV]])
    if len(faces) == 0:
        return np.zeros((0, 3), dtype=np.int64)
    tris = []
    for f in faces:
        vi = LV[ps[f]:ps[f] + pt[f]]
        for k in range(1, len(vi) - 1):
            tris.append((int(vi[0]), int(vi[k]), int(vi[k + 1])))
    return np.array(tris, dtype=np.int64)


def pair_list_sub(co, tris):
    """严格自交对列表(精确相交; 与 selfint_clean._self_pairs_from 同判据)"""
    if len(tris) < 4:
        return []
    used = np.unique(tris)
    remap = {int(v): k for k, v in enumerate(used)}
    pts = [tuple(map(float, co[int(v)])) for v in used]
    t2 = [tuple(remap[int(v)] for v in t) for t in tris]
    bvh = BVHTree.FromPolygons(pts, t2, all_triangles=True)
    return [(i, j) for i, j in bvh.overlap(bvh) if i < j]


def count_pairs_sub(co, tris):
    return len(pair_list_sub(co, tris))


def loop_tris_box(me, lo, hi):
    """Blender 真实三角化(loop_triangles=导出/渲染用的那种)在盒内的三角形 —— 第二口径"""
    me.calc_loop_triangles()
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    n = len(me.loop_triangles)
    tr = np.empty(n * 3, dtype=np.int64); me.loop_triangles.foreach_get("vertices", tr); tr = tr.reshape(-1, 3)
    inside = np.all((co >= lo) & (co <= hi), axis=1)
    keep = inside[tr].any(axis=1)
    return co, tr[keep]


def nonmanifold_count(me):
    ne = len(me.edges)
    LE = np.empty(len(me.loops), dtype=np.int64); me.loops.foreach_get("edge_index", LE)
    cnt = np.bincount(LE, minlength=ne)
    return int((cnt > 2).sum())


# ---------------- 主流程 ----------------
def _rotate_face_anchor(bm, f, anchor_v):
    """重建面 f 使 loop 顺序从 anchor_v 开始 —— 改变扇形三角化锚点(vi[0]).
    返回新面对象; 失败返回 None. 保持绕向/材质索引不变."""
    try:
        vs = list(f.verts)
        if anchor_v not in vs or len(vs) < 3:
            return None
        k = vs.index(anchor_v)
        vs2 = vs[k:] + vs[:k]
        mi = f.material_index
        bmesh.ops.delete(bm, geom=[f], context='FACES_ONLY')
        nf = bm.faces.new(vs2)
        nf.material_index = mi
        nf.normal_update()
        return nf
    except Exception:
        return None


def restore_rim_combo(obj, HIw, center_w, combos=None, budgets=(60, 24), tri_flags=(False, True),
                      move_flags=(True, False), ang_probe=None, verbose=True, **kw):
    """对 (预算 max_ins) × (带面三角化) × (是否移动顶点) 的组合各跑一次 restore_rim, 每次从同一原始网格出发,
    按 (转角max, 轮廓偏差max) 择优。硬门槛: 收尾最大转角不得比初始环更折(>初始+0.01° 即弃用该组合)。
    胜者写回 obj.data 并返回其 rep(附 "variant")。"""
    base = obj.data.copy()               # 原始状态(每次尝试都从这里重新开始)
    best = None
    last = None
    if combos is None:
        combos = [(int(_b), bool(_tb), bool(_mv))
                  for _tb in tri_flags for _mv in move_flags for _b in budgets]
    for (_b, _tb, _mv) in combos:
        obj.data = base.copy()
        obj.data.update()
        tag = (int(_b), bool(_tb), bool(_mv))
        try:
            r = restore_rim(obj, HIw, center_w, max_ins=_b, tri_band=_tb, move_verts=_mv,
                            verbose=False, **kw)
        except Exception as _e:
            import traceback
            traceback.print_exc()
            print("8.9 rim恢复: ⚠ 组合(预算%d, 三角化%s, 移动%s) 异常: %s" % (_b, _tb, _mv, _e))
            continue
        last = r
        if not r.get("ok"):
            if verbose:
                print("8.9 rim恢复: 组合(预算%d, 三角化%s, 移动%s) 失败/回退: %s"
                      % (_b, _tb, _mv, r.get("reverted")))
            continue
        a = r.get("ang_max_after"); a = 999.0 if a is None else float(a)
        d = r.get("dev_max_after"); d = 999.0 if d is None else float(d)
        a0 = r.get("ang_max_before"); a0 = 0.0 if a0 is None else float(a0)
        if ang_probe is not None:
            try:
                a = float(ang_probe(obj))
            except Exception:
                pass
        over = a > a0 + 0.01          # 收尾比初始更折 → 弃用
        if verbose:
            print("8.9 rim恢复: 组合(预算%d, 三角化%s, 移动%s) → 转角max %.2f°(初始 %.2f°%s) 偏差max %.3fmm "
                  "局部自交 %s(真 %s) 平滑轮 %s"
                  % (_b, _tb, _mv, a, a0, ", 更折→弃用" if over else "", d,
                     r.get("local_after"), r.get("pairs_real_after"), r.get("smooth_passes")))
        if over:
            continue
        if best is None or (a, d) < best[0]:
            best = ((a, d), dict(r), obj.data.copy(), tag)
    if best is None:
        obj.data = base.copy()
        obj.data.update()
        out = dict(last) if last is not None else {"ok": False}
        out["ok"] = False
        out["reverted"] = (out.get("reverted") or "所有组合收尾转角都更折或失败")
        out["variant"] = "无(保持未恢复)"
        if verbose:
            print("8.9 rim恢复: ⚠ 无可用组合 → 该眼保持未恢复原样")
        return out
    obj.data = best[2]
    obj.data.update()
    out = best[1]
    out["variant"] = {"max_ins": best[3][0], "tri_band": best[3][1], "move_verts": best[3][2],
                      "score_ang": round(best[0][0], 2), "score_dev": round(best[0][1], 3)}
    if verbose:
        print("8.9 rim恢复: 采纳 (预算%d, 三角化%s, 移动%s) 转角max %.2f° 偏差max %.3fmm"
              % (best[3][0], best[3][1], best[3][2], best[0][0], best[0][1]))
    return out


def restore_rim(obj, HIw, center_w, tol_mm=0.10, gap_mm=0.25, ang_target=15.0,
                move_verts=True, max_move_mm=1.5, max_ins=120, min_gap_mm=0.06,
                max_iter=5, gate_margin_mm=4.0, gate_real=True, fold_clear_mm=0.5,
                smooth_iter=4, smooth_lam=0.5, tri_band=True, verbose=True):
    HIw = np.asarray(HIw, dtype=float)
    center_w = np.asarray(center_w, dtype=float)
    rep = {"ok": False, "ins_planned": 0, "ins_done": 0, "moved": 0, "reverted": None,
           "local_before": None, "local_after": None, "nm_before": None, "nm_after": None,
           "ang_max_before": None, "ang_max_after": None, "n_ring_before": None,
           "n_ring_after": None, "hit_cap": False}
    MW = np.array(obj.matrix_world)
    inv = np.linalg.inv(MW)
    c3l = inv[:3, :3] @ center_w + inv[:3, 3]
    me = obj.data
    snap = me.copy()
    nm_before = nonmanifold_count(me)
    rep["nm_before"] = nm_before
    HIl = (HIw - MW[:3, 3]) @ np.linalg.inv(MW[:3, :3]).T

    def _fail(msg):
        obj.data = snap
        obj.data.update()
        rep["reverted"] = msg
        rep["ok"] = False
        if verbose:
            print("8.9 rim恢复(v2): ⚠ 回退 — %s" % msg)
        return rep

    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()

    # --- 低模 rim 环(开放边, 眼心附近) ---
    oe = [e for e in bm.edges if len(e.link_faces) == 1
          and (e.verts[0].co - Vector(c3l)).xz.length < 0.05 and e.verts[0].co.y < c3l[1] + 0.02]
    dg = {}
    for e in oe:
        a, b = e.verts
        dg.setdefault(a.index, []).append(b.index)
        dg.setdefault(b.index, []).append(a.index)
    deg_bad = [k for k in dg if len(dg[k]) != 2]
    if len(oe) < 10 or deg_bad:
        bm.free()
        return _fail("低模 rim 环异常(边界边%d 度≠2点%d)" % (len(oe), len(deg_bad)))
    st_i = next(iter(dg))
    ring_i = [st_i]
    pv, cu = None, st_i
    while True:
        nx = [x for x in dg.get(cu, []) if x != pv]
        if not nx or nx[0] == st_i:
            break
        pv, cu = cu, nx[0]
        ring_i.append(cu)
    if len(ring_i) != len(dg):
        bm.free()
        return _fail("低模 rim 环遍历未覆盖全部点(%d/%d)" % (len(ring_i), len(dg)))
    ring_v = [bm.verts[i] for i in ring_i]
    LOl = np.array([list(v.co) for v in ring_v])
    LOw = LOl @ MW[:3, :3].T + MW[:3, 3]
    nLO = len(LOl)
    rep["n_ring_before"] = nLO
    _CEIL = float(_xz_angles(LOw).max()) + 0.01      # 转角上限: 任何位移/平滑都不得让环上最大转角超过初始值

    # --- 映射到高模真值环 ---
    nH = len(HIw)
    D = np.linalg.norm(HIw[:, None, :] - LOw[None, :, :], axis=2)
    idx = np.argmin(D, axis=0).astype(int)
    fwd = np.array([(int(idx[(i + 1) % nLO]) - int(idx[i])) % nH for i in range(nLO)])
    dirfwd = bool(np.median(fwd) <= nH / 2)

    # --- 折返缝宽度(真值环非邻域最近距离): 缝宽 < fold_clear 处, 目标沿弦回拉 ---
    # 依据: 低模带面宽 2~5mm, 塞不进 0.2~0.4mm 的缝; 硬塞 → 与对侧面片相交(已实测).
    _kk = np.arange(nH)
    _dd = np.abs(_kk[:, None] - _kk[None, :])
    _nb = (_dd <= 8) | (_dd >= nH - 8)
    _Da = np.linalg.norm(HIl[:, None, :] - HIl[None, :, :], axis=2)
    gap_hi = np.where(_nb, 1e9, _Da).min(axis=1)

    def _pull(p, hj, A, B):
        """把真值点目标按缝宽拉回弦上: alpha=clip(gap/fold_clear,0,1); 返回(目标, alpha)"""
        if fold_clear_mm <= 0.0:
            return p, 1.0
        al = float(np.clip(float(gap_hi[int(hj) % nH]) / (fold_clear_mm / 1000.0), 0.0, 1.0))
        if al >= 0.999:
            return p, al
        ab = B - A; nn = float(ab @ ab)
        t = float(np.clip((p - A) @ ab / nn, 0.0, 1.0)) if nn > 1e-16 else 0.0
        foot = A + ab * t
        return (foot + (p - foot) * al), al

    # --- 逐段: 高模弧数组 ---
    arcs = {}
    seg_meta = {}
    for i in range(nLO):
        j0, j1 = int(idx[i]), int(idx[(i + 1) % nLO])
        span = ((j1 - j0) % nH) if dirfwd else ((j0 - j1) % nH)
        if span <= 1:
            continue
        step = 1 if dirfwd else -1
        mid = HIl[np.array([(j0 + step * k) % nH for k in range(1, span)])]
        A, B = LOl[i], LOl[(i + 1) % nLO]
        arc = np.vstack([A[None, :], mid, B[None, :]])
        arcs[i] = (arc, _seg_dev(arc, A, B) * 1000.0)
        seg_meta[i] = (j0, step)

    def _tgt(i, k):
        """段 i 的弧点 k 的最终目标(已按缝宽回拉)"""
        arc = arcs[i][0]
        j0, step = seg_meta[i]
        return _pull(arc[k], (j0 + step * k) % nH, arc[0], arc[-1])[0]
    if not arcs:
        bm.free()
        return _fail("无可加密段(低模环 %d 点 / 真值环 %d 点)" % (nLO, nH))

    # --- 存活顶点→真值折线投影(预测&应用共用) ---
    def _proj_polyline(p, i):
        best = p.copy(); bd = 1e9
        for k in range(-3, 4):
            a = HIl[(idx[i] + k) % nH]; b = HIl[(idx[i] + k + 1) % nH]
            ab = b - a; nn = float(ab @ ab)
            t = float(np.clip((p - a) @ ab / nn, 0, 1)) if nn > 1e-16 else 0.0
            q = a + ab * t
            d = float(np.linalg.norm(p - q))
            if d < bd:
                bd = d; best = q
        return best, bd

    surv_tgt = {}
    if move_verts:
        for i in range(nLO):
            q, d = _proj_polyline(LOl[i], i)
            if d <= max_move_mm / 1000.0:
                if fold_clear_mm > 0.0:      # 缝太窄处只走 alpha 比例(与插点同规则)
                    al = float(np.clip(float(gap_hi[int(idx[i]) % nH]) / (fold_clear_mm / 1000.0), 0.0, 1.0))
                    q = LOl[i] + (q - LOl[i]) * al
                surv_tgt[i] = q

    # --- 迭代规划(角度不达标就对相关段加密) ---
    plan_idx = {i: set() for i in arcs}
    tol = tol_mm / 1000.0
    gap = gap_mm / 1000.0
    active = set(arcs.keys())
    dev_first = {i: arcs[i][1] for i in arcs}
    for it in range(max_iter + 1):
        for i in active:
            arc, _ = arcs[i]
            for k in _rdp(arc, tol)[1:-1]:
                plan_idx[i].add(int(k))
        pred = []
        seg_of = []
        for i in range(nLO):
            pred.append(surv_tgt.get(i, LOl[i])); seg_of.append(i)
            for k in sorted(plan_idx.get(i, ())):
                pred.append(_tgt(i, k)); seg_of.append(i)
        pred = np.array(pred)
        ang = _xz_angles(pred)
        bad = [j for j in range(len(pred)) if ang[j] > ang_target]
        if (not bad) or it == max_iter:
            break
        need = set()
        for j in bad:
            i = seg_of[j]
            need.add(i); need.add((i - 1) % nLO); need.add((i + 1) % nLO)
        active = set(i for i in need if i in arcs)
        if not active:
            break
        tol = max(tol / 3.0, 0.004 / 1000.0)
        gap = max(gap / 2.5, min_gap_mm / 1000.0)

    # --- 最终插点表(间距过滤, 环序) ---
    gap_f = gap
    ins_all = {}
    n_ins = 0
    for i in sorted(plan_idx):
        if not plan_idx[i]:
            continue
        arc = arcs[i][0]
        A, B = arc[0], arc[-1]
        pts = []
        for k in sorted(plan_idx[i]):
            p = _tgt(i, k)
            if np.linalg.norm(p - A) < gap_f * 0.6 or np.linalg.norm(p - B) < gap_f * 0.6:
                continue
            if pts and np.linalg.norm(p - pts[-1]) < gap_f * 0.5:
                continue
            pts.append(p)
        if pts:
            ins_all[i] = pts
            n_ins += len(pts)
    rep["ins_planned"] = n_ins
    if n_ins > max_ins:
        rep["hit_cap"] = True
        keep = max_ins
        cut = {}
        for i in sorted(ins_all):
            take = min(len(ins_all[i]), keep)
            if take > 0:
                cut[i] = ins_all[i][:take]
                keep -= take
            if keep <= 0:
                break
        ins_all = cut
        n_ins = sum(len(v) for v in ins_all.values())
    if n_ins == 0 and not surv_tgt:
        bm.free()
        return _fail("规划 0 个插入点且无顶点可移动")

    # --- 局部自交门基准 ---
    ring_lo = LOl.min(axis=0) - gate_margin_mm / 1000.0
    ring_hi = LOl.max(axis=0) + gate_margin_mm / 1000.0
    ps0, pt0, LV0, co0 = mesh_arrays(me)
    tris_sub0 = box_tris(ps0, pt0, LV0, co0, ring_lo, ring_hi)
    p0 = count_pairs_sub(co0, tris_sub0)
    rep["local_before"] = int(p0)
    rp0 = 0
    if gate_real:
        _coR, _trR = loop_tris_box(me, ring_lo, ring_hi)
        rp0 = count_pairs_sub(_coR, _trR)

    # --- 拓扑插入(逐段; 单调门: 局部自交对数不得增加, 否则 dissolve 回退该段新增点) ---
    def _pairs_now():
        ps_, pt_, LV_, co_ = mesh_arrays(me)
        return count_pairs_sub(co_, box_tris(ps_, pt_, LV_, co_, ring_lo, ring_hi))

    ins_recs = []      # (bmesh vert, target(局部坐标))
    n_done = 0
    n_rej = 0
    for i in sorted(ins_all, key=lambda k: -arcs[k][1]):     # dev 大的段先试(最有价值的先保)
        A_v = ring_v[i]; B_v = ring_v[(i + 1) % nLO]
        cur = bm.edges.get((A_v, B_v))
        if cur is None:
            continue
        seg_new = []
        # 扇形锚点校正: 带面若从外圈点起扇, n 边形的扇形会横跨折返缝 → 假自交.
        # 把锚点转到 rim 端点 A_v 上, 扇形就变成"沿 rim 的条带扇形".
        f_band = cur.link_faces[0] if len(cur.link_faces) == 1 else None
        f_orig_anchor = None
        if f_band is not None:
            vs_now = list(f_band.verts)
            if vs_now:
                f_orig_anchor = vs_now[0]
                if vs_now[0] is not A_v and vs_now[0] is not B_v:
                    _rotate_face_anchor(bm, f_band, A_v)
                    bm.to_mesh(me); me.update()
                    if _pairs_now() > p0:      # 旋转本身变差 → 转回原锚点
                        f_b2 = cur.link_faces[0] if len(cur.link_faces) == 1 else None
                        if f_b2 is not None:
                            _rotate_face_anchor(bm, f_b2, f_orig_anchor)
                        bm.to_mesh(me); me.update()
                        f_orig_anchor = None
        for p in ins_all[i]:
            q0v = np.array(list(cur.verts[0].co)); q1v = np.array(list(cur.verts[1].co))
            ab = q1v - q0v; nn = float(ab @ ab)
            fac = float(np.clip(((p - q0v) @ ab) / nn, 0.02, 0.98)) if nn > 1e-16 else 0.5
            x_v = cur.verts[0]
            try:
                _ne, nv = bmesh.utils.edge_split(cur, x_v, fac)
            except Exception as e:
                if verbose:
                    print("8.9 rim恢复(v2): edge_split 失败(该段剩余点跳过): %s" % e)
                break
            q0 = q0v + ab * fac
            nv.co = Vector((float(q0[0]), float(q0[1]), float(q0[2])))
            seg_new.append((nv, p))
            nxt = [e for e in nv.link_edges if B_v in e.verts]
            if not nxt:
                break
            cur = nxt[0]
            # --- 逐点单调门: 只回退让局部自交变差的那一个点 ---
            bm.to_mesh(me); me.update()
            if _pairs_now() > p0:
                try:
                    bmesh.ops.dissolve_verts(bm, verts=[nv])
                except Exception:
                    pass
                seg_new.pop()
                n_rej += 1
                bm.to_mesh(me); me.update()
                cur = None
                for _e2 in B_v.link_edges:      # dissolve 后取 (x_v,B_v) 子边(避免 edges.get 的同点报错)
                    if _e2.other_vert(B_v) is x_v:
                        cur = _e2
                        break
                if cur is None:
                    break
        bm.to_mesh(me); me.update()
        if _pairs_now() > p0:          # 该段破坏了局部自交 → 整段回退
            for nv, _p in reversed(seg_new):
                try:
                    bmesh.ops.dissolve_verts(bm, verts=[nv])
                except Exception:
                    pass
            bm.to_mesh(me); me.update()
            n_rej += len(seg_new)
        else:
            ins_recs.extend(seg_new)
            n_done += len(seg_new)
    bm.verts.index_update()
    ins_idx = [(int(nv.index), np.array(tgt, dtype=float)) for nv, tgt in ins_recs]
    surv_idx = [(int(ring_v[i].index), np.array(surv_tgt[i], dtype=float)) for i in sorted(surv_tgt)]
    bm.normal_update()
    rep["ins_done"] = n_done
    rep["ins_rejected"] = n_rej

    # --- 带面三角化: rim 相邻的 n 边形带面先切成三角形 ---
    # 理由: n 边形的“扇形”三角化(house 口径/selfint_clean 同一口径)在折返处会生成横跨缝的膜三角形,
    #   产生“假自交”; 先把带面切成三角形, 扇形口径 == Blender 真实三角化口径,
    #   后续折角平滑/位移就不会被假自交挡住(真几何仍由两道门把守)。
    if tri_band:
        _fband = set()
        for _e in bm.edges:
            if len(_e.link_faces) == 1:
                _m = (np.array(list(_e.verts[0].co)) + np.array(list(_e.verts[1].co))) * 0.5
                _mw = _m @ MW[:3, :3].T + MW[:3, 3]
                if (ring_lo[0] <= _mw[0] <= ring_hi[0] and ring_lo[1] <= _mw[1] <= ring_hi[1]
                        and ring_lo[2] <= _mw[2] <= ring_hi[2]):
                    _fband.update(_e.link_faces)
        _fband = [f for f in _fband if len(f.verts) > 3]
        if _fband:
            _me_bak = me.copy()
            _p_b4, _pt4, _lv4, _co4 = mesh_arrays(me)
            _n_b4 = count_pairs_sub(_co4, box_tris(_p_b4, _pt4, _lv4, _co4, ring_lo, ring_hi))
            try:
                bmesh.ops.triangulate(bm, faces=_fband, quad_method='BEAUTY', ngon_method='BEAUTY')
            except Exception as _et:
                print("8.9 rim恢复(v2): 带面三角化失败(跳过): %s" % _et)
            bm.to_mesh(me); me.update()
            _p_a4, _pt6, _lv6, _co6 = mesh_arrays(me)
            _n_a4 = count_pairs_sub(_co6, box_tris(_p_a4, _pt6, _lv6, _co6, ring_lo, ring_hi))
            if _n_a4 > max(p0, _n_b4):
                obj.data = _me_bak              # 三角化反而变差 → 回退
                me = obj.data
                bm = bmesh.new(); bm.from_mesh(me)
                bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
                print("8.9 rim恢复(v2): 带面三角化 %d→%d 对(变差) → 已回退" % (_n_b4, _n_a4))
            else:
                print("8.9 rim恢复(v2): 带面三角化 %d 个面(局部自交 %d→%d)"
                      % (len(_fband), _n_b4, _n_a4))

    # --- 位移阶段: 逐点单调门(1→1/2→1/4→1/8 取最大安全位移) ---
    ps1, pt1, LV1, co1 = mesh_arrays(me)
    tris_sub = box_tris(ps1, pt1, LV1, co1, ring_lo, ring_hi)
    p1 = count_pairs_sub(co1, tris_sub)
    nm1 = nonmanifold_count(me)
    if p1 > p0 or nm1 > nm_before:
        bm.free()
        return _fail("拓扑插入阶段局部自交 %d→%d / 非流形 %d→%d" % (p0, p1, nm_before, nm1))
    co_live = co1.copy()
    cur_pairs = p1
    moved = 0
    clamped = 0
    mv_state = {}          # 顶点索引 -> (原位, 目标)
    _ri_m = ring_indices_of(bm, c3l)

    def _rmax(co_now):
        if not _ri_m:
            return 0.0
        _pw = co_now[np.array(_ri_m)] @ MW[:3, :3].T + MW[:3, 3]
        return float(_xz_angles(_pw).max())
    for vi, tgt in ins_idx + surv_idx:
        if vi >= len(co_live):
            continue
        old = co_live[vi].copy()
        done = False
        for k in (1.0, 0.5, 0.25, 0.125):
            co_live[vi] = old + (tgt - old) * k
            if count_pairs_sub(co_live, tris_sub) <= cur_pairs:
                if k < 1.0:
                    clamped += 1
                cur_pairs = count_pairs_sub(co_live, tris_sub)
                moved += 1
                mv_state[vi] = (old, tgt)
                done = True
                break
        if not done:
            co_live[vi] = old            # 位置不动(留在弦上/原位)
    rep["moved"] = moved
    rep["moved_clamped"] = clamped
    rep["local_after"] = int(cur_pairs)
    co_flat = np.ascontiguousarray(co_live.reshape(-1))
    me.vertices.foreach_set("co", co_flat)
    me.update()

    # (折角平滑已移到第二口径清理之后执行)
    rep["smooth_passes"] = 0

    # --- 第二口径复核(Blender 真实三角化 = 导出/渲染所用): 逐轮收窄越界位移 ---
    rp_after = None
    if gate_real:
        co_r, tr_r = loop_tris_box(me, ring_lo, ring_hi)
        rp_after = count_pairs_sub(co_r, tr_r)

    # --- 收尾清理: fan/real 两路口径轮流逐点收窄(取"最大不引发交叉"的位移比例) ---
    def _cleanup(metric):
        nonlocal co_live
        base = p0 if metric == "fan" else rp0
        for _r in range(8):
            me.vertices.foreach_set("co", np.ascontiguousarray(co_live.reshape(-1)))   # 保证网格==工作副本
            me.update()
            if metric == "fan":
                _p2, _t2, _l2, _c2 = mesh_arrays(me)
                tris = box_tris(_p2, _t2, _l2, _c2, ring_lo, ring_hi)
                pl = pair_list_sub(_c2, tris)
            else:
                _c2, tris = loop_tris_box(me, ring_lo, ring_hi)
                pl = pair_list_sub(_c2, tris)
            if len(pl) <= base:
                return len(pl)
            cand = []
            for i, j in pl:
                for t in (i, j):
                    for v in tris[t]:
                        vv = int(v)
                        if vv in mv_state and vv not in cand:
                            cand.append(vv)
            if not cand:
                return len(pl)
            order = sorted(cand, key=lambda k: -float(np.linalg.norm(mv_state[k][1] - mv_state[k][0])))
            fixed = False
            for vi in order:
                old, tgt = mv_state[vi]
                for kk in (0.5, 0.25, 0.0):
                    trial = co_live.copy()
                    trial[vi] = old + (tgt - old) * kk
                    me.vertices.foreach_set("co", np.ascontiguousarray(trial.reshape(-1)))
                    me.update()
                    if metric == "fan":
                        _q1, _q2, _q3, _c3 = mesh_arrays(me)
                        n2 = count_pairs_sub(_c3, box_tris(_q1, _q2, _q3, _c3, ring_lo, ring_hi))
                    else:
                        _c3, _t3 = loop_tris_box(me, ring_lo, ring_hi)
                        n2 = count_pairs_sub(_c3, _t3)
                    if n2 < len(pl):
                        co_live = trial
                        mv_state[vi] = (old, old + (tgt - old) * kk)
                        if verbose:
                            print("8.9 rim恢复(v2): %s口径收窄 顶点%d 位移→%.0f%% (%d→%d)"
                                  % (metric, vi, kk * 100, len(pl), n2))
                        fixed = True
                        break
                if fixed:
                    break
            if not fixed:
                if verbose:
                    print("8.9 rim恢复(v2): %s口径 %d 对无单点解, 候选整体退回原位" % (metric, len(pl)))
                for vi in cand:
                    co_live[vi] = mv_state[vi][0]
                me.vertices.foreach_set("co", np.ascontiguousarray(co_live.reshape(-1)))
                me.update()
                if metric == "fan":
                    _q1, _q2, _q3, _c3 = mesh_arrays(me)
                    n3 = count_pairs_sub(_c3, box_tris(_q1, _q2, _q3, _c3, ring_lo, ring_hi))
                else:
                    _c3, _t3 = loop_tris_box(me, ring_lo, ring_hi)
                    n3 = count_pairs_sub(_c3, _t3)
                if n3 >= len(pl):
                    return n3
                return n3 if n3 <= base else n3
        return -1

    if gate_real:
        for _alt in range(4):
            f_ret = _cleanup("fan")
            r_ret = _cleanup("real")
            _p9, _t9, _l9, _c9 = mesh_arrays(me)
            f_chk = count_pairs_sub(_c9, box_tris(_p9, _t9, _l9, _c9, ring_lo, ring_hi))
            _c9b, _t9b = loop_tris_box(me, ring_lo, ring_hi)
            r_chk = count_pairs_sub(_c9b, _t9b)
            if f_chk <= p0 and r_chk <= rp0:
                break
        rep["cleanup_rounds"] = _alt + 1
    else:
        _cleanup("fan")
    _cE, _tE = loop_tris_box(me, ring_lo, ring_hi)
    rp_after = count_pairs_sub(_cE, _tE)
    _pE, _tE2, _lE, _cE2 = mesh_arrays(me)
    p_fan_end = count_pairs_sub(_cE2, box_tris(_pE, _tE2, _lE, _cE2, ring_lo, ring_hi))
    rep["local_after"] = int(p_fan_end)
    rep["pairs_real_before"] = int(rp0)
    rep["pairs_real_after"] = int(rp_after) if rp_after is not None else None

    # --- 折角平滑(第二轮): 残余大转角摊到相邻段; 只在两道门都不变差时才提交 ---
    smooth_done = 0
    if smooth_iter > 0:
        bmw = bmesh.new(); bmw.from_mesh(me)
        bmw.verts.ensure_lookup_table()
        _oew = []
        for e in bmw.edges:
            if len(e.link_faces) != 1:
                continue
            w0 = np.array(list(e.verts[0].co)) @ MW[:3, :3].T + MW[:3, 3]
            if np.linalg.norm((w0 - center_w)[[0, 2]]) < 0.05 and w0[1] < center_w[1] + 0.02:
                _oew.append(e)
        _dgw = {}
        for e in _oew:
            a1, b1 = e.verts
            _dgw.setdefault(a1.index, []).append(b1.index)
            _dgw.setdefault(b1.index, []).append(a1.index)
        if len(_dgw) == len(oe) + len(ins_idx):
            stw = next(iter(_dgw)); ring_ord = [stw]; _pvw, _cuw = None, stw
            while True:
                _nx = [x for x in _dgw.get(_cuw, []) if x != _pvw]
                if not _nx or _nx[0] == stw:
                    break
                _pvw, _cuw = _cuw, _nx[0]
                ring_ord.append(_cuw)
            nr = len(ring_ord)
            ridx = np.array(ring_ord)
            co_s = co_live.copy()

            def _rmax_s(co_now):
                _pw = co_now[ridx] @ MW[:3, :3].T + MW[:3, 3]
                return float(_xz_angles(_pw).max())

            for _ps in range(smooth_iter):
                pw = (co_s[ridx] @ MW[:3, :3].T + MW[:3, 3])
                ang_w = _xz_angles(pw)
                pre = co_s[ridx[(np.arange(nr) - 1) % nr]]
                nxt = co_s[ridx[(np.arange(nr) + 1) % nr]]
                mid = 0.5 * (pre + nxt)
                kink = [kk for kk in range(nr) if ang_w[kk] > ang_target]
                if not kink:
                    break
                lam_map = {}
                for kk in kink:
                    lam_map[kk] = smooth_lam
                # (1) 先试整批(同轮所有候选点一起摊) —— 收敛快
                old_b = {}
                for kk, lm in lam_map.items():
                    old_b[kk] = co_s[ridx[kk]].copy()
                    co_s[ridx[kk]] = old_b[kk] + (mid[kk] - old_b[kk]) * lm
                me.vertices.foreach_set("co", np.ascontiguousarray(co_s.reshape(-1)))
                me.update()
                _ps_, _pt_, _LV_, _c2 = mesh_arrays(me)
                okp = count_pairs_sub(_c2, box_tris(_ps_, _pt_, _LV_, _c2, ring_lo, ring_hi)) <= p0
                if okp and gate_real:
                    _c3, _t3 = loop_tris_box(me, ring_lo, ring_hi)
                    okp = count_pairs_sub(_c3, _t3) <= rp0
                if okp:
                    smooth_done += 1
                else:
                    # (2) 整批过不了门 → 逐点试(只让步态可接受的候选点; 逐点只用廉价的 fan 口径,
                    #     整轮结束后再做一次 real 口径复核, 变差则本轮整体回退)
                    for kk in lam_map:
                        co_s[ridx[kk]] = old_b[kk]
                    me.vertices.foreach_set("co", np.ascontiguousarray(co_s.reshape(-1)))
                    me.update()
                    n_acc = 0
                    acc_keys = []
                    for kk, lm in lam_map.items():
                        oldp = co_s[ridx[kk]].copy()
                        co_s[ridx[kk]] = oldp + (mid[kk] - oldp) * lm
                        me.vertices.foreach_set("co", np.ascontiguousarray(co_s.reshape(-1)))
                        me.update()
                        _q1, _q2, _q3, _c4 = mesh_arrays(me)
                        okp2 = count_pairs_sub(_c4, box_tris(_q1, _q2, _q3, _c4, ring_lo, ring_hi)) <= p0
                        if okp2:
                            n_acc += 1
                            acc_keys.append(kk)
                        else:
                            co_s[ridx[kk]] = oldp
                    me.vertices.foreach_set("co", np.ascontiguousarray(co_s.reshape(-1)))
                    me.update()
                    if n_acc == 0:
                        break
                    if gate_real:
                        _c5, _t5 = loop_tris_box(me, ring_lo, ring_hi)
                        if count_pairs_sub(_c5, _t5) > rp0:        # 本轮 real 变差 → 整体回退
                            for kk in acc_keys:
                                co_s[ridx[kk]] = old_b[kk]
                            me.vertices.foreach_set("co", np.ascontiguousarray(co_s.reshape(-1)))
                            me.update()
                            break
                    smooth_done += 1
            co_live = co_s
            me.vertices.foreach_set("co", np.ascontiguousarray(co_s.reshape(-1)))
            me.update()
        elif verbose:
            print("8.9 rim恢复(v2): 平滑跳过(环点数不匹配 %d vs %d)" % (len(_dgw), len(oe) + len(ins_idx)))
        bmw.free()
    rep["smooth_passes"] = smooth_done

    # --- 平滑后再跑一轮双门清理(平滑可能引入新的 real 交叉) ---
    if gate_real and smooth_done:
        for _alt2 in range(3):
            _cleanup("fan")
            _cleanup("real")
            _pa, _ta, _la, _ca = mesh_arrays(me)
            if (count_pairs_sub(_ca, box_tris(_pa, _ta, _la, _ca, ring_lo, ring_hi)) <= p0):
                _cb, _tb = loop_tris_box(me, ring_lo, ring_hi)
                if count_pairs_sub(_cb, _tb) <= rp0:
                    break

    # --- 复核: 环仍单一闭环? ---
    bm3 = bmesh.new(); bm3.from_mesh(me)
    bm3.verts.ensure_lookup_table(); bm3.edges.ensure_lookup_table()
    oe2 = [e for e in bm3.edges if len(e.link_faces) == 1
           and (e.verts[0].co - Vector(c3l)).xz.length < 0.05 and e.verts[0].co.y < c3l[1] + 0.02]
    dg2 = {}
    for e in oe2:
        a, b = e.verts
        dg2.setdefault(a.index, []).append(b.index)
        dg2.setdefault(b.index, []).append(a.index)
    deg_bad2 = [k for k in dg2 if len(dg2[k]) != 2]
    if deg_bad2:
        _info = []
        for k in sorted(deg_bad2)[:6]:
            _v = bm3.verts[k]
            _w = (np.array(list(_v.co)) @ MW[:3, :3].T + MW[:3, 3]) * 1000
            _info.append("idx%d deg%d @(%.2f,%.2f,%.2f)mm" % (k, len(dg2[k]), _w[0], _w[1], _w[2]))
        print("8.9 rim恢复(v2) 调试: 环边=%d 环点=%d 阈值内=%d 坏点: %s"
              % (len(oe2), len(dg2), sum(1 for e in bm3.edges if len(e.link_faces) == 1), " | ".join(_info)))
        bm3.free(); bm.free()
        return _fail("恢复后 rim 环度≠2点=%d" % len(deg_bad2))
    st2 = next(iter(dg2))
    ring2 = [st2]
    pv2, cu2 = None, st2
    while True:
        nx = [x for x in dg2.get(cu2, []) if x != pv2]
        if not nx or nx[0] == st2:
            break
        pv2, cu2 = cu2, nx[0]
        ring2.append(cu2)
    single = (len(ring2) == len(dg2))
    vco = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", vco); vco = vco.reshape(-1, 3)
    R2l = vco[np.array(ring2)]
    R2w = R2l @ MW[:3, :3].T + MW[:3, 3]
    nm2 = int(sum(1 for e in bm3.edges if len(e.link_faces) > 2))
    bm3.free(); bm.free()
    psE, ptE, LVE, coE = mesh_arrays(me)
    rep["local_after"] = int(count_pairs_sub(coE, box_tris(psE, ptE, LVE, coE, ring_lo, ring_hi)))
    if gate_real:
        _cE, _tE = loop_tris_box(me, ring_lo, ring_hi)
        rep["pairs_real_after"] = int(count_pairs_sub(_cE, _tE))
    if not single:
        return _fail("恢复后 rim 环不再是单一闭环(覆盖 %d/%d)" % (len(ring2), len(dg2)))
    rep.update(ok=True, n_ring_after=len(ring2), single_closed_loop=True, nm_after=nm2,
               ang_max_before=float(_xz_angles(LOw).max()),
               ang_max_after=float(_xz_angles(R2w).max()),
               metrics_before=ring_metrics_str(LOw), metrics_after=ring_metrics_str(R2w),
               dev_max_before=float(max(dev_first.values())) if dev_first else 0.0)
    dd = []
    for hp in HIl:
        best = 1e9
        for k in range(len(R2l)):
            a3 = R2l[k]; b3 = R2l[(k + 1) % len(R2l)]
            ab3 = b3 - a3; nn3 = float(ab3 @ ab3)
            t = float(np.clip((hp - a3) @ ab3 / nn3, 0, 1)) if nn3 > 1e-16 else 0.0
            best = min(best, float(np.linalg.norm(hp - (a3 + ab3 * t))))
        dd.append(best)
    rep["dev_max_after"] = float(np.max(dd)) * 1000.0
    return rep
