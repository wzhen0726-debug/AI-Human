"""render_input_vs_output_eye: 对比 原始输入模型 vs 当前输出 的眼区
目的: 验证睫毛在原模型存在, 以及当前输出丢了睫毛
"""
import bpy, os, sys, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

import json
with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

def setup_scene():
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1000; scene.render.resolution_y = 1000
    for name, loc, energy in [("Key",(0,-1,0.5),120),("Fill",(0.5,0.3,0),40),("Rim",(0,1,0.3),60)]:
        ld = bpy.data.lights.new(name, type='AREA'); ld.energy=energy; ld.size=1.0
        lo = bpy.data.objects.new(name, ld); lo.location=loc
        look = Vector((0,0,0)) - Vector(loc)
        lo.rotation_euler = look.to_track_quat('-Z','Y').to_euler()
        scene.collection.objects.link(lo)
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (0.6,0.6,0.6,1.0)
        bg.inputs['Strength'].default_value = 0.8

def render_eye(blend_path, out_name):
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    obj = [o for o in bpy.data.objects if o.type=='MESH'][0]
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    setup_scene()
    scene = bpy.context.scene
    cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    if not cam.users_scene:
        scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 100
    target = cL
    cam.location = Vector((target.x, target.y - 0.05, target.z))
    look = target - cam.location
    cam.rotation_euler = look.to_track_quat('-Z','Y').to_euler()
    scene.render.filepath = os.path.join(SHOT_DIR, out_name)
    bpy.ops.render.render(write_still=True)
    print(f"shot: {scene.render.filepath}")

os.makedirs(SHOT_DIR, exist_ok=True)
render_eye(IN_BLEND, "cmp_INPUT_L_eye.png")
render_eye(OUT_BLEND, "cmp_OUTPUT_L_eye.png")
print("完成")
