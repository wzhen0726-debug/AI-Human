# -*- coding: utf-8 -*-
"""
02 自交穿插清理 (2026-09-22 新增)
-----------------------------------------------------------------
背景: QuadRemesher 把"衣服壳 / 身体壳"在交界处重拓扑成单层封闭面时, 会在衣摆/袖口
这类折边处产生【双层近共面微折】与【绕向不一致面】。它们没有拓扑孔洞(边界边/非流形边
都是0), 但渲染时表现为尖角/台阶/发黑暗面 —— 用户报的"破面"。

根因归属(2026-09-22 实测, 局部自交对计数):
    大腿衣摆   高模=0  →  QR原始=34  →  QR+眼窝碗=39      ← QR 产生
    右眼窝外眦 高模=8  →  QR原始=0   →  QR+眼窝碗=1       ← 建碗产生
故清理放在 02: 哪个环节产生的, 就在哪个环节的输出上清掉。

判据(踩过坑):
    bvh.overlap(bvh) 是精确三角-三角相交, 不是 AABB 粗筛 —— 161k 面网格上只报几十对
    (若按 AABB 会把相邻面都报进来, 那是几十万对)。**共享顶点的相交对同样是缺陷**:
    折角恰恰发生在共享顶点/共享边处。故不加"排除相邻面"的过滤, 只去 i>=j 的重复对。
    (早先版本加了共享顶点过滤 → 修完后审计仍报 14 对 = 判据自盲, 已纠正。)

做法(零硬编码, 全部自动):
    ① 全模型精确自交检测(严格判据) → 涉及三角面
    ② 按质心空间聚类(CLUSTER_MM) → 每簇 = 一处缺陷
    ③ 每簇: 顶点级微焊接, 距离由小到大逐档试, 取第一个"清零 **且卫生不退化**"的档;
            焊接后删同顶点集重复面(非流形边的主因); 卫生退化 → 该档回退试下一档;
            全档失败 → 限幅平滑兜底(单顶点位移硬上限 RELAX_CAP_MM)
    ④ 绕向修复 v2(2026-09-30 ab14): 并查集奇偶解 + 每连通块参考/多数定向 → 坏边残留=0(旧版
           "坏边两侧一起翻"会波浪扩散不收敛, 已废, 见 logs/_ab14/AB14_REPORT.txt)
        ⑤ 全模型复检(最多 MAX_ROUNDS 轮), 残留如实报告

⚠ 卫生硬指标: 清理不得让 非流形边/退化面 变多, 否则该档回退 —— 为了"眼见好看"把网格
   改坏是本管线的禁令(修复引入新错误=全否)。

用法:
    from selfint_clean import clean_self_intersections
    rep = clean_self_intersections(obj)      # 就地改 obj.data
"""
import numpy as np
import bmesh
from mathutils.bvhtree import BVHTree

# ---- 尺寸活性(2026-09-23, 用户要求"参数都必须是活的") ----
# 本模块所有毫米级阈值都按模型 bbox 比例算, 不再写死。基准 REF_BBOX_MAX_M 取自当前角色实测
# (1.809m, 与 04_bake.py 的 CAGE_BODY=bbox_max*0.011 同口径), 因此下列比例与历史固定值【数值等价】:
#   CLUSTER_MM 6.0mm / WELD_LADDER 0.8~5.0mm / RELAX_CAP_MM 0.3mm / 簇心间距 25mm
# 换体型(孩童/女人/老人)或换比例尺时自动缩放 → 不必回来改常数。
REF_BBOX_MAX_M = 1.808408   # 实测: 03_auto_uv.blend 低模 bbox_max(x向/臂展), 2026-09-23 量取
CLUSTER_RATIO = 6.0 / (REF_BBOX_MAX_M * 1000.0)
WELD_LADDER_RATIO = tuple(v / (REF_BBOX_MAX_M * 1000.0) for v in
                          (0.8, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0))
RELAX_CAP_RATIO = 0.3 / (REF_BBOX_MAX_M * 1000.0)
CENTER_DIST_RATIO = 25.0 / (REF_BBOX_MAX_M * 1000.0)

# 下列为"当前模型"下的实际值, 由 _apply_size(obj) 按 bbox 实时刷新(FALLBACK = 基准体型下的值)
CLUSTER_MM = 6.0
WELD_LADDER = (0.0008, 0.0012, 0.0015, 0.0020, 0.0025, 0.0030, 0.0040, 0.0050)  # m
RELAX_CAP_MM = 0.3        # 兜底平滑的单顶点位移硬上限
MIN_CENTER_DIST_MM = 25.0
MAX_ROUNDS = 4


def _apply_size(obj):
    """按 obj 的世界 bbox 刷新毫米级阈值(返回尺度系数, 1.0 = 基准体型)。"""
    global CLUSTER_MM, WELD_LADDER, RELAX_CAP_MM, MIN_CENTER_DIST_MM
    from mathutils import Vector
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    span = max(max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3))
    sc = float(span) / REF_BBOX_MAX_M
    CLUSTER_MM = CLUSTER_RATIO * REF_BBOX_MAX_M * 1000.0 * sc      # mm
    # ⚠ WELD_LADDER 单位是【米】(见文件头常量注释): 比例已是 mm/mm, 故乘基准米数即可, 不能再 ×1000
    WELD_LADDER = tuple(r * REF_BBOX_MAX_M * sc for r in WELD_LADDER_RATIO)   # m
    RELAX_CAP_MM = RELAX_CAP_RATIO * REF_BBOX_MAX_M * 1000.0 * sc
    MIN_CENTER_DIST_MM = CENTER_DIST_RATIO * REF_BBOX_MAX_M * 1000.0 * sc
    return sc


def _tri_array(me):
    """三角索引 + 顶点坐标 —— **与验证脚本 _audit_defects2.py 完全同口径**(按多边形扇形三角化)。
    踩过: 模块用 loop_triangles、审计用扇形 → 同一网格一边报3对一边报14对, 弃。
    修复判据必须与验证判据同口径, 否则等于自证。"""
    nv = len(me.vertices)
    co = np.empty(nv * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    # AB17J P1(2026-10-08): 逐面 Python 循环 → numpy 扇形三角化(逐位等价):
    #   面序/每面内 k 序与旧循环完全一致 → tris 数组逐元素相同; 161k 面 0.2s→~5ms,
    #   而本函数在自交清理里被调用近百次(实测累计 19.4s)。
    npo = len(me.polygons); nl = len(me.loops)
    if npo == 0 or nl == 0:
        return np.array([], dtype=np.int64), co
    LS = np.empty(npo, dtype=np.int64); me.polygons.foreach_get("loop_start", LS)
    LT = np.empty(npo, dtype=np.int64); me.polygons.foreach_get("loop_total", LT)
    LV = np.empty(nl, dtype=np.int64); me.loops.foreach_get("vertex_index", LV)
    F = np.repeat(np.arange(npo, dtype=np.int64), LT)
    pos = np.arange(nl, dtype=np.int64) - LS[F]
    m = (pos >= 1) & (pos <= (LT[F] - 2))
    idx = np.where(m)[0]
    if len(idx) == 0:
        return np.array([], dtype=np.int64), co
    v0 = LV[LS[F[idx]]]
    tris = np.stack((v0, LV[idx], LV[idx + 1]), axis=1)
    return tris.astype(np.int64), co


def _self_pairs_from(tris, co):
    """严格自交对(精确相交; 不排除共享顶点)"""
    if len(tris) < 4:
        return []
    used = np.unique(tris)
    remap = {int(v): k for k, v in enumerate(used)}
    pts = [tuple(map(float, co[int(v)])) for v in used]
    t2 = [tuple(remap[int(v)] for v in t) for t in tris]
    bvh = BVHTree.FromPolygons(pts, t2, all_triangles=True)
    return [(i, j) for i, j in bvh.overlap(bvh) if i < j]


def _self_pairs(me):
    me.calc_loop_triangles()
    tris, co = _tri_array(me)
    return _self_pairs_from(tris, co)


def _hygiene(obj):
    """卫生指标: 边界边 / 非流形边 / 退化面 / 同顶点集重复面"""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bd = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    nb = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    dg = sum(1 for f in bm.faces if f.calc_area() < 1e-11)
    seen, dup = set(), 0
    for f in bm.faces:
        k = tuple(sorted(v.index for v in f.verts))
        if k in seen:
            dup += 1
        else:
            seen.add(k)
    bm.free()
    return {"边界边": bd, "非流形边": nb, "退化面": dg, "重复面": dup}


def _drop_dup_faces(obj):
    """删同顶点集的重复面(焊接常产生) —— 非流形边的主要来源"""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    seen, dead = set(), []
    for f in bm.faces:
        k = tuple(sorted(v.index for v in f.verts))
        if k in seen:
            dead.append(f)
        else:
            seen.add(k)
    n = len(dead)
    if n:
        bmesh.ops.delete(bm, geom=dead, context='FACES')
        bm.to_mesh(obj.data)
        obj.data.update()
    bm.free()
    return n


def _cluster_keys(pairs, tris, co, min_center_dist_mm=None):
    if min_center_dist_mm is None:
        min_center_dist_mm = MIN_CENTER_DIST_MM
    """当前所有缺陷簇的"地点指纹"(四舍五入的中心), 用于判断某次修复有没有在别处新生缺陷。"""
    if not pairs:
        return []
    cl = _clusters(tris, co, pairs, min_center_dist_mm)
    return [tuple(round(v, 2) for v in c["center"]) for c in cl]


def _shortest_center_dist(keys, center):
    if not keys:
        return 1e9
    return min(np.linalg.norm(np.array(k) - np.array(center)) for k in keys)


def _clusters(tris, co, pairs, thr_mm=None):
    if thr_mm is None:
        thr_mm = CLUSTER_MM
    """把自交涉及的三角按质心距离聚类 → [ {'tris':[...], 'center':(x,y,z), 'n':对数} ]"""
    inv = sorted({t for p in pairs for t in p})
    if not inv:
        return []
    cen = co[tris[inv]].mean(axis=1)
    parent = list(range(len(inv)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    thr = thr_mm / 1000.0
    for a in range(len(inv)):
        for b in range(a + 1, len(inv)):
            if np.linalg.norm(cen[a] - cen[b]) <= thr:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[rb] = ra
    groups = {}
    for k in range(len(inv)):
        groups.setdefault(find(k), []).append(inv[k])
    out = []
    for g in groups.values():
        cc = co[tris[g]].reshape(-1, 3).mean(axis=0)
        n = sum(1 for i, j in pairs if i in g or j in g)
        out.append({"tris": sorted(g), "center": (float(cc[0]), float(cc[1]), float(cc[2])), "n": n})
    out.sort(key=lambda d: -d["n"])
    return out


def _local_count(obj, center, half):
    """盒内严格自交对数(与全模型同一判据)"""
    me = obj.data
    me.calc_loop_triangles()
    tris, co = _tri_array(me)
    c = np.array(center)
    inside = np.all(np.abs(co - c) < half, axis=1)
    # AB17J P1(2026-10-08): 逐面 any() Python 循环 → 布尔矩阵 any(axis=1)(逐位等价:
    #   同一 inside 布尔向量 + 同一 tris 行 → 选中行集合与顺序相同; 0.2s→~3ms,
    #   每簇每档都会调用(实测累计 35s 级)。
    if len(tris) == 0:
        return 0
    sel = np.where(inside[tris].any(axis=1))[0]
    if len(sel) < 4:
        return 0
    return len(_self_pairs_from(tris[sel], co))


def _weld(obj, vert_ids, dist):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    vs = [bm.verts[i] for i in vert_ids if i < len(bm.verts)]
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=vs, dist=dist)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return n0 - len(obj.data.vertices)


def _relax(obj, vert_ids, cap_mm=None, rounds=10, factor=0.3):
    if cap_mm is None:
        cap_mm = RELAX_CAP_MM
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    V = set(i for i in vert_ids if i < len(bm.verts))
    for _ in range(2):                        # 扩两圈邻居, 免得局部塌坑
        nb = set()
        for vi in V:
            v = bm.verts[vi]
            for e in v.link_edges:
                nb.add(e.other_vert(v).index)
        V |= nb
    vs = [bm.verts[i] for i in V]
    orig = {v.index: v.co.copy() for v in vs}
    cap = cap_mm / 1000.0
    for _ in range(rounds):
        bmesh.ops.smooth_vert(bm, verts=vs, factor=factor,
                              use_axis_x=True, use_axis_y=True, use_axis_z=True)
        for v in vs:
            d = v.co - orig[v.index]
            if d.length > cap:
                v.co = orig[v.index] + d.normalized() * cap
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


# =============================================================================================
# 绕向修复 v2 (2026-09-30 ab14 重写; 旧版"把坏边两侧所有面一起翻"= 相对绕向不变 → 坏边修不掉、
#   每轮向外扩散一圈、计数器只涨不回落(实测 721,539 / 3,898,733 次翻转后仍残留 9,450 / 30,911
#   面朝向错误, 见 logs/_ab14/AB14_REPORT.txt)。
#   v2 原理(确定性: 同输入必得同输出; 与遍历顺序无关):
#     ① 并查集(带奇偶)解每面 flip 奇偶 p: 2面共享边 f2 要求 p(f2)=p(f1) XOR s(该边当前是否同向)
#        → 解完内部边全一致, 坏边残留必=0(不可定向冲突如实计数);
#     ② 每连通块整体朝向: 优先高模参考最近面法线面积加权投票; 无参考 → "修复前原朝向"面积多数表决;
#     ③ 只对 final_flip 面做 reverse_faces(不新建/不删面, 几何零改变)。
#   调用: _fix_winding(obj) 兼容旧签名(无参考=多数表决); 需参考时传 ref_bvh/ref_matrix_world。
# =============================================================================================
_WF_REF_TOL_RATIO = 0.002   # 参考可信距离 = 目标 bbox 对角线 × 0.002 (与 02_qr_auto 8.5b 同口径)
_WF_AMBIG_DOT = 0.10        # |dot| <= 该值 = 模糊(掠射/锐折), 不计入"参考不一致"


def _wf_arrays(me):
    """面/环/边结构数组: 每 loop 沿其边的方向 d + 边→loop 分组"""
    nf, nl, ne, nv = len(me.polygons), len(me.loops), len(me.edges), len(me.vertices)
    LS = np.empty(nf, dtype=np.int64); me.polygons.foreach_get("loop_start", LS)
    LT = np.empty(nf, dtype=np.int64); me.polygons.foreach_get("loop_total", LT)
    L = np.empty(nl, dtype=np.int64); me.loops.foreach_get("vertex_index", L)
    LE = np.empty(nl, dtype=np.int64); me.loops.foreach_get("edge_index", LE)
    E = np.empty(ne * 2, dtype=np.int64); me.edges.foreach_get("vertices", E); E = E.reshape(-1, 2)
    F = np.repeat(np.arange(nf, dtype=np.int64), LT)
    nxt = np.empty(nl, dtype=np.int64)
    if nl:
        nxt[:-1] = L[1:]; nxt[-1] = L[0]
        lm = np.zeros(nl, dtype=bool); lm[LS + LT - 1] = True
        nxt[lm] = L[LS[F[lm]]]
    d = ((L == E[LE, 0]) & (nxt == E[LE, 1])).astype(np.int8) if nl else np.zeros(0, dtype=np.int8)
    order = np.argsort(LE, kind="stable")
    start = np.searchsorted(LE[order], np.arange(ne))
    cnt = np.bincount(LE, minlength=ne)
    return {"nf": nf, "nl": nl, "ne": ne, "nv": nv, "LS": LS, "LT": LT, "L": L, "LE": LE,
            "E": E, "F": F, "d": d, "order": order, "start": start, "cnt": cnt}


def _wf_bad_edges(A):
    """2面共享边中两面同向的 = 绕向不一致(坏)边"""
    two = np.where(A["cnt"] == 2)[0]
    l0 = A["order"][A["start"][two]]
    l1 = A["order"][A["start"][two] + 1]
    f0, f1 = A["F"][l0], A["F"][l1]
    ok = f0 != f1
    d0, d1 = A["d"][l0], A["d"][l1]
    return {"two": two, "f0": f0, "f1": f1, "ok": ok, "d0": d0, "d1": d1, "bad": ok & (d0 == d1)}


def _wf_solve_parity(A):
    """带奇偶并查集: p(f2) = p(f1) XOR s → (p 每面 0/1, roots, 不可定向冲突数)
    find 返回 (root, p(x) XOR p(root)) —— 顺序勿反, 调用方按 root 比较/挂树"""
    B = _wf_bad_edges(A)
    nf = A["nf"]
    if nf == 0:
        return np.zeros(0, dtype=np.int8), np.zeros(0, dtype=np.int64), 0
    parent = list(range(nf)); rnk = [0] * nf; par = [0] * nf

    def find(x):
        r = 0
        while parent[x] != x:
            r ^= par[x]; x = parent[x]
        return x, r

    conflict = 0
    for k in np.where(B["ok"])[0]:
        a = int(B["f0"][k]); b = int(B["f1"][k])
        s = 0 if B["d0"][k] != B["d1"][k] else 1
        ra, xa = find(a); rb, xb = find(b)
        if ra == rb:
            if (xa ^ xb) != s:
                conflict += 1
            continue
        if rnk[ra] < rnk[rb]:
            parent[ra] = rb; par[ra] = xa ^ xb ^ s
        else:
            parent[rb] = ra; par[rb] = xa ^ xb ^ s
            if rnk[ra] == rnk[rb]:
                rnk[ra] += 1
    p = np.empty(nf, dtype=np.int8); roots = np.empty(nf, dtype=np.int64)
    for k in range(nf):
        r, x = find(k); roots[k] = r; p[k] = x
    return p, roots, conflict

def _wf_ref_probe(obj, ref_bvh, ref_matrix_world, tol):
    """面(世界系)法线 vs 参考最近面法线(转世界) 的 dot; 返回 (dot数组, 可信mask, 查询点(ref局部), 面法线世界系)"""
    me = obj.data
    nf = len(me.polygons)
    mw = np.array(obj.matrix_world)
    R = mw[:3, :3]
    nrm = np.empty(nf * 3); me.polygons.foreach_get("normal", nrm); nrm = nrm.reshape(-1, 3)
    cen = np.empty(nf * 3); me.polygons.foreach_get("center", cen); cen = cen.reshape(-1, 3)
    nw = nrm @ R.T
    nw /= np.maximum(np.linalg.norm(nw, axis=1, keepdims=True), 1e-12)
    cw = cen @ R.T + mw[:3, 3]
    if ref_matrix_world is None:
        rinv = np.eye(4); Rref = np.eye(3)
    else:
        rm = np.array(ref_matrix_world)
        rinv = np.linalg.inv(rm); Rref = rm[:3, :3]
    q = cw @ rinv[:3, :3].T + rinv[:3, 3]
    dot = np.full(nf, np.nan); trust = np.zeros(nf, dtype=bool)
    for k in range(nf):
        h = ref_bvh.find_nearest(tuple(q[k]))
        if h[0] is None or h[3] > tol:
            continue
        rn = np.array(h[1]) @ Rref.T
        nn = np.linalg.norm(rn)
        if nn < 1e-12:
            continue
        dot[k] = float(np.dot(nw[k], rn / nn)); trust[k] = True
    return dot, trust, q, nw


def _wf_ref_violations(ref_bvh, nw, dot, trust, q, agree_mm=2.0):
    """宽容口径违规面: 最近参考面反对(dot < -_WF_AMBIG_DOT) 且在 agree_mm 邻域内找不到任何赞成面(dot>0)。
    折缝/夹层处(高模在 <agree_mm 内二次折返)参考本身二义 → 不算违规; 真翻转(局部参考一致反对)必被抓。"""
    bad = np.where(trust & (dot < -_WF_AMBIG_DOT))[0]
    n_viol = 0
    for k in bad:
        hits = ref_bvh.find_nearest_range(tuple(q[k]), agree_mm / 1000.0)
        agree = False
        for hh in hits:
            rn = np.array(hh[1]); nn = np.linalg.norm(rn)
            if nn < 1e-12:
                continue
            if float(np.dot(nw[k], rn / nn)) > 0.0:
                agree = True
                break
        if not agree:
            n_viol += 1
    return n_viol

def _wf_ref_tol(obj, ref_tol_mm=None):
    if ref_tol_mm is not None:
        return ref_tol_mm
    from mathutils import Vector
    pts = np.array([obj.matrix_world @ Vector(c) for c in obj.bound_box])
    diag = float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0)))
    return _WF_REF_TOL_RATIO * diag * 1000.0


def _fix_winding(obj, ref_bvh=None, ref_matrix_world=None, ref_tol_mm=None, report=None, verbose=True):
    """确定性绕向修复。返回实际改变面数(int); report 传 dict 则填详细报告。
    收敛保证: 修复后坏边残留必=0(仅计2面共享边)。ref_bvh=None 时按"修复前原朝向"面积多数表决。"""
    me = obj.data
    A = _wf_arrays(me)
    nf = A["nf"]
    B = _wf_bad_edges(A)
    n_bad0 = int(B["bad"].sum())
    p, roots, conflict = _wf_solve_parity(A)
    uniq, inv, cnts = np.unique(roots, return_inverse=True, return_counts=True) if nf else (np.zeros(0), np.zeros(0, dtype=np.int64), np.zeros(0))

    dot = trust = None
    if ref_bvh is not None and nf:
        tol = _wf_ref_tol(obj, ref_tol_mm) / 1000.0
        dot, trust, _q, _nw = _wf_ref_probe(obj, ref_bvh, ref_matrix_world, tol)

    areas = np.empty(nf); me.polygons.foreach_get("area", areas)
    s_p = np.where(p == 1, -1.0, 1.0)
    final_flip = np.zeros(nf, dtype=bool)
    isl_rep = []
    for i, n in enumerate(cnts):
        sel = np.where(inv == i)[0]
        basis = None; score = None
        if dot is not None:
            ts = sel[trust[sel]]
            if len(ts) > 0:
                score = float(np.sum(areas[ts] * s_p[ts] * dot[ts])); basis = "参考"
        if basis is None:
            score = float(np.sum(areas[sel] * s_p[sel])); basis = "多数表决(无参考/参考不可信)"
        blk_flip = 1 if score < 0 else 0
        final_flip[sel] = (p[sel] == (0 if blk_flip else 1))
        isl_rep.append({"面数": int(n), "奇偶1面": int(p[sel].sum()), "整体翻转": bool(blk_flip),
                        "依据": basis, "得分": round(score, 6),
                        "参考可信面": (int(trust[sel].sum()) if trust is not None else None)})
    isl_rep.sort(key=lambda d: -d["面数"])
    n_change = int(final_flip.sum())
    rep = {"面数": nf, "连通块数": int(len(cnts)), "不可定向冲突边": int(conflict),
           "坏边_修复前": n_bad0, "实际改变面数": n_change, "连通块": isl_rep[:12]}
    if dot is not None:
        rep["参考_可信面"] = int(trust.sum())
        rep["参考_不一致_修复前"] = int(np.nansum((dot < -_WF_AMBIG_DOT) & trust))
        rep["参考_模糊_修复前"] = int(np.nansum((np.abs(dot) <= _WF_AMBIG_DOT) & trust))
    if n_change > 0:
        bm = bmesh.new(); bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bmesh.ops.reverse_faces(bm, faces=[bm.faces[int(i)] for i in np.where(final_flip)[0]])
        bm.to_mesh(me); bm.free(); me.update()
        A2 = _wf_arrays(me)
        rep["坏边_修复后"] = int(_wf_bad_edges(A2)["bad"].sum())
        if dot is not None:
            dot2, trust2, _q2, _nw2 = _wf_ref_probe(obj, ref_bvh, ref_matrix_world, _wf_ref_tol(obj, ref_tol_mm) / 1000.0)
            rep["参考_不一致_修复后"] = int(np.nansum((dot2 < -_WF_AMBIG_DOT) & trust2))
            rep["参考_模糊_修复后"] = int(np.nansum((np.abs(dot2) <= _WF_AMBIG_DOT) & trust2))
    else:
        rep["坏边_修复后"] = n_bad0
        if dot is not None:
            rep["参考_不一致_修复后"] = rep["参考_不一致_修复前"]
            rep["参考_模糊_修复后"] = rep["参考_模糊_修复前"]
    rep["坏边残留"] = rep["坏边_修复后"]
    rep["参考不一致残留"] = rep.get("参考_不一致_修复后")
    if report is not None:
        report.clear(); report.update(rep)
    if verbose:
        print(f"[绕向v2] 面={nf:,} 坏边 {n_bad0}→{rep['坏边_修复后']} 改变面={n_change:,} "
              f"依据={isl_rep[0]['依据'] if isl_rep else '-'}"
              + (f" 参考不一致 {rep['参考_不一致_修复前']}→{rep['参考_不一致_修复后']}" if dot is not None else "")
              + f" {'✓' if rep['坏边_修复后'] == 0 else '✗'}", flush=True)
    return n_change


def winding_gate(obj, ref_bvh=None, ref_matrix_world=None, ref_tol_mm=None, verbose=True):
    """绕向体检(只读, 不改网格): 坏边 / 少数派面数 / 与参考不一致(强/宽容口径)。
    返回 dict。"""
    me = obj.data
    A = _wf_arrays(me)
    nf = A["nf"]
    B = _wf_bad_edges(A)
    p, roots, conflict = _wf_solve_parity(A)
    out = {"面数": nf, "坏边": int(B["bad"].sum()), "不可定向冲突边": int(conflict)}
    if nf:
        uniq, inv, cnts = np.unique(roots, return_inverse=True, return_counts=True)
        minority = 0
        for i, n in enumerate(cnts):
            k = int(p[np.where(inv == i)[0]].sum()); minority += min(k, int(n) - k)
        out["少数派面数"] = minority
        out["连通块数"] = int(len(cnts))
    else:
        out["少数派面数"] = 0; out["连通块数"] = 0
    if ref_bvh is not None and nf:
        tol = _wf_ref_tol(obj, ref_tol_mm) / 1000.0
        dot, trust, q, nw = _wf_ref_probe(obj, ref_bvh, ref_matrix_world, tol)
        out["参考不一致"] = int(np.nansum((dot < -_WF_AMBIG_DOT) & trust))
        out["参考模糊"] = int(np.nansum((np.abs(dot) <= _WF_AMBIG_DOT) & trust))
        out["参考可信面"] = int(trust.sum())
        # 宽容口径(硬门用): 折缝/夹层处参考二义不算违规 → 真翻转才计数
        out["参考不一致(宽容)"] = int(_wf_ref_violations(ref_bvh, nw, dot, trust, q))
    if verbose:
        print("[绕向体检] " + " ".join(f"{k}={v}" for k, v in out.items()), flush=True)
    return out


def clean_self_intersections(obj, verbose=True, ref_bvh=None, ref_matrix_world=None, ref_tol_mm=None):
    """就地清理 obj 的自交穿插 + 绕向不一致; 返回统计(中文键, 便于直接打印)
    ref_bvh/ref_matrix_world: 可选的高模参考(BVHTree.FromPolygons 数据拷贝 + 其 matrix_world)
      —— 传给绕向修复 v2 做"整体朝向"判据; 不传 = 按修复前原朝向多数表决(兼容旧调用)。"""
    sc = _apply_size(obj)
    if verbose:
        print(f"[selfint_clean] 尺寸活性: bbox_max/基准={sc:.4f} → 聚类{CLUSTER_MM:.2f}mm 焊接上限{WELD_LADDER[-1]*1000:.2f}mm 兜底{RELAX_CAP_MM:.3f}mm")
    """就地清理 obj 的自交穿插 + 绕向不一致; 返回统计(中文键, 便于直接打印)"""
    rep = {"对象": obj.name, "簇": [], "残留": None}
    rep["清理前"] = dict(面数=len(obj.data.polygons), 顶点数=len(obj.data.vertices), **_hygiene(obj))
    hy0 = rep["清理前"]

    for rnd in range(1, MAX_ROUNDS + 1):
        me = obj.data
        pairs = _self_pairs(me)
        if verbose:
            print(f"[自交清理] 第{rnd}轮: 全模型自交对={len(pairs)}", flush=True)
        if not pairs:
            break
        tris, co = _tri_array(me)
        cl = _clusters(tris, co, pairs)
        if verbose:
            print(f"[自交清理] 第{rnd}轮: 聚类 {len(cl)} 处", flush=True)
        for k, c in enumerate(cl):
            sub = tris[c["tris"]]
            pts = co[sub.reshape(-1)]
            half = float(np.max(pts.max(axis=0) - pts.min(axis=0))) / 2 + 0.004
            # ⚠ 每簇开始前按盒【重新取顶点】: 上一簇的焊接会删顶点使索引移位,
            #   沿用轮次开始时的旧索引 = 焊到错误的顶点上(踩过: 第2/3簇反复"焊了个寂寞")
            _in = np.all(np.abs(np.array([v.co[:] for v in obj.data.vertices]) - np.array(c["center"])) < half, axis=1)
            vid = sorted(int(i) for i in np.where(_in)[0])
            before = _local_count(obj, c["center"], half)
            snap = obj.data.copy()
            keys0 = _cluster_keys(pairs, tris, co)          # 修复前的缺陷地点集合
            how, dist_used, rem = "未成功", None, before
            for d in WELD_LADDER:
                _weld(obj, vid, d)
                _drop_dup_faces(obj)
                r1 = _local_count(obj, c["center"], half)
                hy = _hygiene(obj)
                # 守门: ①本簇清零 ②卫生不退化 ③没有在别处新生缺陷簇(>25mm 外的新簇 = 我们造的)
                if (r1 == 0 and hy["非流形边"] <= hy0["非流形边"] and hy["退化面"] <= hy0["退化面"]):
                    keys1 = _cluster_keys(_self_pairs(obj.data), *_tri_array(obj.data))
                    if [kk for kk in keys1
                        if _shortest_center_dist(keys0, kk) > 0.025
                        and np.linalg.norm(np.array(kk) - np.array(c["center"])) > 0.025]:
                        obj.data = snap.copy()
                        continue
                    how, dist_used, rem = "微焊接", d, r1
                    break
                obj.data = snap.copy()        # 该档破坏卫生/没清零/新生缺陷 → 回退试下一档
            if how == "未成功":               # 兜底: 限幅平滑
                _relax(obj, vid)
                _drop_dup_faces(obj)
                r1 = _local_count(obj, c["center"], half)
                hy = _hygiene(obj)
                keys1 = _cluster_keys(_self_pairs(obj.data), *_tri_array(obj.data))
                new_far = [kk for kk in keys1
                           if _shortest_center_dist(keys0, kk) > 0.025
                           and np.linalg.norm(np.array(kk) - np.array(c["center"])) > 0.025]
                if (r1 == 0 and hy["非流形边"] <= hy0["非流形边"] and hy["退化面"] <= hy0["退化面"]
                        and not new_far):
                    how, rem = "限幅平滑", r1
                else:
                    obj.data = snap.copy()
            rep["簇"].append({"轮": rnd, "中心mm": [round(x * 1000, 1) for x in c["center"]],
                              "自交对": before, "方式": how,
                              "焊接mm": None if dist_used is None else round(dist_used * 1000, 2),
                              "残留": rem})
            if verbose:
                print(f"   [{k+1}/{len(cl)}] 中心={np.round(np.array(c['center'])*1000,1)}mm "
                      f"{before}→{rem} 方式={how}"
                      f"{'' if dist_used is None else '('+str(round(dist_used*1000,2))+'mm)'} "
                      f"{'✓' if rem == 0 else '✗未清零'}", flush=True)

    rep["残留"] = len(_self_pairs(obj.data))
    # ④ 绕向修复 v2 (2026-09-30 ab14): 奇偶解 + 参考/多数定向 → 收敛且坏边残留必=0。
    #   旧字段"翻转面数"保持(现=实际改变面数); 新增"绕向报告"字段(坏边残留/参考不一致等)。
    _wrep = {}
    rep["翻转面数"] = _fix_winding(obj, ref_bvh=ref_bvh, ref_matrix_world=ref_matrix_world,
                                  ref_tol_mm=ref_tol_mm, report=_wrep, verbose=verbose)
    rep["绕向报告"] = _wrep
    rep["残留"] = len(_self_pairs(obj.data))
    rep["清理后"] = dict(面数=len(obj.data.polygons), 顶点数=len(obj.data.vertices), **_hygiene(obj))
    if verbose:
        print(f"[自交清理] 完成: 残留自交对={rep['残留']} 翻转面={rep['翻转面数']} "
              f"面 {rep['清理前']['面数']:,}→{rep['清理后']['面数']:,} "
              f"顶点 {rep['清理前']['顶点数']:,}→{rep['清理后']['顶点数']:,}", flush=True)
        print(f"[自交清理] 卫生 前={hy0} 后={rep['清理后']}", flush=True)
    return rep
