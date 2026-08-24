"""眼窝rim锐化: 给低模rim带加锐边标记+小倒角, 让眼睑交界视觉更锐利.
原理: QR低模面片在rim处平滑过渡, 锐边+倒角能做出折角感, 不动拓扑."""
import bpy, os, json, bmesh
import numpy as np
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
LOW_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend")
OUT_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_rim_sharp.blend")
XZ_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")
cont = json.load(open(XZ_JSON, encoding="utf-8"))

bpy.ops.wm.open_mainfile(filepath=LOW_BLEND)
head = max([o for o in bpy.data.objects if o.type == 'MESH'],
           key=lambda o: len(o.data.vertices))
mw = head.matrix_world
me = head.data

# 选rim带内的边: 距rim轮廓<3mm 且 法线夹角>15度(折角处)
bm = bmesh.new()
bm.from_mesh(me)
bm.edges.ensure_lookup_table()
bm.verts.ensure_lookup_table()

rim_sel = []
for side in ("L", "R"):
    rim = np.array(cont[side]["rim_3d"], dtype=np.float64)
    for e in bm.edges:
        v0 = np.array(mw @ e.verts[0].co)
        v1 = np.array(mw @ e.verts[1].co)
        mid = (v0 + v1) / 2
        d = np.linalg.norm(mid[None, :] - rim, axis=1).min()
        if d < 0.003:  # rim±3mm内
            # 相邻面法线夹角
            if len(e.link_faces) == 2:
                n0 = e.link_faces[0].normal
                n1 = e.link_faces[1].normal
                ang = np.degrees(np.arccos(np.clip(np.dot(n0, n1), -1, 1)))
                if ang > 12:  # 折角>12度才锐化
                    rim_sel.append(e)

print(f"rim锐化边数: {len(rim_sel)}")
# 标记锐边
for e in rim_sel:
    e.smooth = False
bm.to_mesh(me)
bm.free()

# 保存
bpy.ops.wm.save_mainfile(filepath=OUT_BLEND)
print(f"已保存: {OUT_BLEND}")
print("RIM_SHARP_DONE")
