# -*- coding: utf-8 -*-
"""反推用户手调参考版: 两份 blend 的几何差异报告。

用法:
  blender -b --factory-startup --python diff_reference_blend.py -- <基线.blend> <参考.blend> [左右分界x, 默认0.0]

输出:
  1) 各自 顶点/面/开放边 数; 同拓扑与否(顶点+面数一致)
  2) 按 x 符号分 L/R; 每侧: 未动(<=0.2mm)/动了 的顶点数
  3) 动了顶点的 Δx/Δy/Δz 均值/范围(mm) 与方向性(纯Y位移判定)
  4) 按【基线位置】到该侧区域中心的 XZ 半径分 6 带 → 看出哪几圈被调、前后是否渐变

注意: 纯几何比较, 不比较 UV/材质; 最近点阈值 0.2mm 需按网格密度酌情; 移动量很小时
先确认两份确实同拓扑(否则先对齐坐标系再比)。
"""
import sys
import numpy as np
import bpy
from mathutils import Vector, kdtree

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
BLEND_A = argv[0]
BLEND_B = argv[1]
X_SPLIT = float(argv[2]) if len(argv) > 2 else 0.0
UNMOVED = 0.0002  # 0.2mm


def load(path):
    bpy.ops.wm.open_mainfile(filepath=path)
    objs = [o for o in bpy.data.objects if o.type == 'MESH']
    obj = max(objs, key=lambda o: len(o.data.vertices))
    me = obj.data
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    n_open = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    bm.free()
    return co, len(me.polygons), n_open, obj.name


coA, nfA, noA, nameA = load(BLEND_A)
print(f"[A 基线] {nameA}: 顶点={len(coA)} 面={nfA} 开放边={noA}", flush=True)
coB, nfB, noB, nameB = load(BLEND_B)
print(f"[B 参考] {nameB}: 顶点={len(coB)} 面={nfB} 开放边={noB}", flush=True)
print(f"同拓扑(顶点+面数一致): {len(coA) == len(coB) and nfA == nfB}", flush=True)

kd = kdtree.KDTree(len(coB))
for i, v in enumerate(coB):
    kd.insert(Vector((float(v[0]), float(v[1]), float(v[2]))), i)
kd.balance()

for s in ("L", "R"):
    sel = np.where(coA[:, 0] < -abs(X_SPLIT))[0] if s == "L" else np.where(coA[:, 0] > abs(X_SPLIT))[0]
    if len(sel) == 0:
        continue
    cen = coA[sel][:, [0, 2]].mean(axis=0)
    n_dist, deltas, rr = [], [], []
    for i in sel:
        p = Vector((float(coA[i][0]), float(coA[i][1]), float(coA[i][2])))
        _loc, j, dist = kd.find(p)
        n_dist.append(dist)
        if dist < UNMOVED:
            continue
        q = coB[j]
        dv = Vector((float(q[0]), float(q[1]), float(q[2]))) - p
        deltas.append((dv.x, dv.y, dv.z))
        rr.append(float(np.hypot(coA[i][0] - cen[0], coA[i][2] - cen[1])))
    n_dist = np.array(n_dist)
    print(f"\n[{s}] 区顶点 {len(sel)}  未动 {int((n_dist < UNMOVED).sum())}  动了 {len(deltas)}", flush=True)
    if not deltas:
        continue
    D = np.array(deltas) * 1000.0
    rr = np.array(rr)
    print(f"  Δ(mm): x 均值{D[:, 0].mean():+.3f} [{D[:, 0].min():+.3f},{D[:, 0].max():+.3f}]  "
          f"y 均值{D[:, 1].mean():+.3f} [{D[:, 1].min():+.3f},{D[:, 1].max():+.3f}]  "
          f"z 均值{D[:, 2].mean():+.3f} [{D[:, 2].min():+.3f},{D[:, 2].max():+.3f}]", flush=True)
    y_ratio = abs(D[:, 1]).mean() / (np.linalg.norm(D, axis=1).mean() + 1e-9)
    print(f"  方向性: |Δy|/|Δ| = {y_ratio:.2f} (≈1 = 纯 Y 位移)", flush=True)
    order = np.argsort(-rr)
    N = len(order)
    for g in range(6):
        seg = order[g * N // 6:(g + 1) * N // 6]
        if len(seg) == 0:
            continue
        mm = D[seg]
        print(f"    带{g + 1} r~{rr[seg].mean():.1f}mm n={len(seg)}  "
              f"Δ=({mm[:, 0].mean():+.3f},{mm[:, 1].mean():+.3f},{mm[:, 2].mean():+.3f}) mm  "
              f"|Δ|均{np.linalg.norm(mm, axis=1).mean():.3f}mm", flush=True)
print("\nDIFF_DONE", flush=True)
