"""高模rim材质标记: 给眼窝rim带指定独立材质ID, QR会在材质边界自动放edge loop.
原理: QR的UseMaterialIds=1时, 材质边界=强制edge loop位置 → rim锐利."""
import bpy, os, json, bmesh
import numpy as np
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
HI_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")
OUT_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket_rim_mat.blend")
XZ_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")
cont = json.load(open(XZ_JSON, encoding="utf-8"))

bpy.ops.wm.open_mainfile(filepath=HI_BLEND)
head = max([o for o in bpy.data.objects if o.type == 'MESH'],
           key=lambda o: len(o.data.vertices))
print(f"高模: {head.name} 顶点={len(head.data.vertices)}")
me = head.data
mw = head.matrix_world

# 创建rim材质(红色, 便于识别)
rim_mat = bpy.data.materials.new("RimMat")
rim_mat.use_nodes = True
rim_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1.0, 0.2, 0.2, 1.0)
me.materials.append(rim_mat)
rim_idx = len(me.materials) - 1

# 给rim带面指定rim材质
bm = bmesh.new()
bm.from_mesh(me)
bm.faces.ensure_lookup_table()
sel = 0
for side in ("L", "R"):
    rim = np.array(cont[side]["rim_3d"], dtype=np.float64)
    for f in bm.faces:
        fc = np.array(mw @ f.calc_center_median())
        d = np.linalg.norm(fc[None, :] - rim, axis=1).min()
        if d < 0.004:  # rim±4mm内
            f.material_index = rim_idx
            sel += 1
bm.to_mesh(me)
bm.free()
print(f"rim带标记面数: {sel}")

bpy.ops.wm.save_mainfile(filepath=OUT_BLEND)
print(f"已保存: {OUT_BLEND}")
print("RIM_MAT_DONE")
