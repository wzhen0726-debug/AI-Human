"""render_compare_input: 渲染输入模型(01_highpoly_repair.blend)眼区特写
对比目的: 判断白弧/褶皱是输入模型固有, 还是01A管线引入
"""
import bpy, os, sys, json
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]

with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])
center = Vector(((cL[0]+cR[0])/2, min(cL[1], cR[1]), (cL[2]+cR[2])/2))

# 三灯照明(与v39一致)
for o in [x for x in bpy.data.objects if x.type == 'LIGHT']:
    bpy.data.objects.remove(o, do_unlink=True)

def add_light(name, loc, energy, size=1.0):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy; ld.size = size
    lo = bpy.data.objects.new(name, ld)
    lo.location = loc
    look = center - loc
    lo.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.collection.objects.link(lo)

add_light("key", Vector((center.x-0.35, center.y-0.45, center.z+0.35)), 120, 0.6)
add_light("fill", Vector((center.x+0.35, center.y-0.40, center.z+0.15)), 40, 1.0)
add_light("rim", Vector((center.x, center.y+0.45, center.z+0.40)), 60, 0.5)

world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.6, 0.6, 0.6, 1.0)
    bg.inputs['Strength'].default_value = 0.8

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1200
scene.render.resolution_y = 1200

cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if cam.name not in bpy.context.collection.objects:
    bpy.context.collection.objects.link(cam)
scene.camera = cam
cam.data.lens = 85

for side_name, eye_c in [("L", cL), ("R", cR)]:
    for name, pos in [
        ("eye_front", Vector((eye_c.x, eye_c.y - 0.12, eye_c.z))),
        ("eye_side", Vector((eye_c.x - 0.10, eye_c.y - 0.02, eye_c.z))),
    ]:
        cam.location = pos
        look = eye_c - pos
        cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(SHOT_DIR, f"INPUT_{side_name}_{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"shot: {scene.render.filepath}")

print("输入模型对比渲染完成")
