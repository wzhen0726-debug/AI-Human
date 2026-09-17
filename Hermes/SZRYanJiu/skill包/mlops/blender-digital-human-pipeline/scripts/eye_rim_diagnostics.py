#!/usr/bin/env python
"""Eye rim 环体检(Blender headless): 环闭合性/间距/3D 转角/XZ 折返/眼周反面。

用法:
  blender -b --factory-startup --python eye_rim_diagnostics.py -- <file.blend> [cx_mm cz_mm ...]

不传中心坐标时, 只列出网格里所有开放边界环的 (顶点数, 质心mm, 周长mm) 供挑选;
第一次务必用已知正确的产物核对输出量级, 再用同一套判据对照新旧文件。

参考量级(正确的 rim 环): 顶点度数全 2 / 环最大边长 ≤1mm / 3D 转角 mean <6° / 折返 0。
环最大边长数百 mm = 有顶点深度采样错(射线穿透打到后脑); 数 mm = 粗面边界没细分。
"""
import bpy, bmesh, sys, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv:
    print("用法: blender -b --factory-startup --python eye_rim_diagnostics.py -- <file.blend> [cx_mm cz_mm ...]")
    raise SystemExit
path = argv[0]
bpy.ops.wm.open_mainfile(filepath=path)
obj = max([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
bm = bmesh.new(); bm.from_mesh(obj.data)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
print(f"file={path} obj={obj.name} verts={len(bm.verts)}")

# ---- 所有开放边界环 ----
adj = {}
for e in bm.edges:
    if len(e.link_faces) == 1:
        for a, b in ((e.verts[0], e.verts[1]), (e.verts[1], e.verts[0])):
            adj.setdefault(a.index, []).append(b.index)
loops, seen = [], set()
for s in list(adj):
    if s in seen or len(adj[s]) != 2:
        continue
    lp = [s]; seen.add(s); prev, cur = -1, s
    while cur in adj:
        cand = [n for n in adj[cur] if n != prev]
        if not cand:
            break
        nxt = cand[0]
        if nxt == lp[0] or nxt in seen:
            break
        lp.append(nxt); seen.add(nxt); prev, cur = cur, nxt
        if len(lp) > 200000:
            break
    loops.append(lp)
loops.sort(key=len, reverse=True)

centers = []
if len(argv) >= 3:
    for i in range(1, len(argv) - 1, 2):
        centers.append((float(argv[i]), float(argv[i + 1])))
if not centers:
    print("未给中心坐标 → 候选闭环(挑出眼周两个, 用其质心重跑):")
    for lp in loops[:8]:
        cx = sum(bm.verts[k].co.x for k in lp) / len(lp) * 1000
        cz = sum(bm.verts[k].co.z for k in lp) / len(lp) * 1000
        peri = sum((bm.verts[lp[i]].co - bm.verts[lp[(i + 1) % len(lp)]].co).length for i in range(len(lp))) * 1000
        print(f"   {len(lp):6d} 顶点  质心({cx:+8.2f},{cz:+8.2f})mm  周长{peri:7.1f}mm")
    raise SystemExit

vnorm = {}
for v in bm.verts:
    n = Vector((0.0, 0.0, 0.0))
    for f in v.link_faces:
        n += f.normal
    vnorm[v.index] = n.normalized() if n.length > 1e-12 else Vector((0.0, -1.0, 0.0))

def seg_int(p1, p2, p3, p4):
    d1 = p2 - p1; d2 = p4 - p3
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-14:
        return None
    t = ((p3[0] - p1[0]) * d2[1] - (p3[1] - p1[1]) * d2[0]) / den
    u = ((p3[0] - p1[0]) * d1[1] - (p3[1] - p1[1]) * d1[0]) / den
    if 1e-9 < t < 1 - 1e-9 and 1e-9 < u < 1 - 1e-9:
        return (t, u)
    return None

for ci, (cxm, czm) in enumerate(centers):
    cv = Vector((cxm / 1000.0, 0.0, czm / 1000.0))
    tag = f"eye#{ci+1} ({cxm:+.1f},{czm:+.2f})mm"
    lp = None
    for L in loops:
        d = sum((bm.verts[k].co - cv).xz.length for k in L) / len(L)
        if d < 0.020 and (lp is None or len(L) > len(lp)):
            lp = L
    if not lp:
        print(f"{tag}: 找不到眼周边界环")
        continue
    deg = {}
    for e in bm.edges:
        if len(e.link_faces) == 1 and (e.verts[0].co - cv).xz.length < 0.030:
            for a, b in ((e.verts[0], e.verts[1]), (e.verts[1], e.verts[0])):
                deg.setdefault(a.index, []).append(b.index)
    d1 = sum(1 for k in deg if len(deg[k]) == 1)
    d3 = sum(1 for k in deg if len(deg[k]) >= 3)
    P = [bm.verts[k].co.copy() for k in lp]
    N = len(P)
    step = [(P[(i + 1) % N] - P[i]).length * 1000 for i in range(N)] if N > 1 else [0.0]
    Q = [(p.x - cv.x, p.z - cv.z) for p in P]
    hits = 0
    for i in range(N):
        a1, a2 = Q[i], Q[(i + 1) % N]
        for j in range(i + 2, N):
            if (j + 1) % N == i or j == (i + 1) % N:
                continue
            if seg_int(a1, a2, Q[j], Q[(j + 1) % N]):
                hits += 1
    turns = []
    for i in range(N):
        a = P[i] - P[(i - 1) % N]; b = P[(i + 1) % N] - P[i]
        if a.length > 1e-12 and b.length > 1e-12:
            turns.append(math.degrees(a.angle(b)))
    bad, dists = 0, []
    for f in bm.faces:
        c = f.calc_center_median()
        if (c - cv).xz.length > 0.030:
            continue
        avg = Vector((0.0, 0.0, 0.0))
        for v in f.verts:
            avg += vnorm[v.index]
        if avg.length < 1e-12:
            continue
        if f.normal.dot(avg.normalized()) < 0:
            bad += 1; dists.append((c - cv).xz.length * 1000)
    s = sorted(step)
    print(f"{tag}: 环 {N} 顶点, 1度 {d1} / >=3度 {d3} (全 2 度=闭合)")
    print(f"   边长[min {s[0]:.3f} / 中位 {s[len(s)//2]:.3f} / max {s[-1]:.3f}]mm")
    if turns:
        over = sum(1 for t in turns if t > 30)
        print(f"   3D 转角 mean {sum(turns)/len(turns):.1f}° max {max(turns):.1f}° (>30° {over} 个)")
    print(f"   XZ 折返(自交) {hits} 对   ← 必须为 0")
    if bad:
        print(f"   眼周反面 {bad} 个, 距眼中心 {min(dists):.1f}~{max(dists):.1f}mm "
              f"(≥6mm 且洞口以内=后脑反面正常; 落在皮肤上=翻面 bug)")
    else:
        print("   眼周反面 0 个")
bm.free()
print("DONE")
