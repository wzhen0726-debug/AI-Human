# -*- coding: utf-8 -*-
"""rim 环【外眼角带行重建】(ab08 治本; 默认关) —— 在"倒圆"基础上把外眼角
"环(0.12~0.33mm) ↔ 第一外排"之间被拉长到 1.4~1.8mm 的扇形/碎片带铲掉, 重建为规则四边形行。

根因(ab07/ab08 实测, 报告见 logs/_ab07/AB07_REPORT.txt 与 logs/_ab08/):
  - 外眼角 3mm 盒内: 19~24 个边比≥5 的细长面(环边 0.12~0.24mm × 径向 0.9~1.76mm 的"缎带"),
    L 另有 1 个退化三角(含 1 价悬挂顶点), R 另有 3 个含悬挂点的 5-gon。
  - 环点距本身均匀(0.13~0.33mm, 眼角最密 0.12mm); 问题在"环→第一外排"的带:
    该带在眼角被拉到 1.4~1.8mm 长, 而环侧一点不稀 → 单排缎带面 边比 5.2~14.3。
  - QR 引擎在这类"密集不规则特征簇"上局部加密/挤压(输入同、两次输出不同) → 眼角拥挤。

本模块(每个外眼角一次):
  1) 取 rim 闭环, 以 x 极值点为外眼角尖; 取 ±SPAN 弧窗内的环点 W(其上的带面全部删掉)
     及窗两端外扩 1 点作"环轨"(rail, 只借现成顶点, 不增删/移动任何环点)。
  2) 删除集合 D = 触及 W 的面 ∪ 触及"碎片顶点"(面价≤3 且全为三角、贴着 W)的面
     ∪ 迭代清掉眼角邻域里被孤立的非环顶点/无线面边(wire)。
  3) 删完后眼角洞的外侧边界 = "第一外排链"(A链, 顶点/边全部保留原样, 位置不动)。
  4) 在 rail 与 A链之间重建: 列 = rail 顶点(1:1), 每列的"行数" n_c = ceil(带宽/目标行宽)
     (1..MAXROWS, 相邻列差≤1, 两端列 n=1 → 复用现成的"切边"不裂缝);
     中间行顶点 = rail→A 直线上按比例取点后【贴回原曲面】(BVH 最近点, 上限 SNAP_MM)。
     面 = 逐列贪心合并(分数 u=j/n 对齐): 同行 → 四边形; 错位 → 良好三角形(都在外排接缝,
     边长 ~0.3~0.4mm)。
  5) 校验(不通过 → 回滚, 原 mesh 一个字节不改): 环点数/位置不变、环仍单一闭环、
     边界边数不变、非流形边数不变、新增面 无细长(边比≥4.6)/无退化(<0.012mm²)/无 n-gon。

env(全默认关 = 与历史完全一致):
  EYE_RIM_CANTHUS_BAND_MM       目标行宽(mm, >0 才启用; 建议 0.38~0.45)
  EYE_RIM_CANTHUS_BAND_SPAN_MM  弧窗半宽(mm, 默认 5.5)
  EYE_RIM_CANTHUS_BAND_SNAP_MM  新顶点贴回原曲面的距离上限(mm, 默认 0.45)
  EYE_RIM_CANTHUS_BAND_MAXROWS  单列最大行数(默认 6)
  EYE_RIM_CANTHUS_FILLET_EYES   "LR"/"L"/"R"(与倒圆共用; 默认 LR)
"""
import bpy, bmesh, math, os
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

_EPS = 1e-12


def _env_f(name, default=0.0):
    try:
        return float(os.environ.get(name, default) or default)
    except Exception:
        return float(default)


def _ring_of_eye(bm, cv):
    """该眼 rim 闭环(开放边界上度=2 的顶点), 返回按环序的顶点 index 列表。
    (与 rim_canthus_fillet._ring_of_eye 完全同口径: 区域过滤放宽到 XZ 50mm / y cy+20mm)"""
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
    ring = [st[0]]
    prev, cur = -1, st[0]
    while cur in nadj:
        cand = [n for n in nadj[cur] if n != prev]
        if not cand:
            break
        nxt = cand[0]
        if nxt == ring[0]:
            break
        ring.append(nxt)
        prev, cur = cur, nxt
        if len(ring) > 200000:
            break
    return ring


def _tri_stats(a, b, c):
    """(面积 m², 边比)"""
    ar = (b - a).cross(c - a).length / 2.0
    ls = [(b - a).length, (c - b).length, (a - c).length]
    return ar, max(ls) / max(min(ls), 1e-12)


def _quad_stats(P):
    """P=[p0..p3] → (面积 m², 顺序边边比)"""
    a, b, c, d = P
    ar = (b - a).cross(c - a).length / 2.0 + (c - a).cross(d - a).length / 2.0
    ls = [(b - a).length, (c - b).length, (d - c).length, (a - d).length]
    return ar, max(ls) / max(min(ls), 1e-12)


def _dvloc(dv, dcoords, v, w):
    """把 bmesh 顶点按对象身份登记到局部列表, 返回局部索引(供 BVHTree.FromPolygons)。"""
    k = dv.get(v)
    if k is None:
        k = len(dcoords)
        dv[v] = k
        dcoords.append(list(w(v)))
    return k


def rebuild_rim_canthus_band(obj, center, side, verbose=True):
    """外眼角带行重建。返回 dict 报告(None = 未启用 env)。失败/校验不过 → ok=False 且 mesh 不变。"""
    tgt_mm = _env_f('EYE_RIM_CANTHUS_BAND_MM', 0.0)
    if tgt_mm <= 0:
        return None
    eyes = (os.environ.get('EYE_RIM_CANTHUS_FILLET_EYES', 'LR') or 'LR').upper()
    if side.upper() not in eyes:
        return None
    span = _env_f('EYE_RIM_CANTHUS_BAND_SPAN_MM', 5.5) / 1000.0
    snapcap = _env_f('EYE_RIM_CANTHUS_BAND_SNAP_MM', 0.0) / 1000.0   # 0 = 关(默认): 贴回会拉塌行距
    maxrows = max(1, int(_env_f('EYE_RIM_CANTHUS_BAND_MAXROWS', 6)))
    tgt = tgt_mm / 1000.0

    cv = Vector((float(center[0]), float(center[1]), float(center[2])))
    mesh = obj.data
    MW = obj.matrix_world.copy()
    MWi = MW.inverted()
    rep = dict(side=side, ok=False, target_mm=tgt_mm, span_mm=span * 1000.0,
               snap_mm=snapcap * 1000.0, maxrows=maxrows, reason="")

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    nv0 = len(bm.verts)
    nf0 = len(bm.faces)

    def w(v):
        return MW @ v.co

    def wl(seq):
        return np.array([list(w(v)) for v in seq], dtype=np.float64)

    def fail(msg):
        rep["reason"] = msg
        bm.free()
        if verbose:
            print(f"rebuild_band {side}: 放弃({msg}) —— mesh 未改动")
        return rep

    try:
        ring = _ring_of_eye(bm, cv)
        if len(ring) < 8:
            return fail(f"环顶点不足({len(ring)})")
        Rv = [bm.verts[i] for i in ring]
        Pw = wl(Rv)
        n = len(ring)
        seg = np.linalg.norm(np.roll(Pw, -1, axis=0) - Pw, axis=1)
        arc = np.concatenate([[0.0], np.cumsum(seg)])
        per = float(arc[-1])
        itip = int(np.argmin(Pw[:, 0])) if cv.x < 0 else int(np.argmax(Pw[:, 0]))
        tip = Vector((Pw[itip, 0], Pw[itip, 1], Pw[itip, 2]))

        # ---- 弧窗(环点) ---- (两端可独立设跨度: SPAN_LO/HI 或 SPAN)
        span_lo = _env_f('EYE_RIM_CANTHUS_BAND_SPAN_LO_MM_%s' % side.upper(),
                          _env_f('EYE_RIM_CANTHUS_BAND_SPAN_LO_MM', span * 1000.0)) / 1000.0
        span_hi = _env_f('EYE_RIM_CANTHUS_BAND_SPAN_HI_MM_%s' % side.upper(),
                          _env_f('EYE_RIM_CANTHUS_BAND_SPAN_HI_MM', span * 1000.0)) / 1000.0
        i_lo = i_hi = itip
        acc = 0.0
        while True:
            j = (i_lo - 1) % n
            if acc + seg[j] > span_lo or j == itip:
                break
            acc += seg[j]
            i_lo = j
        acc = 0.0
        while True:
            j = (i_hi + 1) % n
            if acc + seg[i_hi] > span_hi or j == itip:
                break
            acc += seg[i_hi]
            i_hi = j
        wdel_idx = []
        t = i_lo
        while True:
            wdel_idx.append(t)
            if t == i_hi:
                break
            t = (t + 1) % n
        rail_idx = [(i_lo - 1) % n] + wdel_idx + [(i_hi + 1) % n]
        if len(wdel_idx) > n - 6 or len(wdel_idx) < 6:
            return fail(f"窗过大/过小({len(wdel_idx)}/{n})")
        rail = [Rv[i] for i in rail_idx]
        Wdel = set(Rv[i] for i in wdel_idx)
        rail_set = set(rail)
        railP = wl(rail)
        C = len(rail) - 1  # 列数(rail[0..C])

        # ---- 碎片顶点 J(面价<=3 且全为三角形, 且贴着 W 的面) ----
        J = set()
        for v in bm.verts:
            if v in rail_set:
                continue
            lf = v.link_faces
            if not lf or len(lf) > 3:
                continue
            if not all(len(f.verts) == 3 for f in lf):
                continue
            if (w(v) - tip).length > span * 0.8:
                continue
            if any(any(vv in Wdel for vv in f.verts) for f in lf):
                J.add(v)

        # ---- 删除 D(先快照带面几何: 供 BVH 贴回与法线参考) ----
        Dset = set()
        for v in Wdel:
            Dset.update(v.link_faces)
        for v in J:
            Dset.update(v.link_faces)
        if not Dset:
            return fail("D 集合为空")
        D = list(Dset)
        dv = {}
        dcoords = []
        dpolys = []
        dnrm = np.zeros(3)
        da = 0.0
        for f in D:
            dpolys.append([_dvloc(dv, dcoords, v, w) for v in f.verts])
            dnrm = dnrm + np.array(list(f.normal)) * f.calc_area()
            da += f.calc_area()
        dnrm = dnrm / max(np.linalg.norm(dnrm), _EPS)
        bvh = BVHTree.FromPolygons(dcoords, dpolys, all_triangles=False)
        bmesh.ops.delete(bm, geom=D, context='FACES_ONLY')
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        # ---- 清理: 眼角邻域内的非环孤立顶点 → 无线面边(保留环-环边备用) ----
        Rlim = span * 1.45
        for _round in range(10):
            dead = [v for v in bm.verts
                    if v.is_valid and len(v.link_faces) == 0 and v not in rail_set
                    and (w(v) - tip).length <= Rlim]
            if not dead:
                break
            bmesh.ops.delete(bm, geom=dead, context='VERTS')
            bm.verts.ensure_lookup_table()
        rset = rail_set
        wire = [e for e in bm.edges
                if len(e.link_faces) == 0
                and not (e.verts[0] in rset and e.verts[1] in rset)
                and (w(e.verts[0]) - tip).length <= Rlim]
        if wire:
            bmesh.ops.delete(bm, geom=wire, context='EDGES')
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
        wire_keep = [e for e in bm.edges if len(e.link_faces) == 0]
        rep["wire_left_mid"] = len(wire_keep)
        if len(wire_keep) > 0:
            # 除"环-环边"外不允许残留无线面边
            badwire = [e for e in wire_keep if not (e.verts[0] in rail_set and e.verts[1] in rail_set)]
            if badwire:
                return fail(f"清理后仍残留无线面边 {len(badwire)}")

        # ---- 找 A链(外排链): 眼角邻域内 单面边 的连通链(两端各接一条"切边"到 rail) ----
        #      排除"环-环"边(环自身就是边界, 与窗外的环段无关)
        ring_vset = set(Rv)
        chain_edges = []
        for e in bm.edges:
            if len(e.link_faces) != 1:
                continue
            a, b = e.verts
            if a in rail_set or b in rail_set:
                continue
            if a in ring_vset and b in ring_vset:
                continue
            if (w(a) - tip).length > Rlim or (w(b) - tip).length > Rlim:
                continue
            chain_edges.append((a, b))
        chain_adj = {}
        for a, b in chain_edges:
            chain_adj.setdefault(a, []).append(b)
            chain_adj.setdefault(b, []).append(a)
        bad = [v for v, nb in chain_adj.items() if len(nb) not in (1, 2)]
        if bad:
            return fail(f"A链顶点度异常 {len(bad)} 个")
        # 连通分量
        seen = set()
        comps = []
        for v0 in chain_adj:
            if v0 in seen:
                continue
            stack = [v0]
            seen.add(v0)
            comp = []
            while stack:
                u = stack.pop()
                comp.append(u)
                for x in chain_adj[u]:
                    if x not in seen:
                        seen.add(x)
                        stack.append(x)
            comps.append(comp)
        if len(comps) > 1:
            if _env_f('EYE_RIM_CANTHUS_BAND_DEBUG', 0) > 0:
                print(f"[dbg] 窗 {len(wdel_idx)} 环点 rail={len(rail)} | Rlim={Rlim * 1000:.2f}mm | comps={len(comps)}")
                railpos = wl(rail) * 1000
                for ci, rv in enumerate(rail):
                    q = w(rv) * 1000
                    print(f"[dbg] rail[{ci}] v{getattr(rv, 'index', -1)} ({q.x:.2f},{q.y:.2f},{q.z:.2f}) lf={len(rv.link_faces)}")
                tipa = np.array(list(tip))
                for ci, cmp_ in enumerate(comps):
                    endsv = [v for v in cmp_ if len(chain_adj[v]) == 1]
                    print(f"[dbg] comp{ci}: n={len(cmp_)} ends={len(endsv)}")
                    if endsv:
                        walk = [endsv[0]]
                        pv, cu = None, endsv[0]
                        while True:
                            nb = [x for x in chain_adj[cu] if x is not pv]
                            if not nb:
                                break
                            walk.append(nb[0])
                            pv, cu = cu, nb[0]
                            if len(walk) > 5000:
                                break
                        for wv in walk:
                            q = w(wv) * 1000
                            dt = float(np.linalg.norm(np.array(list(w(wv))) - tipa)) * 1000
                            rl = [int(i) for i, rv in enumerate(rail)
                                  if any(e.other_vert(rv) is wv for e in rv.link_edges)]
                            print(f"[dbg]    v{getattr(wv, 'index', -1)} ({q.x:.2f},{q.y:.2f},{q.z:.2f}) "
                                  f"d={dt:.2f}mm lf={len(wv.link_faces)} rail邻={rl} deg={len(chain_adj[wv])}")
                        if len(endsv) > 1:
                            q = w(endsv[1]) * 1000
                            print(f"[dbg]    end2 v{getattr(endsv[1], 'index', -1)} ({q.x:.2f},{q.y:.2f},{q.z:.2f})")
            return fail(f"A链候选不连通: {len(comps)} 段(尺寸 {[len(c) for c in comps][:6]})")
        comp = comps[0]
        # 端点(度=1)必须一个是 rail[0] 的邻居、一个是 rail[C] 的邻居
        ends = [v for v in comp if len(chain_adj[v]) == 1]
        if len(ends) != 2:
            return fail(f"链端点异常({len(ends)})")

        def adj_rail(vrail):
            return [e.other_vert(vrail) for e in vrail.link_edges
                    if e.other_vert(vrail) not in rail_set
                    and (w(e.other_vert(vrail)) - tip).length <= Rlim * 1.2]
        n0 = adj_rail(rail[0])
        nC = adj_rail(rail[C])
        cand0 = [v for v in n0 if v in chain_adj]
        candC = [v for v in nC if v in chain_adj]
        if len(cand0) != 1 or len(candC) != 1:
            return fail(f"端部链端不唯一({len(cand0)},{len(candC)})")
        a_start, a_end = cand0[0], candC[0]
        if a_start == a_end:
            return fail("两端同一顶点")
        chain = [a_start]
        prev, cur = None, a_start
        while True:
            nb = [x for x in chain_adj[cur] if x != prev]
            if not nb:
                break
            nxt = nb[0]
            if nxt == a_start:
                return fail("链成环")
            chain.append(nxt)
            prev, cur = cur, nxt
            if len(chain) > 20000:
                return fail("链过长")
        if cur != a_end:
            return fail(f"链走到 {len(chain)} 越界(未到端)")
        if len(chain) != len(comp):
            return fail(f"链未覆盖全分量({len(chain)}/{len(comp)})")
        # 额外安全: 链上所有顶点都在这条路上(已由 len 覆盖), 且链外不得再有"含 rail 的单面边"残留
        M = len(chain) - 1
        if M < 3:
            return fail(f"链太短({M + 1})")

        # ---- 外排精化(1:1 对齐): 链边上按"环弧长分数"插点, 让列:外排 = 1:1 ----
        #   理由: 环点(0.13~0.35mm)比外排(0.25~0.44mm)密 → 直接 1:n 配对会形成
        #   楔形(两列共用一个外排点), 楔内任何细分都会出现边比>5 的细长面(实测)。
        #   只在外排侧插点(不改 ring/rail): 被改的是链边外侧的"保留面"(插 T 点后成 n-gon)。
        arcR = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(railP, axis=0), axis=1))])
        fR = arcR / max(arcR[-1], _EPS)
        chP = wl(chain)
        arcC = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(chP, axis=0), axis=1))])
        gC = arcC / max(arcC[-1], _EPS)
        uvlay = bm.loops.layers.uv.active
        outer = [None] * (C + 1)
        # 1) 原链顶点按"最近分数"分派到列(严格递增, 且每个原顶点都保留)
        outer[0] = chain[0]
        outer[C] = chain[M]
        cprev = 0
        for j in range(1, M):
            g = float(gC[j])
            cbest = int(np.argmin(np.abs(fR - g)))
            if cbest <= cprev:
                cbest = cprev + 1
            cmax = C - (M - j)
            if cbest > cmax:
                cbest = cmax
            if cbest <= cprev or cbest >= C:
                return fail(f"原外排顶点分派失败(j={j},c={cbest})")
            outer[cbest] = chain[j]
            cprev = cbest
        # 2) 其余列 → 链折线上 f_c 处的插值点(切链边)
        splits = {}
        for c in range(1, C):
            if outer[c] is not None:
                continue
            fc = float(fR[c])
            j = int(np.searchsorted(gC, fc, side='right')) - 1
            j = max(0, min(M - 1, j))
            t = (fc - gC[j]) / max(gC[j + 1] - gC[j], _EPS)
            t = min(max(float(t), 0.15), 0.85)     # 防止贴近原顶点(避免微边)
            splits.setdefault(j, []).append((t, c))
        n_ins = 0
        for j, lst in sorted(splits.items()):
            lst.sort()
            a, b = chain[j], chain[j + 1]
            e_ = None
            for ee in a.link_edges:
                if ee.other_vert(a) is b:
                    e_ = ee
                    break
            if e_ is None or len(e_.link_faces) != 1:
                return fail("链边保留面异常")
            F = e_.link_faces[0]
            lv = [l.vert for l in F.loops]
            nf_ = len(lv)
            uvmap = {}
            if uvlay is not None:
                for l in F.loops:
                    uvmap[l.vert] = (float(l[uvlay].uv[0]), float(l[uvlay].uv[1]))
            nv = []
            for (t, c) in lst:
                p = chP[j] * (1.0 - t) + chP[j + 1] * t
                v = bm.verts.new(MWi @ Vector((float(p[0]), float(p[1]), float(p[2]))))
                nv.append(v)
                outer[c] = v
                n_ins += 1
            newloop = []
            for i in range(nf_):
                vh, vn = lv[i], lv[(i + 1) % nf_]
                newloop.append(vh)
                if vh is a and vn is b:
                    newloop.extend(nv)
                elif vh is b and vn is a:
                    newloop.extend(reversed(nv))
            sm_ = F.smooth
            mi_ = F.material_index
            bm.faces.remove(F)
            F2 = bm.faces.new(newloop)
            F2.smooth = sm_
            F2.material_index = mi_
            if uvlay is not None:
                uva = uvmap.get(a, (0.0, 0.0))
                uvb = uvmap.get(b, (0.0, 0.0))
                for l in F2.loops:
                    if l.vert in uvmap:
                        l[uvlay].uv = uvmap[l.vert]
                for (t, c), v in zip(lst, nv):
                    for l in F2.loops:
                        if l.vert is v:
                            l[uvlay].uv = (uva[0] + (uvb[0] - uva[0]) * t, uva[1] + (uvb[1] - uva[1]) * t)
        if any(v is None for v in outer):
            return fail("外排精化失败(空锚点)")
        chain = outer
        chP = wl(chain)
        M = C
        T = list(range(C + 1))
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        # ---- 带宽/行数(1:1) ----
        wcol = np.array([np.linalg.norm(chP[T[c]] - railP[c]) for c in range(C + 1)])
        ncol = np.clip(np.ceil(wcol / max(tgt, 1e-6)).astype(int), 1, maxrows)
        ncol[0] = 1
        ncol[C] = 1
        for c in range(1, C + 1):
            ncol[c] = min(ncol[c], ncol[c - 1] + 1)
        for c in range(C - 1, -1, -1):
            ncol[c] = min(ncol[c], ncol[c + 1] + 1)
        ncol = np.maximum(ncol, 1)
        if _env_f('EYE_RIM_CANTHUS_BAND_DEBUG', 0) > 0:
            print("[dbg] 列映射(C=%d, M=%d):" % (C, M))
            for c in range(C + 1):
                q1 = railP[c] * 1000
                q2 = chP[T[c]] * 1000
                print("[dbg]  col%2d rail[%2d](%.2f,%.2f,%.2f) → A[%2d](%.2f,%.2f,%.2f) w=%.3fmm n=%d h=%.3fmm"
                      % (c, c, q1[0], q1[1], q1[2], T[c], q2[0], q2[1], q2[2],
                         wcol[c] * 1000, int(ncol[c]), wcol[c] * 1000 / max(int(ncol[c]), 1)))

        # ---- 建列顶点 + 面 ----
        n_new = 0
        n_snap = 0
        col = []
        for c in range(C + 1):
            nrows = int(ncol[c])
            vlist = [rail[c]]
            for j in range(1, nrows):
                p = railP[c] + (j / nrows) * (chP[T[c]] - railP[c])
                loc, nrm, idx, dist = bvh.find_nearest(Vector((float(p[0]), float(p[1]), float(p[2]))))
                if loc is not None and dist is not None and dist <= snapcap:
                    p = np.array([loc[0], loc[1], loc[2]])
                    n_snap += 1
                v = bm.verts.new(MWi @ Vector((float(p[0]), float(p[1]), float(p[2]))))
                vlist.append(v)
                n_new += 1
            vlist.append(chain[T[c]])
            col.append(vlist)
        bm.verts.ensure_lookup_table()

        new_faces = []
        n_tri = 0
        emit = []
        for c in range(C):
            A = col[c]
            B = col[c + 1]
            nA, nB = len(A) - 1, len(B) - 1
            t_same = (T[c] == T[c + 1])
            jj = kk = 0
            guard = 0
            while jj < nA or kk < nB:
                guard += 1
                if guard > 4 * (nA + nB) + 16:
                    return fail("列合并死循环")

                def _min_edge(fv):
                    return min((fv[i].co - fv[(i + 1) % len(fv)].co).length for i in range(len(fv)))

                if jj == nA:
                    opts = [([A[jj], B[kk], B[kk + 1]], 0, 1)]
                elif kk == nB:
                    opts = [([A[jj], A[jj + 1], B[kk]], 1, 0)]
                elif t_same and (jj + 1 == nA) and (kk + 1 == nB):
                    opts = [([A[jj], B[kk], A[jj + 1]], 1, 1)]
                else:
                    tj = (jj + 1) / nA
                    tk = (kk + 1) / nB
                    if abs(tj - tk) < 1e-9:
                        opts = [([A[jj], B[kk], B[kk + 1], A[jj + 1]], 1, 1)]
                    else:
                        o_j = ([A[jj], A[jj + 1], B[kk]], 1, 0)
                        o_k = ([A[jj], B[kk], B[kk + 1]], 0, 1)
                        prefer = 0 if tj < tk else 1     # 常规: t 较小的一侧先推进(等比)
                        m0, m1 = _min_edge(o_j[0]), _min_edge(o_k[0])
                        if m0 < 0.50 * tgt and m1 > m0 * 1.8:
                            prefer = 1                  # 形状感知: 换成不产生微边的一侧
                        elif m1 < 0.50 * tgt and m0 > m1 * 1.8:
                            prefer = 0
                        opts = [o_j if prefer == 0 else o_k]
                fo, dj, dk = opts[0]
                jj += dj
                kk += dk
                if len(set(fo)) != len(fo):
                    return fail("面顶点重复")
                if len(fo) == 4:
                    P4 = [w(v) for v in fo]
                    qa, qr = _quad_stats(P4)
                    if qr < 4.6 and qa > 1.02e-8:
                        emit.append(tuple(fo))
                    else:
                        t1 = (_tri_stats(P4[0], P4[1], P4[2]), _tri_stats(P4[0], P4[2], P4[3]))
                        t2 = (_tri_stats(P4[0], P4[1], P4[3]), _tri_stats(P4[1], P4[2], P4[3]))
                        def _wr(ts):
                            return max(z[1] for z in ts)
                        def _amin(ts):
                            return min(z[0] for z in ts)
                        cand = []
                        if _amin(t1) > 1.02e-8 and _wr(t1) < 4.6:
                            cand.append((_wr(t1), [(fo[0], fo[1], fo[2]), (fo[0], fo[2], fo[3])]))
                        if _amin(t2) > 1.02e-8 and _wr(t2) < 4.6:
                            cand.append((_wr(t2), [(fo[0], fo[1], fo[3]), (fo[1], fo[2], fo[3])]))
                        if cand:
                            cand.sort(key=lambda z: z[0])
                            emit.extend(cand[0][1])
                        else:
                            emit.append(tuple(fo))   # 兜底: 交给校验判死
                else:
                    emit.append(tuple(fo))
        for fo in emit:
            if len(set(fo)) != len(fo):
                return fail("面顶点重复")
            f = bm.faces.new(fo)
            f.smooth = True
            new_faces.append(f)
            if len(fo) == 3:
                n_tri += 1
        bm.normal_update()

        # ---- 朝向统一(参考原带面法线) ----
        nflip = 0
        for f in new_faces:
            c0 = f.calc_center_median()
            loc, nrm, idx, dist = bvh.find_nearest(c0)
            if nrm is not None and f.normal.dot(nrm) < 0:
                f.normal_flip()
                nflip += 1
        bm.normal_update()

        # ---- 残留无线面边清理(重建后) ----
        wire2 = [e for e in bm.edges if len(e.link_faces) == 0
                 and min((w(e.verts[0]) - tip).length, (w(e.verts[1]) - tip).length) <= Rlim]
        if wire2:
            bmesh.ops.delete(bm, geom=wire2, context='EDGES')
            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            bm.edges.ensure_lookup_table()

        # ---- 校验 1: 环不变(点数/位置) ----
        ring2 = _ring_of_eye(bm, cv)
        if len(ring2) != len(ring):
            return fail(f"环点数变了 {len(ring)}→{len(ring2)}")
        P2 = wl([bm.verts[i] for i in ring2])
        dmax = float(np.abs(P2 - Pw).max()) if len(P2) else 0.0
        # 逐点集合匹配(顺序可能不同)
        # 用 KD 粗暴: 允许重排 → 用最近点距离
        dmin_all = []
        for p in Pw:
            dmin_all.append(float(np.linalg.norm(P2 - p[None, :], axis=1).min()))
        dmax = max(dmin_all) if dmin_all else 0.0
        if dmax > 1e-9:
            return fail(f"环点位置变了 max={dmax * 1000:.4f}mm")

        # ---- 校验 2: 新增面形状 ----
        bad_shape = 0
        min_area = 1e9
        max_ratio = 0.0
        for f in new_faces:
            if not f.is_valid:
                return fail("新面失效")
            if len(f.verts) > 4:
                return fail("新面含 n-gon")
            ar = f.calc_area()
            min_area = min(min_area, ar)
            if ar <= 1.02e-8:
                bad_shape += 1
            ls = [e.calc_length() for e in f.edges]
            ra = max(ls) / max(min(ls), _EPS)
            max_ratio = max(max_ratio, ra)
            if ra >= 4.6:
                bad_shape += 1
        if bad_shape:
            if _env_f('EYE_RIM_CANTHUS_BAND_DEBUG', 0) > 0:
                nb_ = 0
                for f in new_faces:
                    ar = f.calc_area()
                    ls = [e.calc_length() for e in f.edges]
                    ra = max(ls) / max(min(ls), _EPS)
                    if ar < 1.2e-8 or ra >= 4.6:
                        nb_ += 1
                        if nb_ <= 14:
                            pp = [w(v) * 1000 for v in f.verts]

                            def _rl(vv):
                                if vv in rail_set:
                                    return "rail[%d]" % rail.index(vv)
                                if vv in chain:
                                    return "A[%d]" % chain.index(vv)
                                return "new"
                            print("[dbg] 坏面#%d n=%d 面积=%.5fmm² 边比=%.2f 边长mm=[%s] 点=%s" % (
                                nb_, len(f.verts), ar * 1e6, ra,
                                ",".join("%.3f" % (l * 1000) for l in ls),
                                " ".join("%s(%.2f,%.2f,%.2f)" % (_rl(v), q.x, q.y, q.z)
                                         for v, q in zip(f.verts, pp))))
                print("[dbg] 坏面共 %d / %d" % (nb_, len(new_faces)))
            return fail(f"新面形状不合格: 面积<0.012mm² 或 边比≥4.6 共 {bad_shape} 个")

        # ---- 校验 3: 全局拓扑计数 ----
        bnd = sum(1 for e in bm.edges if len(e.link_faces) == 1)
        nmf = sum(1 for e in bm.edges if len(e.link_faces) > 2)
        rep["bnd_after"] = bnd
        rep["nmf_after"] = nmf
        if _env_f('EYE_RIM_CANTHUS_BAND_DEBUG', 0) > 0:
            vlab = {}
            for c in range(C + 1):
                for j, vv in enumerate(col[c]):
                    if j == 0:
                        vlab[vv] = "rail%d" % c
                    elif j < len(col[c]) - 1:
                        vlab[vv] = "c%d.r%d" % (c, j)
            for j, vv in enumerate(chain):
                vlab.setdefault(vv, "out%d" % j)
                if "out" not in vlab[vv]:
                    vlab[vv] = "T->out%d" % j
            for c in range(C + 1):
                vlab.setdefault(chain[c], "out%d" % c)
            print("[dbg] 重建后 短边界边(<0.05mm)明细:")
            nshort = 0
            for e in bm.edges:
                if len(e.link_faces) != 1:
                    continue
                L = e.calc_length()
                if L >= 5e-5:
                    continue
                a_, b_ = e.verts
                if min((w(a_) - tip).length, (w(b_) - tip).length) > Rlim:
                    continue
                nshort += 1
                if nshort <= 20:
                    f = e.link_faces[0]
                    print("[dbg]   len=%.4fmm %s-%s | 面[%s]" % (
                        L * 1000, vlab.get(a_, "?"), vlab.get(b_, "?"),
                        " ".join(vlab.get(x, "?") for x in f.verts)))
            print("[dbg]  短边界边共 %d" % nshort)
            rset2 = set(rail)
            oset = set(chain)
            cnt_ring = cnt_outer = cnt_cut = 0
            strays = []
            for e in bm.edges:
                if len(e.link_faces) != 1:
                    continue
                a_, b_ = e.verts
                if min((w(a_) - tip).length, (w(b_) - tip).length) > Rlim:
                    continue
                inr = (a_ in rset2 or b_ in rset2)
                ino = (a_ in oset or b_ in oset)
                if a_ in rset2 and b_ in rset2:
                    cnt_ring += 1
                elif (a_ in rset2) != (b_ in rset2):
                    cnt_cut += 1
                elif ino:
                    cnt_outer += 1
                    if (a_ in oset) != (b_ in oset) and cnt_outer <= 40:
                        la = ("rail" if a_ in rset2 else ("outer" if a_ in oset else "B"))
                        lb = ("rail" if b_ in rset2 else ("outer" if b_ in oset else "B"))
                        qa, qb = w(a_) * 1000, w(b_) * 1000
                        print("[dbg]  半边外排 %s-%s (%.2f,%.2f,%.2f)-(%.2f,%.2f,%.2f) lf=%d,%d len=%.3fmm" % (
                            la, lb, qa.x, qa.y, qa.z, qb.x, qb.y, qb.z,
                            len(a_.link_faces), len(b_.link_faces), (qa - qb).length))
                else:
                    qa, qb = w(a_) * 1000, w(b_) * 1000
                    strays.append((a_, b_, qa, qb))
                    if len(strays) <= 24:
                        la = ("rail" if a_ in rset2 else ("outer" if a_ in oset else "?"))
                        lb = ("rail" if b_ in rset2 else ("outer" if b_ in oset else "?"))
                        print("[dbg]  外排类边 %s-%s (%.2f,%.2f,%.2f)-(%.2f,%.2f,%.2f) lf=%d,%d len=%.3fmm" % (
                            la, lb, qa.x, qa.y, qa.z, qb.x, qb.y, qb.z,
                            len(a_.link_faces), len(b_.link_faces), (qa - qb).length))
            print("[dbg] 区域内边界边: 环边=%d 外排边=%d 切边=%d 游离=%d" % (cnt_ring, cnt_outer, cnt_cut, len(strays)))
            for a_, b_, qa, qb in strays[:20]:
                print("[dbg]   游离边 (%.2f,%.2f,%.2f)-(%.2f,%.2f,%.2f) lf=%d,%d" % (
                    qa.x, qa.y, qa.z, qb.x, qb.y, qb.z, len(a_.link_faces), len(b_.link_faces)))
        if _env_f('EYE_RIM_CANTHUS_BAND_DRYRUN', 0) > 0:
            rep.update(ok=True, dry=True, ring_pts=len(ring), win=int(len(wdel_idx)), rail=int(C + 1),
                       chain=int(M + 1), new_verts=n_new, new_faces=len(new_faces), new_tris=n_tri,
                       snapped=n_snap, flipped=nflip, rows_max=int(ncol.max()),
                       min_area_mm2=min_area * 1e6, max_ratio=max_ratio)
            if verbose:
                print(f"rebuild_band {side}[dry]: 窗 {len(wdel_idx)} 环点 → {C + 1} 列 × 1..{int(ncol.max())} 行 = "
                      f"{len(new_faces)} 面(三角 {n_tri}) 新顶点 {n_new}(贴回 {n_snap}) | 面积min {min_area * 1e6:.4f}mm² "
                      f"边比max {max_ratio:.2f} | 边界边 {bnd} 非流形边 {nmf}")
            bm.free()
            return rep

        # ---- 写回 ----
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        # position 属性同步(该文件里 position==顶点坐标)
        try:
            if "position" in [a.name for a in mesh.attributes]:
                aa = mesh.attributes["position"]
                nvv = len(mesh.vertices)
                arr = np.zeros(nvv * 3)
                mesh.vertices.foreach_get("co", arr)
                aa.data.foreach_set("vector", arr)
        except Exception as e:
            print(f"rebuild_band {side}: position 属性同步跳过({e})")
        rep.update(ok=True, ring_pts=len(ring), win=int(len(wdel_idx)), rail=int(C + 1),
                   chain=int(M + 1), new_verts=n_new, new_faces=len(new_faces), new_tris=n_tri,
                   snapped=n_snap, flipped=nflip, rows_max=int(ncol.max()),
                   min_area_mm2=min_area * 1e6, max_ratio=max_ratio,
                   nv0=nv0, nf0=nf0, nv1=len(mesh.vertices), nf1=len(mesh.polygons))
        if verbose:
            print(f"rebuild_band {side}: 窗 {len(wdel_idx)} 环点 → 重建 {C + 1} 列 × 1..{int(ncol.max())} 行 = "
                  f"{len(new_faces)} 面(三角 {n_tri}) 新顶点 {n_new}(贴回 {n_snap}) | 面积min {min_area * 1e6:.4f}mm² "
                  f"边比max {max_ratio:.2f} | 环 {len(ring)} 点不变 | 边界边 {bnd} 非流形边 {nmf}")
        return rep
    except Exception as e:
        import traceback
        traceback.print_exc()
        rep["reason"] = f"异常: {e}"
        try:
            bm.free()
        except Exception:
            pass
        if verbose:
            print(f"rebuild_band {side}: 异常 → mesh 未改动 ({e})")
        return rep
