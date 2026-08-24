"""低模rim倒角: 在低模rim带加0.5mm倒角, 让rim有几何锐利度, 再烘焙."""
import bpy, os, json, bmesh
import numpy as np
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
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

# 找rim带边(距rim轮廓<3mm)
bm = bmesh.new()
bm.from_mesh(me)
bm.edges.ensure_lookup_table()
rim_edges = []
for e in bm.edges:
    v0 = np.array(mw @ e.verts[0].co)
    v1 = np.array(mw @ e.verts[1].co)
    mid = (v0 + v1) / 2
    for side in ("L", "R"):
        rim = np.array(cont[side]["rim_3d"], dtype=np.float64)
        if np.linalg.norm(mid[None, :] - rim, axis=1).min() < 0.003:
            rim_edges.append(e)
            break
print(f"rim带边数: {len(rim_edges)}")

# 给rim边加倒角权重(直接用mesh边索引, 不用bmesh)
bm.to_mesh(me)
bm.free()
# 创建bevel_weight_edge属性
bw_attr = me.attributes.get("bevel_weight_edge")
if bw_attr is None:
    bw_attr = me.attributes.new(name="bevel_weight_edge", type='FLOAT', domain='EDGE')
# 直接用mesh边设置权重
me.update()
for e in me.edges:
    v0 = np.array(mw @ me.vertices[e.vertices[0]].co)
    v1 = np.array(mw @ me.vertices[e.vertices[1]].co)
    mid = (v0 + v1) / 2
    for side in ("L", "R"):
        rim = np.array(cont[side]["rim_3d"], dtype=np.float64)
        if np.linalg.norm(mid[None, :] - rim, axis=1).min() < 0.003:
            bw_attr.data[e.index].value = 1.0
            break

# 加倒角修改器
bev = head.modifiers.new("RimBevel", 'BEVEL')
bev.width = 0.0005   # 0.5mm
bev.segments = 2
bev.limit_method = 'WEIGHT'
bev.angle_limit = 0.0

bpy.ops.wm.save_mainfile(filepath=OUT_BLEND)
print(f"已保存: {OUT_BLEND}")
print("RIM_BEVEL_DONE")
