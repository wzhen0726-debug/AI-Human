"""低模rim倒角: 在低模rim带加0.5mm倒角, 让rim有几何锐利度, 再烘焙.

选边逻辑(2026-09-07重写): rim轮廓最近边法.
旧版用"边中点距rim轮廓<3mm带宽"选边, 在QR低模(眼部边长中位~3mm)上会抓到
2~3排交错碎边(实测138条散布0.56~3.0mm), 眼周碎线全带上倒角权重 → 杂乱倒角.
新版: 对rim轮廓的每个点, 只取点-线段距离最近的那条边(边真正紧贴轮廓),
再用自适应紧阈值(0.4×眼部边长中位, 下限1mm)过滤离群点. 只有眼睑缘本身的边
有权重, 周围碎边权重为0. 全部距离测量驱动, 无硬编码体型参数."""
import bpy, os, json, bmesh, math
import numpy as np
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付"
LOW_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend")
OUT_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_rim_bevel.blend")
XZ_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")
cont = json.load(open(XZ_JSON, encoding="utf-8"))

bpy.ops.wm.open_mainfile(filepath=LOW_BLEND)
head = max([o for o in bpy.data.objects if o.type == 'MESH'],
           key=lambda o: len(o.data.vertices))
print(f"低模: {head.name} 顶点={len(head.data.vertices)}")
me = head.data
mw = head.matrix_world

# ---- 顶点世界坐标(批量) ----
co = np.empty(len(me.vertices) * 3, dtype=np.float64)
me.vertices.foreach_get("co", co)
V = co.reshape(-1, 3) @ np.array(mw.to_3x3()).T + np.array(mw.translation)

# ---- 边端点索引(批量) ----
evi = np.empty(len(me.edges) * 2, dtype=np.int32)
me.edges.foreach_get("vertices", evi)
EV = evi.reshape(-1, 2)
E0 = V[EV[:, 0]]; E1 = V[EV[:, 1]]
Elen = np.linalg.norm(E1 - E0, axis=1)

# ---- 眼部区域边长中位(测量驱动阈值): rim附近8mm内的边 ----
rim_all = np.vstack([np.array(cont[s]["rim_3d"], dtype=np.float64) for s in ("L", "R")])
Emid = (E0 + E1) / 2
d_mid_all = np.linalg.norm(Emid[:, None, :] - rim_all[None, :, :], axis=2).min(axis=1)
near_mask = d_mid_all < 0.008
med_len = float(np.median(Elen[near_mask]))
print(f"眼部区边数={int(near_mask.sum())} 边长中位={med_len*1000:.3f}mm")

# ---- rim最近边法 + 切向过滤: 每个rim点找最近边, 且边方向必须顺着轮廓 ----
# 距离阈值: 0.4×边长中位, 下限1mm; 切向阈值: 与最近轮廓段夹角<35°
# (只查距离会选中斜跨轮廓的碎边: QR眼部网格不与rim对齐, 最近边常是44~77°横穿边)
THRESH = max(0.001, 0.4 * med_len)
# rim轮廓折线段(L/R各闭合)
segs = []
for s in ("L", "R"):
    p = np.array(cont[s]["rim_3d"], dtype=np.float64)
    for i in range(len(p)):
        segs.append((p[i], p[(i+1) % len(p)]))
S0 = np.array([x[0] for x in segs]); S1 = np.array([x[1] for x in segs])
SD = S1 - S0
SDl2 = np.einsum('ij,ij->i', SD, SD) + 1e-12
SDu = SD / np.sqrt(SDl2)[:, None]

def rim_dist_tang(p, dv):
    """点p到轮廓折线距离 + 方向dv与最近轮廓段切向夹角(度)"""
    t = np.clip(np.einsum('ij,ij->i', p - S0, SD) / SDl2, 0, 1)
    proj = S0 + t[:, None] * SD
    d = np.linalg.norm(proj - p[None, :], axis=1)
    i = int(d.argmin())
    c = abs(np.dot(dv, SDu[i]) / (np.linalg.norm(dv) + 1e-12))
    return d[i], math.degrees(math.acos(np.clip(c, 0, 1)))

sel = set()
dmax = 0.0; n_rej_tang = 0; n_rej_dist = 0
for p in rim_all:
    ab = E1 - E0
    ap = p - E0
    t = np.einsum('ij,ij->i', ap, ab) / (np.einsum('ij,ij->i', ab, ab) + 1e-12)
    tc = np.clip(t, 0, 1)
    proj = E0 + tc[:, None] * ab
    d = np.linalg.norm(proj - p[None, :], axis=1)
    i = int(np.argmin(d))
    if d[i] >= THRESH:
        n_rej_dist += 1; continue
    mid = Emid[i]; dv = E1[i] - E0[i]
    dm, ang = rim_dist_tang(mid, dv)
    if ang >= 35.0:
        n_rej_tang += 1; continue
    sel.add(i)
    dmax = max(dmax, d[i])
print(f"最近边法+切向过滤: 距离阈值={THRESH*1000:.2f}mm 切向<35° 选中边={len(sel)} "
      f"拒(距离)={n_rej_dist} 拒(斜跨)={n_rej_tang} rim点距边max={dmax*1000:.2f}mm")

# ---- 写bevel权重: 只有选中边=1, 其余全0(碎线清零) ----
bw_attr = me.attributes.get("bevel_weight_edge")
if bw_attr is None:
    bw_attr = me.attributes.new(name="bevel_weight_edge", type='FLOAT', domain='EDGE')
vals = np.zeros(len(me.edges), dtype=np.float32)
for i in sel:
    vals[i] = 1.0
bw_attr.data.foreach_set("value", vals)
me.update()
nz = int((vals > 0).sum())
print(f"bevel_weight_edge: 非零={nz} / {len(me.edges)} (其余全0)")

# ---- 倒角修改器(参数与旧版一致) ----
if head.modifiers.get("RimBevel"):
    head.modifiers.remove(head.modifiers["RimBevel"])
bev = head.modifiers.new("RimBevel", 'BEVEL')
bev.width = 0.0005   # 0.5mm
bev.segments = 2
bev.limit_method = 'WEIGHT'
bev.angle_limit = 0.0

bpy.ops.wm.save_mainfile(filepath=OUT_BLEND)
print(f"已保存: {OUT_BLEND}")
print("RIM_BEVEL_DONE")
