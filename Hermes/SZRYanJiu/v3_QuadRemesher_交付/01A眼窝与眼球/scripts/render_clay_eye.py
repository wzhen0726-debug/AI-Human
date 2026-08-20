"""渲染当前01_1模型的素模(无贴图)眼部特写, 供用户查看M形线确切位置.
相机: 正对R眼, 85mm长焦, AREA三灯. 材质: 灰色matcap素模.
"""
import bpy, os, sys, json
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *
OUT_TAG = os.environ.get("RENDER_TAG", "v47B")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]

ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))
cL = Vector(ddfa["L"]["center_3d"]); cR = Vector(ddfa["R"]["center_3d"])
center = Vector(((cL.x+cR.x)/2, min(cL.y,cR.y), (cL.z+cR.z)/2))

# 素模材质: 灰色, 无贴图
mat = bpy.data.materials.new("clay")
mat.use_nodes = True
nt = mat.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
out = nt.nodes.new("ShaderNodeOutputMaterial")
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
bsdf.inputs['Base Color'].default_value = (0.7, 0.7, 0.7, 1.0)
bsdf.inputs['Roughness'].default_value = 0.6
nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
obj.data.materials.clear()
obj.data.materials.append(mat)

# 三灯
for o in [x for x in bpy.data.objects if x.type == 'LIGHT']:
    bpy.data.objects.remove(o, do_unlink=True)
def add_light(name, loc, energy, size=1.0):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.size = size
    lo = bpy.data.objects.new(name, ld); lo.location = loc
    lo.rotation_euler = (center-loc).to_track_quat('-Z','Y').to_euler()
    bpy.context.collection.objects.link(lo)
add_light("key", Vector((center.x-0.3, center.y-0.4, center.z+0.3)), 100, 0.5)
add_light("fill", Vector((center.x+0.3, center.y-0.35, center.z+0.1)), 35, 0.8)
add_light("rim", Vector((center.x, center.y+0.4, center.z+0.35)), 50, 0.4)
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world; world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg: bg.inputs['Color'].default_value = (0.15,0.15,0.15,1.0); bg.inputs['Strength'].default_value = 0.5

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1600; scene.render.resolution_y = 1200
cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if cam.name not in bpy.context.collection.objects: bpy.context.collection.objects.link(cam)
scene.camera = cam
cam.data.lens = 85

# R眼特写(正视, 略偏下让下半部清楚)
eye = cR
cam.location = Vector((eye.x, eye.y - 0.10, eye.z + 0.005))
cam.rotation_euler = (eye - cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath = os.path.join(SHOT_DIR, f"{OUT_TAG}_R_eye_clay.png")
bpy.ops.render.render(write_still=True)
print("saved:", scene.render.filepath)

# 下半部特写
cam.location = Vector((eye.x, eye.y - 0.10, eye.z - 0.008))
cam.rotation_euler = (Vector((eye.x, eye.y, eye.z-0.005)) - cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath = os.path.join(SHOT_DIR, f"{OUT_TAG}_R_eye_lower_clay.png")
bpy.ops.render.render(write_still=True)
print("saved:", scene.render.filepath)