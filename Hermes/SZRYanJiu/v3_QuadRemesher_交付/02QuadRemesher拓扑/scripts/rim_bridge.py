"""rim环桥接 v2: 把rim环的边界边与低模rim带边桥接(Bridge Edge Loops), 形成闭环."""
import bpy, os, json, bmesh
import numpy as np
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
RING_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_rim_ring.blend")
OUT_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_rim_bridged.blend")
XZ_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")
cont = json.load(open(XZ_JSON, encoding="utf-8"))

bpy.ops.wm.open_mainfile(filepath=RING_BLEND)
head = max([o for o in bpy.data.objects if o.type == 'MESH'],
           key=lambda o: len(o.data.vertices))
me = head.data
print(f"打开: {head.name} 顶点={len(me.vertices)} 面={len(me.polygons)}")

# 进入编辑模式
bpy.context.view_layer.objects.active = head
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='DESELECT')

# 找rim环的边界边(最后96个面是rim环)
bm = bmesh.new()
bm.from_mesh(me)
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()

rim_face_idx = set(range(len(me.polygons)-96, len(me.polygons)))
rim_faces = [bm.faces[i] for i in rim_face_idx if i < len(bm.faces)]
rim_boundary = []
for f in rim_faces:
    for e in f.edges:
        if len(e.link_faces) == 1:
            rim_boundary.append(e)
print(f"rim环边界边: {len(rim_boundary)}")

# 找低模rim带的边界边(距rim轮廓<5mm, 且不是rim环的边)
low_boundary = []
for e in bm.edges:
    if len(e.link_faces) == 1 and e not in rim_boundary:
        v0 = np.array(head.matrix_world @ e.verts[0].co)
        v1 = np.array(head.matrix_world @ e.verts[1].co)
        mid = (v0 + v1) / 2
        for side in ("L", "R"):
            rim = np.array(cont[side]["rim_3d"], dtype=np.float64)
            if np.linalg.norm(mid[None, :] - rim, axis=1).min() < 0.005:
                low_boundary.append(e)
                break
print(f"低模rim带边界边: {len(low_boundary)}")

# 选rim环边界边和低模rim带边
bpy.ops.mesh.select_all(action='DESELECT')
for e in rim_boundary + low_boundary:
    e.select = True
print(f"选中边数: {len(rim_boundary) + len(low_boundary)}")

# Bridge Edge Loops
bpy.ops.mesh.bridge_edge_loops()
bpy.ops.object.mode_set(mode='OBJECT')

bpy.ops.wm.save_mainfile(filepath=OUT_BLEND)
print(f"已保存: {OUT_BLEND}")
print("BRIDGE_DONE")
