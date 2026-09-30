# -*- coding: utf-8 -*-
"""rim 环"眼角 3D 倒圆" —— ab07 新开关(默认关; 沙箱用 env 打开)。

根因(ab07 实测, 见 logs/_ab07/AB07_REPORT.txt):
  QR 引擎的边界采样在【眼角】处局部加密(外眼角 5mm 弧内 rim 点数密度 = 环平均的 1.3~1.85×,
  段长中位 1.1mm vs 环 1.7~2.9mm), 且该处出现极小面/极点/极短段(B 方案最小面 0.104mm² = 中位的 1/14)。
  输入侧对应的几何特征 = 眼角处的【3D 折角】: rim 环在 ±3mm 弧内累计 3D 转角 157~164°
  (= 对应曲率半径 ~2.1mm), 明显小于 QR 目标边长(≈2.4mm 眼周 / 3.7mm 全模)的"可分辨半径";
  而 01a 既有的"眼角圆化"(socket_ops.rebuild_rim_band 内)是按【XZ 投影】逐点阈值 R=0.07×眼宽≈2.45mm 做的,
  3D 方向上的残余折角没有被处理。
本模块: 在【3D】上把眼角的转角摊开(等弧长方向平滑 + 弧长保持重投影), 并按距离衰减带动环外 1~2 排带面顶点,
  使 rim 环在眼角处的局部曲率半径 ≥ 目标值(默认 3.0mm ≈ 0.8×QR 眼周目标边长), 形状改变受限(位移上限, 默认 0.8mm)。

env 开关(全默认关 = 行为与历史完全一致):
  EYE_RIM_CANTHUS_FILLET_MM     目标曲率半径(mm, >0 才启用; 建议 2.5~4.0)
  EYE_RIM_CANTHUS_FILLET_SPAN_MM 弧窗半宽(mm, 默认 3.5)
  EYE_RIM_CANTHUS_FILLET_CAP_MM  单顶点位移上限(mm, 默认 0.8)
  EYE_RIM_CANTHUS_FILLET_SIGMA_MM 环外顶点位移衰减尺度(mm, 默认 0.9)
  EYE_RIM_CANTHUS_FILLET_EYES    "LR"/"L"/"R"(默认 LR)
只动几何, 不改拓扑(不增删顶点/面)。失败只打印, 不阻塞。
"""
import bpy, bmesh, math, os
import numpy as np
from mathutils import Vector

_EPS = 1e-12


def _env_f(name, default=0.0):
    try:
        return float(os.environ.get(name, default) or default)
    except Exception:
        return float(default)


def _ring_of_eye(bm, cv):
    """取该眼的 rim 闭环(开放边界上度数=2 的顶点), 返回按环序的顶点 index 列表。
    ⚠ 区域过滤必须比 socket_ops 里的 30mm/10mm 更宽: 外眼角的环点 y 可到 cv.y+11mm 以外
      (实测 L 外眼角 y=-97.7mm vs cv.y+10=-98.4mm), 用紧过滤会把外眼角整段环漏掉。
    """
    nadj = {}
    for v in bm.verts:
        if (v.co - cv).xz.length > 0.050 or v.co.y > cv.y + 0.020:
            continue
        nb = [e.other_vert(v).index for e in v.link_edges if len(e.link_faces) == 1]
        if len(nb) == 2:
            nadj[v.index] = nb
    st = [k for k in nadj if len(nadj[k]) == 2]
    if not st:
        return []
    ring = [st[0]]; prev, cur = -1, st[0]
    while cur in nadj:
        cand = [n for n in nadj[cur] if n != prev]
        if not cand:
            break
        nxt = cand[0]
        if nxt == ring[0]:
            break
        ring.append(nxt); prev, cur = cur, nxt
        if len(ring) > 200000:
            break
    return ring


def _turns(P):
    n = len(P)
    t = np.zeros(n)
    for i in range(n):
        a = P[(i - 1) % n]; b = P[i]; c = P[(i + 1) % n]
        v1 = b - a; v2 = c - b
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 > _EPS and n2 > _EPS:
            t[i] = math.degrees(math.acos(float(np.clip(np.dot(v1, v2) / (n1 * n2), -1, 1))))
    return t


def _smooth_arc_preserve(Q, iters, lam=0.5):
    """Laplacian 平滑 + 段长重投影(弧长保持): 只改方向, 不缩短曲线"""
    L0 = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    Q = Q.copy()
    for _ in range(int(iters)):
        S = Q.copy()
        S[1:-1] = (1 - lam) * Q[1:-1] + lam * 0.5 * (Q[:-2] + Q[2:])
        # 段长重投影: 按原段长重新积分(保持端点=原端点)
        D = np.diff(S, axis=0)
        d = np.linalg.norm(D, axis=1)
        d = np.where(d < 1e-9, 1e-9, d)
        Dn = D / d[:, None] * L0[:, None]
        R2 = np.vstack([S[0], S[0] + np.cumsum(Dn, axis=0)])
        Q = R2
    return Q


def fillet_rim_canthus(obj, center, side, verbose=True):
    """对单只眼的【内外眼角】做 3D 倒圆。返回 dict 报告(或 None=未启用)。"""
    R_t = _env_f('EYE_RIM_CANTHUS_FILLET_MM', 0.0)
    if R_t <= 0:
        return None
    eyes = (os.environ.get('EYE_RIM_CANTHUS_FILLET_EYES', 'LR') or 'LR').upper()
    if side.upper() not in eyes:
        return None
    span = _env_f('EYE_RIM_CANTHUS_FILLET_SPAN_MM', 3.5) / 1000.0
    cap = _env_f('EYE_RIM_CANTHUS_FILLET_CAP_MM', 0.8) / 1000.0
    sigma = _env_f('EYE_RIM_CANTHUS_FILLET_SIGMA_MM', 0.9) / 1000.0

    cv = Vector((float(center[0]), float(center[1]), float(center[2])))
    mesh = obj.data
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    ring = _ring_of_eye(bm, cv)
    if len(ring) < 8:
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"fillet_rim_canthus {side}: 环顶点不足({len(ring)}) → 跳过")
        return None
    n = len(ring)
    P = np.array([[bm.verts[i].co.x, bm.verts[i].co.y, bm.verts[i].co.z] for i in ring], dtype=np.float64)
    seg = np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])          # n+1
    per = float(arc[-1])

    def window_of(itip):
        step = seg[itip]
        kk = max(3, int(round(span / max(step, 1e-9))))
        kk = min(kk, n // 2 - 1)
        idx = [(itip + x) % n for x in range(-kk, kk + 1)]
        return idx

    moved_v = set()
    rep = {}
    for tag, xf in (("outer", lambda Q: int(np.argmin(Q[:, 0])) if center[0] < 0 else int(np.argmax(Q[:, 0]))),
                    ("inner", lambda Q: int(np.argmax(Q[:, 0])) if center[0] < 0 else int(np.argmin(Q[:, 0])))):
        itip = xf(P)
        idx = window_of(itip)
        if len(idx) < 7:
            continue
        Q0 = P[idx].copy()
        t0 = _turns(Q0)
        # 目标: 窗内累计转角 <= sum(2asin(step/(2R)))
        Lw = np.linalg.norm(np.diff(Q0, axis=0), axis=1)
        allow = np.degrees(2 * np.arcsin(np.clip(Lw / (2 * R_t), 0, 1)))
        target = float(allow.sum())
        best = Q0.copy()
        for it in range(0, 121, 5):
            Qc = _smooth_arc_preserve(Q0, it) if it else Q0.copy()
            if float(_turns(Qc).sum()) <= target:
                best = Qc
                break
            best = Qc
        D = best - Q0
        if verbose:
            print(f"   [fillet] {side}/{tag}: 窗 {len(idx)} 点(弧 {sum(Lw)*1000:.2f}mm) 累计转角 "
                  f"{float(t0.sum()):.1f}° → {float(_turns(best).sum()):.1f}° (目标<= {target:.1f}° @R={R_t:.2f}mm) "
                  f"最大位移 {np.abs(D).max()*1000:.3f}mm(上限{cap*1000:.2f})")
        # 沿窗的衰减(1 在尖端, 0 在窗两端)
        w = np.array([1.0 - (abs(x) / max(len(idx) // 2, 1)) ** 2 for x in range(-(len(idx) // 2), len(idx) // 2 + 1)])
        w = np.clip(w, 0.0, 1.0) ** 2
        Dw = D * w[:, None]
        # 位移上限
        dn = np.linalg.norm(Dw, axis=1)
        over = dn > cap
        if over.any():
            Dw[over] = Dw[over] / dn[over][:, None] * cap
        # 环顶点: 位移
        for j, vi in enumerate(idx):
            v = bm.verts[ring[vi]]
            v.co = Vector((v.co.x + float(Dw[j, 0]), v.co.y + float(Dw[j, 1]), v.co.z + float(Dw[j, 2])))
            moved_v.add(ring[vi])
        # 环外顶点: 按到(原)尖端的距离加权取邻域 3 个窗环点的位移
        P0w = Q0
        band = 2.5 * sigma
        for v in bm.verts:
            if v.index in moved_v:
                continue
            dv = np.linalg.norm(np.array(v.co) - np.array(bm.verts[ring[itip]].co))
            # 用移动前的位姿: 环尖端近似用窗中心点(已移动, 影响很小)
            if dv > band:
                continue
            dd = np.linalg.norm(P0w - np.array(v.co)[None, :], axis=1)
            o = np.argsort(dd)[:3]
            ww = 1.0 / (dd[o] + 0.0002) ** 2
            Dv = (Dw[o] * ww[:, None]).sum(axis=0) / ww.sum()
            fall = max(0.0, 1.0 - (min(dd[o][0], band) / band) ** 2)
            v.co = Vector((v.co.x + float(Dv[0] * fall), v.co.y + float(Dv[1] * fall), v.co.z + float(Dv[2] * fall)))
            moved_v.add(v.index)
        rep[tag] = dict(n_win=len(idx), turn_before=float(t0.sum()), turn_after=float(_turns(best).sum()),
                        target=target, max_disp_mm=float(np.abs(Dw).max() * 1000))
    bm.normal_update()
    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
    if verbose and rep:
        print(f"fillet_rim_canthus {side}: 处理 {len(rep)} 个眼角, 移动顶点 {len(moved_v)} 个 "
              f"(R_target={R_t:.2f}mm span={span*1000:.1f}mm cap={cap*1000:.2f}mm sigma={sigma*1000:.1f}mm)")
    rep["n_moved"] = len(moved_v)
    return rep
def coarsen_rim_canthus(obj, center, side, verbose=True):
    """眼角局部粗化 + 退化面清理。返回 dict 报告(或 None=未启用)。"""
    tgt = _env_f('EYE_RIM_CANTHUS_COARSEN_MM', 0.0)
    if tgt <= 0:
        return None
    eyes = (os.environ.get('EYE_RIM_CANTHUS_FILLET_EYES', 'LR') or 'LR').upper()
    if side.upper() not in eyes:
        return None
    win = _env_f('EYE_RIM_CANTHUS_COARSEN_WIN_MM', 6.0) / 1000.0
    tgt = tgt / 1000.0
    do_clean = (os.environ.get('EYE_RIM_CANTHUS_DEGEN_CLEAN', '1') or '1') != '0'

    cv = Vector((float(center[0]), float(center[1]), float(center[2])))
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    ring = _ring_of_eye(bm, cv)
    if len(ring) < 8:
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"coarsen_rim_canthus {side}: 环顶点不足 → 跳过")
        return None
    n0 = len(ring)
    P = np.array([[bm.verts[i].co.x, bm.verts[i].co.y, bm.verts[i].co.z] for i in ring])
    seg = np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    per = float(arc[-1])
    rep, dissolve = {}, []
    for tag in ("outer", "inner"):
        itip = int(np.argmin(P[:, 0])) if center[0] < 0 else int(np.argmax(P[:, 0]))
        if tag == "inner":
            itip = int(np.argmax(P[:, 0])) if center[0] < 0 else int(np.argmin(P[:, 0]))
        for d in (1, -1):
            i = itip
            acc = 0.0
            while True:
                j = (i + d) % n0
                if j == itip:
                    break
                dd = abs((arc[j] if j >= 0 else arc[j]) - arc[itip])
                dd = min(dd, per - dd)
                if dd > win:
                    break
                acc += seg[i if d > 0 else j]
                if acc < tgt:
                    dissolve.append(ring[j])
                else:
                    acc = 0.0
                i = j
        rep[tag] = dict(win_dissolve=len(dissolve))
    # 去重; 环的极端点(眼角尖)永不溶解
    dissolve = sorted(set(dissolve))
    tipverts = set()
    for c0 in (min(P[:, 0]), max(P[:, 0])):
        tipverts.add(ring[int(np.argmin(np.abs(P[:, 0] - c0)))])
    dissolve = [i for i in dissolve if i not in tipverts]
    if verbose:
        print(f"   [coarsen] {side}: 环 {n0} 点 → 计划溶解 {len(dissolve)} 点(目标点距 {tgt*1000:.2f}mm 窗 ±{win*1000:.1f}mm)")
    if dissolve:
        vs = [bm.verts[i] for i in dissolve]
        try:
            bmesh.ops.dissolve_verts(bm, verts=vs)
        except Exception as e:
            print(f"   [coarsen] {side} dissolve_verts 失败: {e}")
    # 退化面/悬挂顶点清理(只在眼角邻域)
    n_deg = 0
    if do_clean:
        for tag in ("outer", "inner"):
            itip = int(np.argmin(P[:, 0])) if center[0] < 0 else int(np.argmax(P[:, 0]))
            if tag == "inner":
                itip = int(np.argmax(P[:, 0])) if center[0] < 0 else int(np.argmin(P[:, 0]))
            tipv = Vector(P[itip].tolist())
            bm.faces.ensure_lookup_table()
            bad = [f for f in bm.faces if (f.calc_center_median() - tipv).length < 0.0035
                   and (f.calc_area() < 1e-5 or len(f.verts) > 8)]
            if bad:
                n_deg += len(bad)
                bmesh.ops.delete(bm, geom=bad, context='FACES')
            # 悬挂顶点(无面)删除
            hang = [v for v in bm.verts if len(v.link_faces) == 0
                    and (v.co - tipv).length < 0.0035]
            if hang:
                bmesh.ops.delete(bm, geom=hang, context='VERTS')
    bm.normal_update()
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    # 复核: 环仍单一闭环?
    bm2 = bmesh.new(); bm2.from_mesh(obj.data)
    bm2.verts.ensure_lookup_table()
    r2 = _ring_of_eye(bm2, cv)
    P2 = np.array([[bm2.verts[i].co.x, bm2.verts[i].co.y, bm2.verts[i].co.z] for i in r2]) if r2 else np.zeros((0, 3))
    nseg = np.linalg.norm(np.roll(P2, -1, axis=0) - P2, axis=1) * 1000 if len(P2) else np.array([0.0])
    bm2.free()
    if verbose:
        print(f"   [coarsen] {side}: 环 {n0} → {len(r2)} 点 | 段长 中位={np.median(nseg):.3f} min={nseg.min():.3f} "
              f"max={nseg.max():.3f}mm | 删退化面/大 n-gon {n_deg} 个 | 环单一闭环={len(r2) > 8}")
    rep.update(ring_before=n0, ring_after=len(r2), seg_med_mm=float(np.median(nseg)),
               seg_min_mm=float(nseg.min()), seg_max_mm=float(nseg.max()), removed_degenerate=n_deg)
    return rep
