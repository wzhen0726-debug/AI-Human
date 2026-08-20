"""渲染原始高模眼区正视图, 检查眼睛几何状态(睁眼/闭眼/眼窝形状)."""
import bpy, os, sys
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
cL = Vector(IRIS_L); cR = Vector(IRIS_R)
center = Vector(((cL[0]+cR[0])/2, min(cL[1], cR[1]), (cL[2]+cR[2])/2))

# AREA三灯
for o in [x for x in bpy.data.objects if x.type == 'LIGHT']:
    bpy.data.objects.remove(o, do_unlink=True)
def add_light(name, loc, energy, size=1.0):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.size = size
    lo = bpy.data.objects.new(name, ld); lo.location = loc
    lo.rotation_euler = (center-loc).to_track_quat('-Z','Y').to_euler()
    bpy.context.collection.objects.link(lo)
add_light("key", Vector((center.x-0.35, center.y-0.45, center.z+0.35)), 120, 0.6)
add_light("fill", Vector((center.x+0.35, center.y-0.40, center.z+0.15)), 40, 1.0)
add_light("rim", Vector((center.x, center.y+0.45, center.z+0.40)), 60, 0.5)
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world; world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg: bg.inputs['Color'].default_value = (0.6,0.6,0.6,1.0); bg.inputs['Strength'].default_value = 0.8

# 找贴图材质
mat_tex = None
for m in bpy.data.materials:
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image: mat_tex = m; break
        if mat_tex: break

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1200; scene.render.resolution_y = 1200
cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if cam.name not in bpy.context.collection.objects: bpy.context.collection.objects.link(cam)
scene.camera = cam

# 正面: 相机在眼区前方(Y=-0.30), 正交
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 0.08  # 80mm视口
cam.location = Vector((center.x, center.y-0.30, center.z))
cam.rotation_euler = (center-cam.location).to_track_quat('-Z','Y').to_euler()
obj.data.materials.clear()
if mat_tex: obj.data.materials.append(mat_tex)
scene.render.filepath = os.path.join(SHOT_DIR, "input_eye_front.png")
bpy.ops.render.render(write_still=True)
print(f"shot: {scene.render.filepath}")

# 左眼特写
cam.data.ortho_scale = 0.04
cam.location = Vector((cL.x, cL.y-0.15, cL.z))
cam.rotation_euler = (cL-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath = os.path.join(SHOT_DIR, "input_eye_L_closeup.png")
bpy.ops.render.render(write_still=True)
print(f"shot: {scene.render.filepath}")
print("渲染完成")