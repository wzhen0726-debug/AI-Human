"""render_eye_corner_closeup: 渲染内外眼角特写(贴图模式), 定位UV错乱
针对vision报的'撕纸状贴片/断裂边缘'(内外眼角)
"""
import bpy, os, sys, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH' and 'tripo' in o.name][0]

import json
with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1000; scene.render.resolution_y = 1000

# AREA三灯
face_center = Vector(((cL.x+cR.x)/2, min(cL.y, cR.y), (cL.z+cR.z)/2))
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
cam.data.lens = 100  # 长焦特写

os.makedirs(SHOT_DIR, exist_ok=True)
# 左眼正前方特写
shots = [
    ("tex_L_eye", Vector((cL.x, cL.y - 0.05, cL.z))),
    ("tex_R_eye", Vector((cR.x, cR.y - 0.05, cR.z))),
]
for name, target in shots:
    cam.location = Vector((target.x, target.y - 0.001, target.z))
    cam.location.y = target.y - 0.05
    look = target - cam.location
    cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(SHOT_DIR, f"{name}_closeup.png")
    bpy.ops.render.render(write_still=True)
    print(f"shot: {scene.render.filepath}")
