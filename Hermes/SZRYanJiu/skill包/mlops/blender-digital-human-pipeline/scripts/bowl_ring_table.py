# -*- coding: utf-8 -*-
"""碗环 BFS 表 — 低模碗(02 杯工序)环结构的权威量测工具.

用法(Blender headless):
  blender -b --factory-startup --python scripts/bowl_ring_table.py -- <blend路径> [更多blend...]

判读口径(用户参考碗实测规律, 复刻必须命中):
  * 深度步进应逐环全等(参考碗: +3.13mm ×7);
  * 顶点波动按 (NB-k)/NB 精确线性衰减, 最深环 y 跨度 = 0.00(全平的眼窝心);
  * 缩放序列线性(≈0.105/环, 最深环 r/rrim ≈ 0.15);
  * 极点比最深环再深 ≈0.058×眼宽(参考碗 +2.17mm @ 37.13mm).

原理: 碗 = 四边形环带 → 从 rim 出发按网格边 BFS, 图距 = 环号.
  确定性, 与顶点顺序无关(用户手工重建过的参考碗同样能读);
  不要用"按半径分箱/同半径圆周"替代 —— 杏仁形环会把不同环+皮肤混样,
  也不要用"按顶点索引切片" —— 那是假定"创建顺序=环顺序", 手工重建的文件立刻读乱.
前提: 碗顶点是文件里最后追加的顶点块(本管线产物与用户参考版都满足; 不满足时脚本会提示).
"""
import bpy, sys, mathutils, numpy as np
from collections import deque

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv:
    print("用法: -- <blend路径> [更多blend...]", flush=True)
    sys.exit(1)

DEF = {"L": np.array([-0.0361, -0.0935, 1.6712]), "R": np.array([0.0361, -0.0935, 1.6712])}


def eye_centers():
    """优先用 Eye002_L/R 的包围盒中心; 缺失时回退内置默认(当前主模型)."""
    out = {}
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name in ("Eye002_L", "Eye002_R"):
            bb = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
            out[o.name[-1]] = np.array([sum(v.x for v in bb) / 8.,
                                        sum(v.y for v in bb) / 8.,
                                        sum(v.z for v in bb) / 8.])
    for s in ("L", "R"):
        out.setdefault(s, DEF[s])
    return out


def analyze(fp):
    bpy.ops.wm.open_mainfile(filepath=fp)
    head = [o for o in bpy.data.objects if o.type == 'MESH' and len(o.data.vertices) > 1000][0]
    me = head.data
    NV = len(me.vertices)
    V = np.empty(NV * 3); me.vertices.foreach_get("co", V); V = V.reshape(-1, 3)
    E = np.empty(len(me.edges) * 2, dtype=np.int64); me.edges.foreach_get("vertices", E); E = E.reshape(-1, 2)
    CS = eye_centers()

    def ok(p):
        return p[1] < -0.05 and min(np.linalg.norm(p - c) for c in CS.values()) < 0.032

    i = NV - 1
    while i >= 0 and ok(V[i]):
        i -= 1
    tail = list(range(i + 1, NV))
    print(f"\n=== {fp}\n    NV={NV} 碗候选(尾部块)={len(tail)} (假定: 碗为最后追加顶点块)", flush=True)
    if len(tail) < 50:
        print("   ⚠ 尾部块过小 — 该文件的碗不是最后追加(或过滤条件不符), 下表不可信", flush=True)
        return
    bset = set(tail)
    ad = {}
    for a, b in E:
        if a in bset: ad.setdefault(a, []).append(b)
        if b in bset: ad.setdefault(b, []).append(a)
    rim = sorted({n for v in tail for n in ad[v] if n not in bset})
    for side, C in CS.items():
        bl = [v for v in tail if (V[v, 0] > 0) == (side == "R")]
        rim_s = [v for v in rim if (V[v, 0] > 0) == (side == "R")]
        if len(bl) < 40:
            continue
        bs = set(bl)
        rim_s = set(rim_s)
        r2b = {}
        for a, b in E:
            if a in rim_s and b in bs: r2b.setdefault(a, []).append(b)
            if b in rim_s and a in bs: r2b.setdefault(b, []).append(a)
        dd = {}; q = deque()
        for rv in rim_s:
            for w in r2b.get(rv, []):
                if w not in dd:
                    dd[w] = 1; q.append(w)
        while q:
            v = q.popleft()
            for w in ad[v]:
                if w in bs and w not in dd:
                    dd[w] = dd[v] + 1; q.append(w)
        layers = {}
        for v, d in dd.items():
            layers.setdefault(d, []).append(v)
        rrim = float(np.median([np.hypot(V[v][0] - C[0], V[v][2] - C[2]) for v in rim_s]))
        print(f"  --- {side}眼: 环层={len(layers)} 未达={len(bs)-len(dd)} rim顶点={len(rim_s)} ---", flush=True)
        print("   d    n   r均mm  r/rrim   y均mm  ystd  y跨度mm   Δ上环", flush=True)
        prev = None
        for d in sorted(layers):
            vs = layers[d]
            rr = np.array([np.hypot(V[v][0] - C[0], V[v][2] - C[2]) for v in vs]) * 1000
            yy = np.array([V[v][1] for v in vs]) * 1000
            dy = "" if prev is None else f"{yy.mean()-prev:+.2f}"
            print(f"  {d:2d} {len(vs):4d} {rr.mean():7.2f} {rr.mean()/1000/rrim:6.3f} {yy.mean():8.2f} {yy.std():5.2f} {yy.max()-yy.min():6.2f}  {dy}", flush=True)
            prev = yy.mean()
    print("  判读: 步进应逐环全等; 波动线性衰减; 最深环(倒数第2层)跨度应=0.00; 末层=极点", flush=True)


for fp in argv:
    analyze(fp)
print("\nBOWL_RING_TABLE_DONE", flush=True)
