# -*- coding: utf-8 -*-
# rim 环(眼窝/开口边界折线)平滑度体检 —— 边长均匀性 + 转角分布 + 尖点定位
#
# 适用: 用户报“rim 环不平滑 / 波浪 / 锯齿 / 眼角有尖点”。这是**边界折线**质量, 与坏面指标是两条独立轴。
# 用法(项目根 = 演示版_终端控制端):
#   blender.exe -b --factory-startup -noaudio --python-exit-code 1 \
#     --python <skill>/scripts/rim_ring_smoothness.py -- "<01_1_eye_socket.blend 绝对路径>"
#
# 口径: 转角一律在 **xz 投影**算(与手描轮廓定义平面一致); 三维口径会被面外微起伏稀释,
#   实测 xz 31.7° 的尖点在三维下不到 25° → 与修复阈值比较时会漏判。
# 主指标: 边长 CV / 最小边长 / max 转角 / `>15°`、`>25°` 顶点数; 热点坐标用来指认“内眼角/外眼角/下睑中段”。
# 参照基准(杏仁形手描轮廓): 边长中位 ~0.5mm、CV 35~40%; 平滑环 max 转角 <20°、>15° 顶点个位数;
#   退化的环会出现 0.07mm 级短边 + 30°+ 尖点。
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.open_mainfile(filepath=a[0])
ROOT = os.path.dirname(bpy.data.filepath)
while os.path.basename(ROOT) != "演示版_终端控制端":
    ROOT = os.path.dirname(ROOT)
sys.path.insert(0, os.path.join(ROOT, "01a眼窝眼球", "scripts"))
import eye_socket_config as CFG

o = max([x for x in bpy.data.objects if x.type == 'MESH'], key=lambda x: len(x.data.polygons))
me = o.data
cj = json.load(open(os.path.join(ROOT, "01a眼窝眼球", "3ddfa", "eyelid_contour_manual.json"), encoding="utf-8"))
print(f"网格 {o.name} 面={len(me.polygons):,}")

edge_faces = {}
for p in me.polygons:
    for ek in p.edge_keys:
        edge_faces[ek] = edge_faces.get(ek, 0) + 1
bnd_edges = [ek for ek, c in edge_faces.items() if c == 1]
print(f"全网格边界边 {len(bnd_edges):,} (闭合壳应为0; 应≈两环周长之和)")

for s in ("L", "R"):
    c = Vector([float(v) for v in cj[s]["center"]])
    sel = [(u, v) for (u, v) in bnd_edges
           if (me.vertices[u].co - c).xz.length < CFG.EYE_AREA_R and me.vertices[u].co.y < c.y + 0.02]
    if len(sel) < 8:
        print(f"[{s}] 眼区边界边只有 {len(sel)} 条"); continue
    adj = {}
    for u, v in sel:
        adj.setdefault(u, []).append(v); adj.setdefault(v, []).append(u)
    start = next(iter(adj)); ring = [start]; prev = None; cur = start
    for _ in range(len(sel) + 5):
        nxt = [x for x in adj.get(cur, []) if x != prev]
        if not nxt: break
        prev, cur = cur, nxt[0]
        if cur == start: break
        ring.append(cur)
    P = np.array([list(me.vertices[i].co) for i in ring])
    seg = np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1)
    Q = np.vstack([P[:, [0, 2]], P[:1, [0, 2]]])          # 闭合成环的 xz 投影
    ang = []
    for i in range(1, len(Q) - 1):
        a1 = Q[i] - Q[i - 1]; a2 = Q[i + 1] - Q[i]
        n1, n2 = np.linalg.norm(a1), np.linalg.norm(a2)
        if n1 < 1e-9 or n2 < 1e-9: continue
        ca = float(np.clip(np.dot(a1, a2) / (n1 * n2), -1, 1))
        ang.append(math.degrees(math.acos(ca)))
    ang = np.array(ang)
    print(f"\n[{s}] 环顶点={len(ring)}  边长(mm): 中位={np.median(seg)*1000:.3f} 最小={seg.min()*1000:.3f} "
          f"最大={seg.max()*1000:.3f} CV={seg.std()/seg.mean()*100:.1f}%")
    print(f"     转角(xz): 中位={np.median(ang):.2f}° 均值={ang.mean():.2f}° p95={np.percentile(ang,95):.2f}° "
          f"max={ang.max():.2f}°  >15°={int((ang > 15).sum())}  >25°={int((ang > 25).sum())}")
    for k in np.argsort(-ang)[:5]:
        i = k + 1
        print(f"       尖点: 顶点#{ring[i]} 坐标=({Q[i][0]*1000:+.2f},{P[i][1]*1000:+.2f},{Q[i][1]*1000:+.2f})mm "
              f"转角={ang[k]:.1f}° 两侧边长={seg[i-1]*1000:.2f}/{seg[i]*1000:.2f}mm")
print("RIMRING_DONE")
