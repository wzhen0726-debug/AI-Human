"""诊断: 低模眼窝交界处(rim)为什么不锐利.
测量: 1) rim带内面片平均尺寸(密度够不够) 2) rim轮廓边缘的形状保持
3) rim边缘的锐度(法线变化角度) — 高模是锐利折角, 低模可能被磨圆."""
import bpy, os, json, sys
import numpy as np
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
LOG = os.path.join(DELIVERY, "02QuadRemesher拓扑", "logs", "rim_diag_result.txt")
os.makedirs(os.path.dirname(LOG), exist_ok=True)
def out(msg):
    out(msg)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
if os.path.exists(LOG):
    os.remove(LOG)
LOW_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend")
XZ_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")
cont = json.load(open(XZ_JSON, encoding="utf-8"))

bpy.ops.wm.open_mainfile(filepath=LOW_BLEND)
head = max([o for o in bpy.data.objects if o.type == 'MESH'],
           key=lambda o: len(o.data.vertices))
me = head.data
mw = head.matrix_world
hp = np.array([mw @ v.co for v in me.vertices])

for side in ("L", "R"):
    c = np.array(cont[side]["center"], dtype=np.float64)
    rim3d = np.array(cont[side]["rim_3d"], dtype=np.float64)
    # rim带顶点: 距rim折线任一顶点 < 4mm
    d_rim = np.array([np.linalg.norm(p - rim3d, axis=1).min() for p in hp])
    rim_band = d_rim < 0.004
    # rim带内的面: 面心在rim带内
    faces_rim = []
    for poly in me.polygons:
        fc = mw @ poly.center
        if np.linalg.norm(fc - rim3d, axis=1).min() < 0.004:
            faces_rim.append(poly)
    areas = [p.area for p in faces_rim]
    edges_len = []
    for p in faces_rim:
        for ek in p.edge_keys:
            e = me.edges[ek]
            v0 = np.array(mw @ me.vertices[e.vertices[0]].co)
            v1 = np.array(mw @ me.vertices[e.vertices[1]].co)
            edges_len.append(np.linalg.norm(v1 - v0))
    # 锐度: rim带内相邻面法线夹角分布
    out(f"=== {side} rim带 ===")
    out(f"  rim带顶点={int(rim_band.sum())} 面数={len(faces_rim)}")
    if areas:
        out(f"  面平均面积={np.mean(areas)*1e6:.2f}mm²  等效边长≈{np.sqrt(np.mean(areas))*1000:.2f}mm")
    if edges_len:
        out(f"  边长: 均值={np.mean(edges_len)*1000:.2f}mm 最大={np.max(edges_len)*1000:.2f}mm")
    # 开口高12mm ÷ 边长 = rim上下各能摆几排面
    if edges_len:
        rows = 12.2 / (np.mean(edges_len) * 1000)
        out(f"  开口高12.2mm ÷ 平均边长 → rim区域约{rows:.1f}排面")
out("RIM_DIAG_DONE")
