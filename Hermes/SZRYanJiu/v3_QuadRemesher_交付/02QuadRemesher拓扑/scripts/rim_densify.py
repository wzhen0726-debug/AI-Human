"""低模眼窝rim局部加密: 选rim带面→细分→Shrinkwrap回高模表面→平滑.
让rim边缘更锐利, 不动其他区域."""
import bpy, os, json, bmesh
import numpy as np
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
LOW_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend")
HI_BLEND  = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")
OUT_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_rim_dense.blend")
XZ_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")
cont = json.load(open(XZ_JSON, encoding="utf-8"))

# 1. 打开低模, 选rim带面(距rim轮廓<5mm)
bpy.ops.wm.open_mainfile(filepath=LOW_BLEND)
head = max([o for o in bpy.data.objects if o.type == 'MESH'],
           key=lambda o: len(o.data.vertices))
mw = head.matrix_world
me = head.data

bpy.context.view_layer.objects.active = head
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.object.mode_set(mode='OBJECT')

# 标记rim带面
sel = 0
for p in me.polygons:
    fc = np.array(mw @ p.center)
    keep = False
    for side in ("L", "R"):
        rim = np.array(cont[side]["rim_3d"], dtype=np.float64)
        if np.linalg.norm(fc[None, :] - rim, axis=1).min() < 0.005:
            keep = True; break
    p.select = keep
    if keep: sel += 1
print(f"rim带选中面数: {sel}")

# 2. 细分这些面(1次, cut_number=2 → 每面变4小面)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=2, smoothness=0.0)
bpy.ops.object.mode_set(mode='OBJECT')
me = head.data
print(f"细分后总面数: {len(me.polygons)}")

# 3. Shrinkwrap投射回高模表面(保持rim形状不漂移)
bpy.ops.wm.append(filepath=os.path.join(HI_BLEND, "Object"),
                  directory=os.path.join(HI_BLEND, "Object"),
                  filename="tripo_node_89f96507-4268-42bd-8c27-bf6892366069", autoselect=False)
hi = bpy.data.objects.get("tripo_node_89f96507-4268-42bd-8c27-bf6892366069")
if hi is None:
    # 找新append进来的大mesh
    hi = max([o for o in bpy.data.objects if o.type == 'MESH' and o != head],
             key=lambda o: len(o.data.vertices))
print(f"高模参考: {hi.name} 顶点={len(hi.data.vertices)}")

sw = head.modifiers.new("ShrinkToHi", 'SHRINKWRAP')
sw.target = hi
sw.wrap_method = 'NEAREST_SURFACEPOINT'
sw.offset = 0.0
# 只作用rim带: 建顶点组
vg = head.vertex_groups.new(name="RimDense")
mw2 = head.matrix_world
rim_verts = []
for v in me.vertices:
    w = np.array(mw2 @ v.co)
    for side in ("L", "R"):
        rim = np.array(cont[side]["rim_3d"], dtype=np.float64)
        if np.linalg.norm(w[None, :] - rim, axis=1).min() < 0.006:
            rim_verts.append(v.index); break
vg.add(rim_verts, 1.0, 'REPLACE')
sw.vertex_group = "RimDense"
print(f"Shrinkwrap顶点组: {len(rim_verts)}顶点")

# 4. 平滑rim带(去细分锯齿)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.object.mode_set(mode='OBJECT')
for i in rim_verts:
    me.vertices[i].select = True
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.vertices_smooth(factor=0.3, repeat=2)
bpy.ops.object.mode_set(mode='OBJECT')

bpy.ops.wm.save_mainfile(filepath=OUT_BLEND)
print(f"已保存: {OUT_BLEND}")
print(f"最终面数: {len(head.data.polygons)}")
print("RIM_DENSE_DONE")
