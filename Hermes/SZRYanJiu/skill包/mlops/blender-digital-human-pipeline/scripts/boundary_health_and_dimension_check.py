# -*- coding: utf-8 -*-
# 几何验收的“分维度 + 反向口径”检查器(通用化自 01a rim 门控核验)
#
# 用途(两个独立模块, 都可单独跑):
#   [1] ref_accuracy(): 先量“真值本身有多准” —— 参考点/标记点集到网格表面的最近距离。
#       必须先跑这个: 若参考点自身就散差 p90 3mm, 则“点到参考线的距离”这类指标是被参考误差主导的,
#       不能拿来判几何好坏。(实测手描标记点: mean 1.42 / p90 3.25 / max 5.14 mm, 深度分量仅 0.72mm)
#   [2] compare(): 同一口径对比两个阶段的产物文件, 报 边界拓扑健康度 + 三个维度距离。
#
# 为何分维度: 同一几何用「正视图横向(XZ) / 深度(Y) / 3D」量会得出相反结论。
#   实测: 横向 0.65→0.43mm(max 4.03→0.955, >1mm 超标 9.2%→0%) 是改善,
#        而 3D 距离 2.53→2.86mm 反而“变差”是因为它含了参考点自身的深度散差。
#   报结论时必须指名维度, 并说明哪个维度对齐用户感知(正视图轮廓 → XZ 横向)。
#
# 用法(Blender headless):
#   blender -b --factory-startup -noaudio --python-exit-code 1 --python boundary_health_and_dimension_check.py
# 改 PATH_A/PATH_B/REF_JSON/CENTERS 为本项目的实际路径。
import bpy, os, json, math
import numpy as np
import bmesh

# ---------------- 配置区(按项目改) ----------------
PATH_A = r""     # 基线产物 .blend
PATH_B = r""     # 新产物 .blend
REF_JSON = r""   # 参考点集 JSON
REF_KEY = "rim_3d"          # JSON 里点列表的键(可能是 {L:[...], R:[...]})
SIDES = ("L", "R")
NEAR_MM = 25.0              # “眼周/孔周”判定半径(mm)
SURFACE_BLEND = r""         # 量参考点精度时要打开的文件(应含目标区域完整表面)


def _dist_to_polyline(p, C, xz_only=False):
    """点 p 到闭合折线 C 的最近距离(m)。xz_only=True 时只算 XZ 平面内(正视图横向)。"""
    A = C[:, [0, 2]] if xz_only else C
    B = np.roll(A, -1, axis=0)
    AB = B - A
    L2 = (AB ** 2).sum(axis=1)
    L2[L2 == 0] = 1e-12
    P = np.array([p[0], p[2]]) if xz_only else np.array(p)
    AP = P - A
    t = np.clip((AP * AB).sum(axis=1) / L2, 0.0, 1.0)
    return float(np.linalg.norm(P - (A + t[:, None] * AB), axis=1).min())


def _largest_mesh():
    return max([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))


def ref_accuracy(blend, refs, key=REF_KEY):
    """[1] 参考点集 → 网格表面最近距离(含 Y 分量单独报)。先跑这个再判几何。"""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    bpy.ops.wm.open_mainfile(filepath=blend)
    o = _largest_mesh(); mw = o.matrix_world
    vs = [mw @ v.co for v in o.data.vertices]
    tris = []
    for pl in o.data.polygons:
        vi = list(pl.vertices)
        for k in range(1, len(vi) - 1):
            tris.append((vi[0], vi[k], vi[k + 1]))
    bvh = BVHTree.FromPolygons(vs, tris, all_triangles=True)
    print(f"\n[1] 参考点精度 vs 表面: {os.path.basename(blend)} ({len(tris):,} 三角)")
    for s in refs:
        d3, dy = [], []
        for q in refs[s]:
            loc, nrm, idx, dist = bvh.find_nearest(Vector(list(q)))
            if loc is None:
                continue
            d3.append(dist * 1000.0); dy.append((q[1] - loc.y) * 1000.0)
        d3 = np.array(d3); dy = np.array(dy)
        print(f"   [{s}] n={len(d3)} 到表面: mean={d3.mean():.3f} p50={np.percentile(d3,50):.3f} "
              f"p90={np.percentile(d3,90):.3f} max={d3.max():.3f} mm | 其中 Y 分量 |adj|mean={np.abs(dy).mean():.3f} max={np.abs(dy).max():.3f} mm")
    print("   → 若 p90 已到 mm 级, 则“点到参考线”类指标被参考自身误差主导, 不可用它判几何好坏。")


def compare(path_a, path_b, refs, tag_a="基线", tag_b="新产物", near_mm=NEAR_MM):
    """[2] 同口径对比两个产物: 边界拓扑健康度 + XZ/深度/3D 三维距离。"""
    EYE = {s: np.array(refs[s], float).mean(axis=0) for s in refs}
    for tag, path in ((tag_a, path_a), (tag_b, path_b)):
        bpy.ops.wm.open_mainfile(filepath=path)
        o = _largest_mesh()
        bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
        nb = sum(1 for e in bm.edges if len(e.link_faces) == 1)
        nm = sum(1 for e in bm.edges if len(e.link_faces) >= 3)
        print(f"\n=== [{tag}] {os.path.basename(path)} 面={len(bm.faces):,} 顶={len(bm.verts):,} 边界边={nb} 非流形边={nm} ===")
        for s in refs:
            C = np.array(refs[s], float); c = EYE[s]
            near = [e for e in bm.edges if len(e.link_faces) == 1
                    and math.hypot(e.verts[0].co.x - c[0], e.verts[0].co.z - c[2]) * 1000 <= near_mm]
            vids = set()
            adj = {}
            for e in near:
                a, b = e.verts[0].index, e.verts[1].index
                vids.add(a); vids.add(b)
                adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
            seen, comps = set(), []
            for v in vids:
                if v in seen:
                    continue
                st = [v]; seen.add(v); grp = []
                while st:
                    u = st.pop(); grp.append(u)
                    for w in adj.get(u, ()):
                        if w not in seen:
                            seen.add(w); st.append(w)
                comps.append(grp)
            comps.sort(key=len, reverse=True)
            branch = [v for v in vids
                      if sum(1 for e in bm.verts[v].link_edges if len(e.link_faces) == 1) > 2]
            ds, dxz, ys = [], [], []
            for v in vids:
                p = np.array(bm.verts[v].co[:], float)
                ds.append(_dist_to_polyline(p, C))
                dxz.append(_dist_to_polyline(p, C, xz_only=True))
                j = int(np.argmin((C[:, 0] - p[0]) ** 2 + (C[:, 2] - p[2]) ** 2))
                ys.append((p[1] - C[j, 1]) * 1000.0)
            ds = np.array(ds) * 1000; dxz = np.array(dxz) * 1000; ys = np.array(ys)
            print(f"  [{s}] 孔周顶点={len(vids)} 边界边={len(near)} 连通分量={len(comps)} "
                  f"top点数={[len(x) for x in comps[:5]]} 分支点(>2边界边)={len(branch)}")
            if len(ds):
                print(f"       XZ横向: mean={dxz.mean():.3f} p50={np.percentile(dxz,50):.3f} max={dxz.max():.3f} mm (>1mm {(dxz>1).mean()*100:.1f}%)")
                print(f"       Y深度 : mean={ys.mean():+.3f} |adj|mean={np.abs(ys).mean():.3f} max={np.abs(ys).max():.3f} mm")
                print(f"       3D    : mean={ds.mean():.3f} p50={np.percentile(ds,50):.3f} max={ds.max():.3f} mm")
        bm.free()
    print("\n判读: 以 XZ 横向(正视图轮廓)为改善判据; 多环/碎环/分支点=边界不健康; "
          "3D 距离须先扣掉参考点自身散差(ref_accuracy)才有意义。")


if __name__ == "__main__":
    refs = {}
    if REF_JSON and os.path.exists(REF_JSON):
        J = json.load(open(REF_JSON, encoding="utf-8"))
        refs = {s: [q for q in J[s][REF_KEY] if q is not None] for s in SIDES}
    if SURFACE_BLEND:
        ref_accuracy(SURFACE_BLEND, refs)
    if PATH_A and PATH_B:
        compare(PATH_A, PATH_B, refs)
