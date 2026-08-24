"""高模rim预锐化: 在01_1眼窝高模的rim处加一道小倒角(0.3mm), 让QR的AutoDetectHardEdges能检测到折角.
原理: QR会自动在硬边(角度>阈值)处放置边循环. rim处加倒角=制造硬边=QR自动沿rim布线."""
import bpy, os, json, bmesh
import numpy as np
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
HI_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")
OUT_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket_rim_sharp.blend")
XZ_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")
cont = json.load(open(XZ_JSON, encoding="utf-8"))

bpy.ops.wm.open_mainfile(filepath=HI_BLEND)
head = max([o for o in bpy.data.objects if o.type == 'MESH'],
           key=lambda o: len(o.data.vertices))
print(f"高模: {head.name} 顶点={len(head.data.vertices)}")

# 找rim带内的边(距rim轮廓<2mm)
mw = head.matrix_world
me = head.data
bm = bmesh.new()
bm.from_mesh(me)
bm.edges.ensure_lookup_table()

rim_edges = []
for side in ("L", "R"):
    rim = np.array(cont[side]["rim_3d"], dtype=np.float64)
    for e in bm.edges:
        v0 = np.array(mw @ e.verts[0].co)
        v1 = np.array(mw @ e.verts[1].co)
        mid = (v0 + v1) / 2
        d = np.linalg.norm(mid[None, :] - rim, axis=1).min()
        if d < 0.002:  # rim±2mm内
            rim_edges.append(e)

print(f"rim带边数: {len(rim_edges)}")

# 给rim边加倒角权重(让倒角修改器只作用rim)
bevel_weight = me.attributes.get("bevel_weight_edge")
if bevel_weight is None:
    bevel_weight = me.attributes.new(name="bevel_weight_edge", type='FLOAT', domain='EDGE')
for e in rim_edges:
    bevel_weight.data[e.index].value = 1.0
bm.to_mesh(me)
bm.free()

# 加倒角修改器(小倒角, 制造硬边)
bev = head.modifiers.new("RimBevel", 'BEVEL')
bev.width = 0.0003   # 0.3mm
bev.segments = 2
bev.limit_method = 'WEIGHT'
bev.angle_limit = 0.0

bpy.ops.wm.save_mainfile(filepath=OUT_BLEND)
print(f"已保存: {OUT_BLEND}")
print("RIM_PRE_SHARP_DONE")
