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
    ④ 绕向不一致边贪心翻转 → 0
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
    tris = []
    for p in me.polygons:
        vi = list(p.vertices)
        for k in range(1, len(vi) - 1):
            tris.append((vi[0], vi[k], vi[k + 1]))
    return np.array(tris, dtype=np.int64), co


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
    sel = [k for k, t in enumerate(tris) if any(inside[v] for v in t)]
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


def _fix_winding(obj):
    """绕向不一致边(相邻两面沿该边同向)贪心翻转; 返回翻转过的面数"""
    me = obj.data
    me.calc_loop_triangles()
    flipped = 0
    for _ in range(100):
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()      # 否则 bm.faces[i] 报 outdated internal index table
        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bad = set()
        for e in bm.edges:
            if len(e.link_faces) != 2:
                continue
            a, b = e.verts[0].index, e.verts[1].index
            dirs = []
            for f in e.link_faces:
                li = [v.index for v in f.verts]
                k = li.index(a)
                dirs.append(li[(k + 1) % len(li)] == b)
            if dirs[0] == dirs[1]:
                bad.add((a, b))
                bad.add((b, a))
        if not bad:
            bm.free()
            break
        tgt = set()
        for f in bm.faces:
            li = [v.index for v in f.verts]
            for k in range(len(li)):
                if (li[k], li[(k + 1) % len(li)]) in bad:
                    tgt.add(f.index)
                    break
        if not tgt:
            bm.free()
            break
        bmesh.ops.reverse_faces(bm, faces=[bm.faces[i] for i in sorted(tgt)])
        bm.to_mesh(me)
        bm.free()
        me.update()
        flipped += len(tgt)
    return flipped


def clean_self_intersections(obj, verbose=True):
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
    rep["翻转面数"] = _fix_winding(obj)
    rep["残留"] = len(_self_pairs(obj.data))
    rep["清理后"] = dict(面数=len(obj.data.polygons), 顶点数=len(obj.data.vertices), **_hygiene(obj))
    if verbose:
        print(f"[自交清理] 完成: 残留自交对={rep['残留']} 翻转面={rep['翻转面数']} "
              f"面 {rep['清理前']['面数']:,}→{rep['清理后']['面数']:,} "
              f"顶点 {rep['清理前']['顶点数']:,}→{rep['清理后']['顶点数']:,}", flush=True)
        print(f"[自交清理] 卫生 前={hy0} 后={rep['清理后']}", flush=True)
    return rep
