"""render_eyeball_side: 渲染眼球摆入侧视图(判断突出/包裹)"""
import bpy, os, sys, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
objs = [o for o in bpy.data.objects if o.type == 'MESH']
eyeL = [o for o in objs if 'Eye_R' in o.name][0]
eyeR = [o for o in objs if 'Eye_L' in o.name][0]
cL = Vector(eyeL.matrix_world.translation); cR = Vector(eyeR.matrix_world.translation)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 900; scene.render.resolution_y = 700

face_center = Vector(((cL.x+cR.x)/2, min(cL.y, cR.y), (cL.z+cR.z)/2))
# AREA三灯(同run_eyeball, 防SUN过曝)
for name, loc, energy in [("Key", (0, -1, 0.5), 120), ("Fill", (0.5, 0.3, 0), 40), ("Rim", (0, 1, 0.3), 60)]:
    ld = bpy.data.lights.new(name, type='AREA'); ld.energy = energy; ld.size = 1.0
    lo = bpy.data.objects.new(name, ld); lo.location = loc
    look = face_center - Vector(loc)
    lo.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(lo)
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.6, 0.6, 0.6, 1.0)
    bg.inputs['Strength'].default_value = 0.8

cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if not cam.users_scene:
    scene.collection.objects.link(cam)
scene.camera = cam
cam.data.lens = 85

# 左侧视图: 从模型左侧(-X)看眼区, 判断眼球突出/眼睑包裹
side_pos = Vector((face_center.x - 0.22, face_center.y - 0.06, face_center.z + 0.02))
cam.location = side_pos
look = face_center - side_pos
cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = os.path.join(SHOT_DIR, "01_2_eyeball_side.png")
bpy.ops.render.render(write_still=True)
print(f"shot: {scene.render.filepath}")
