"""渲染肩部打点参考图: 正面+侧面, 在肩关节点画红圈标记, 标注位置说明.
目的: 让用户清楚肩点该放哪(肱骨头, 不是三角肌中点/锁骨末端)."""
import bpy, os
import numpy as np
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
MARKERS = os.path.join(DELIVERY, "05骨骼绑定", "A_半自动打点", "06_rig_markers.blend")
OUT_DIR = os.path.join(DELIVERY, "05骨骼绑定", "screenshots")
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=MARKERS)
body = max([o for o in bpy.data.objects if o.type == 'MESH' and 'eye' not in o.name.lower()],
           key=lambda o: len(o.data.vertices))
body.display_type = 'WIRE'   # 线框显示, 看清结构

# 肩关节点位置: 从测量数据取(肱骨头, 三角肌深层)
import json
joints = json.load(open(os.path.join(DELIVERY, "05骨骼绑定", "A_半自动打点", "joints_measured.json"), encoding="utf-8"))
sh_r = np.array(joints["Shoulder_R"])
sh_l = np.array([-sh_r[0], sh_r[1], sh_r[2]])

# 在肩点放大号红色球标记
for name, pos in [("肩标记_R", sh_r), ("肩标记_L", sh_l)]:
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.018, location=tuple(pos))
    m = bpy.context.active_object
    m.name = name
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1.0, 0.05, 0.05, 1.0)
    mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 2.0
    m.data.materials.append(mat)

# 渲染设置
s = bpy.context.scene
s.render.engine = 'BLENDER_EEVEE'
s.render.resolution_x = 1000; s.render.resolution_y = 1200
for nm in ("Key", "Fill", "Rim"):
    o = bpy.data.objects.get(nm)
    if o: bpy.data.objects.remove(o, do_unlink=True)
for name, loc_rel, energy in [("Key", Vector((0.4, -1.5, 1.0)), 40),
                              ("Fill", Vector((-0.8, -0.5, 0.3)), 15),
                              ("Rim", Vector((0, 1.5, 0.8)), 25)]:
    ld = bpy.data.lights.new(name, type='AREA'); ld.energy = energy; ld.size = 1.5
    lo = bpy.data.objects.new(name, ld); lo.location = Vector((0, 0, 1.3)) + loc_rel
    lo.rotation_euler = (Vector((0, 0, 1.3)) - lo.location).to_track_quat('-Z', 'Y').to_euler()
    s.collection.objects.link(lo)
if s.world is None: s.world = bpy.data.worlds.new("World")
s.world.use_nodes = True
bg = s.world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.15, 0.15, 0.17, 1.0); bg.inputs['Strength'].default_value = 0.5

cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if not cam.users_scene: s.collection.objects.link(cam)
s.camera = cam
cam.data.lens = 85

# 正面: 聚焦肩颈区域
shoulder_center = Vector((0, 0, 1.44))
cam.location = shoulder_center + Vector((0, -1.3, 0.05))
cam.rotation_euler = (shoulder_center - cam.location).to_track_quat('-Z', 'Y').to_euler()
s.render.filepath = os.path.join(OUT_DIR, "肩部打点参考_正面.png")
bpy.ops.render.render(write_still=True)
print("shot: 肩部打点参考_正面.png")

# 侧面: 看肩的前后深度
cam.location = shoulder_center + Vector((1.3, 0, 0.05))
cam.rotation_euler = (shoulder_center - cam.location).to_track_quat('-Z', 'Y').to_euler()
s.render.filepath = os.path.join(OUT_DIR, "肩部打点参考_侧面.png")
bpy.ops.render.render(write_still=True)
print("shot: 肩部打点参考_侧面.png")

print("SHOULDER_REF_DONE")
