"""眼区"穿插/黑面"定量体检 —— 用户报穿插叠面 / 黑面 / 破面时, 先跑这个, 再谈几何改动。

用法(Blender headless):
  EYE_OUT_BLEND=<当前产物.blend> EYE_CONTOUR_JSON=<手描轮廓.json> \
  blender -b --factory-startup --python scripts/mesh_intersect_check.py

判据:
  ① 真穿插面对 = BVH 两两重叠后【排除共顶点邻居】的对数 —— 应为 0 或个位数; 排除共顶点是必须的,
     否则邻接面本身就会互相"重叠"报出成千上万假阳性。
  ② 零面积面 / 极小面积面(<1e-3 mm²) —— 应为 0; 这是用户口中"黑面"的可量化来源之一。

为什么必须要脚本: 这类细结构问 vision 会被说成"大量细长三角形/破面"(与实测矛盾);
vision 只适合做【同设置对侧对比】的定性复核, 网格质量一律脚本定量。
"""
import os, json, sys
import bpy, bmesh, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

F = os.environ.get("EYE_OUT_BLEND") or os.environ.get("CHK_BLEND")
J = os.environ.get("EYE_CONTOUR_JSON")
if not (F and J):
    sys.exit("需要环境变量 EYE_OUT_BLEND + EYE_CONTOUR_JSON")
print("检查:", os.path.basename(F))
bpy.ops.wm.open_mainfile(filepath=F)
Jd = json.load(open(J, encoding="utf-8"))
head = max([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
bm = bmesh.new(); bm.from_mesh(head.data)
bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()

for s in ("L", "R"):
    c = Vector(tuple(float(x) for x in Jd[s]['center']))
    P = np.array([[float(p[0]), float(p[2])] for p in Jd[s]['rim_3d']])
    fs = []
    for f in bm.faces:
        cc = f.calc_center_median()
        if (cc - c).xz.length > 0.030 or cc.y > c.y + 0.02:
            continue                      # 只看前脸眼区, 排除后脑/内腔面
        d = float(np.sqrt((P[:, 0] - cc.x) ** 2 + (P[:, 1] - cc.z) ** 2).min())
        if d <= 0.010:
            fs.append(f)
    vmap, verts, polys = {}, [], []
    for f in fs:
        idx = []
        for v in f.verts:
            if v.index not in vmap:
                vmap[v.index] = len(verts); verts.append(v.co[:])
            idx.append(vmap[v.index])
        polys.append(idx)
    real, adj = set(), 0
    if polys:
        tree = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
        fv = {i: set(p) for i, p in enumerate(polys)}
        for i, j in tree.overlap(tree):
            if i == j:
                continue
            a, b = sorted((i, j))
            if (a, b) in real:
                continue
            if fv[a] & fv[b]:
                adj += 1                  # 共顶点 = 正常邻接, 不算穿插
            else:
                real.add((a, b))
    zero = tiny = tot = 0
    for f in fs:
        tot += 1
        a = f.calc_area() * 1e6
        if a < 1e-6:
            zero += 1
        elif a < 1e-3:
            tiny += 1
    print(f"{s}: 眼区10mm内 {tot}面 | 真穿插面对 {len(real)} | 零面积 {zero} | 极小面积(<1e-3mm2) {tiny}")
    for a, b in list(real)[:4]:
        va = np.mean([verts[i] for i in polys[a]], axis=0)
        print(f"    穿插对 @({va[0]*1000:.1f},{va[1]*1000:.1f},{va[2]*1000:.1f})")
bm.free()
