# -*- coding: utf-8 -*-
# rim 环平滑度审计(只读, 不改任何文件)
# 用法: blender -b --factory-startup -noaudio --python-exit-code 1 --python rim_ring_audit.py -- <blend> [contour_json]
# 输出: 两侧环的 顶点数 / 边长(中位·最小·最大·CV%) / 转角(xz 投影: 中位·均值·p95·max) / >15°·>25° 计数 / 最差尖点坐标
#
# 为什么要这么量:
#  1) 转角一律在 XZ 投影里算 —— 轮廓定义在 (x,z) 平面; 3D 转角被面外起伏稀释, 会放跑真实尖点(实测 XZ 31.7° 的点三维读数 <25°)。
#  2) 报数必须成组: 「等弧长重分布」后新增顶点共线 → 转角中位数可低到 0.04°, 只看中位会被骗; 关键看 p95/max 与 >15° 计数。
#  3) 左右并列报: 单侧好看没有意义, 左右不对称本身就是缺陷信号。
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
BLEND = a[0]
CJ = a[1] if len(a) > 1 else None
bpy.ops.wm.open_mainfile(filepath=BLEND)
if not (CJ and os.path.exists(CJ)):          # 自动向上找手描轮廓 json(取眼区中心)
    d = os.path.dirname(os.path.abspath(BLEND))
    for _ in range(6):
        c = os.path.join(d, "01a眼窝眼球", "3ddfa", "eyelid_contour_manual.json")
        if os.path.exists(c):
            CJ = c
            break
        d = os.path.dirname(d)
CEN = {}
if CJ and os.path.exists(CJ):
    _j = json.load(open(CJ, encoding="utf-8"))
    for _s in ("L", "R"):
        CEN[_s] = Vector([float(v) for v in _j[_s]["center"]])

obj = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
me = obj.data
ef = {}
for p in me.polygons:
    for ek in p.edge_keys:
        ef[ek] = ef.get(ek, 0) + 1
bnd = [(u, v) for (u, v), c in ef.items() if c == 1]
print(f"网格 {obj.name} 面={len(me.polygons):,} 边界边={len(bnd):,} (闭合壳应为 0)")
adj = {}
for u, v in bnd:
    adj.setdefault(u, []).append(v)
    adj.setdefault(v, []).append(u)

seen, rings = set(), []
for s0 in adj:
    if s0 in seen:
        continue
    ring, prev, cur = [s0], None, s0
    seen.add(s0)
    while True:
        nx = [x for x in adj.get(cur, []) if x != prev]
        if not nx:
            break
        prev, cur = cur, nx[0]
        if cur == s0 or cur in seen:
            break
        ring.append(cur)
        seen.add(cur)
    rings.append(ring)
rings.sort(key=len, reverse=True)
print(f"边界环 {len(rings)} 段: " + "; ".join(str(len(r)) for r in rings[:6]))


def stats(ring):
    P = np.array([list(me.vertices[i].co) for i in ring])
    Q = np.vstack([P[:, [0, 2]], P[:1, [0, 2]]])          # XZ 投影, 闭合
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    ang, worst = [], []
    for i in range(1, len(Q) - 1):
        a1, a2 = Q[i] - Q[i - 1], Q[i + 1] - Q[i]
        n1, n2 = np.linalg.norm(a1), np.linalg.norm(a2)
        if n1 < 1e-9 or n2 < 1e-9:
            ang.append(0.0)
            continue
        t = math.degrees(math.acos(float(np.clip(np.dot(a1, a2) / (n1 * n2), -1, 1))))
        ang.append(t)
        worst.append((t, i))
    ang = np.array(ang)
    worst.sort(reverse=True)
    return seg, ang, worst


res = {}
for s in ("L", "R"):
    if s not in CEN or not rings:
        continue
    c = CEN[s]

    def dmed(r):        # 该环到眼心的 xz 中位距离(用于挑出这只眼的 rim 环)
        return float(np.median([(me.vertices[i].co - c).xz.length for i in r]))

    ring = min(rings, key=dmed)
    seg, ang, worst = stats(ring)
    res[s] = dict(n=len(ring), cv=seg.std() / seg.mean() * 100,
                  mn=seg.min() * 1000, mx=seg.max() * 1000,
                  p95=float(np.percentile(ang, 95)), mx_ang=float(ang.max()),
                  n15=int((ang > 15).sum()), n25=int((ang > 25).sum()))
    print(f"\n[{s}] 环 {len(ring)} 顶点 (到眼心 xz 中位距离 {dmed(ring):.2f}mm)")
    print(f"     边长(ms): 中位={np.median(seg)*1000:.3f} 最小={seg.min()*1000:.3f} 最大={seg.max()*1000:.3f} CV={res[s]['cv']:.1f}%")
    print(f"     转角(xz): 中位={np.median(ang):.2f}° 均值={ang.mean():.2f}° p95={res[s]['p95']:.2f}° max={res[s]['mx_ang']:.2f}°"
          f" | >15°={res[s]['n15']} >25°={res[s]['n25']}")
    for t, i in worst[:3]:
        v = me.vertices[ring[i]].co
        print(f"       最差: ({v.x*1000:+.2f},{v.y*1000:+.2f},{v.z*1000:+.2f})mm 转角={t:.1f}°")

if len(res) == 2:
    L, R = res["L"], res["R"]
    print(f"\n[对称性] >15° 计数 L{L['n15']} vs R{R['n15']} (差值 {abs(L['n15']-R['n15'])})"
          f" | 最小边 L{L['mn']:.3f}/R{R['mn']:.3f}mm | CV L{L['cv']:.1f}%/R{R['cv']:.1f}%"
          f" → 单侧数字好看无意义, 左右不对称本身就是缺陷信号。")
print("\nRIM_RING_AUDIT_DONE")
