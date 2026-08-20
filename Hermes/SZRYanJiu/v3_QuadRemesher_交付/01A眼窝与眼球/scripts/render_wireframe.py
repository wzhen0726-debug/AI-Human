"""渲染当前01_1模型线框模式R眼特写, 确认M形线是否消除."""
import bpy, os, sys, json
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]

ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))
cR = Vector(ddfa["R"]["center_3d"])

# 线框材质
mat = bpy.data.materials.new("wire")
mat.use_nodes = True
nt = mat.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
out = nt.nodes.new("ShaderNodeOutputMaterial")
wire = nt.nodes.new("ShaderNodeWireframe")
wire.inputs['Size'].default_value = 0.0005
em = nt.nodes.new("ShaderNodeEmission")
em.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
nt.links.new(wire.outputs[0], em.inputs[0])
nt.links.new(em.outputs[0], out.inputs['Surface'])
obj.data.materials.clear()
obj.data.materials.append(mat)

# 灯光
for o in [x for x in bpy.data.objects if x.type == 'LIGHT']:
    bpy.data.objects.remove(o, do_unlink=True)
ld = bpy.data.lights.new("sun", 'SUN')
ld.energy = 2.0
lo = bpy.data.objects.new("sun", ld)
lo.rotation_euler = (0.8, 0.2, 0.5)
bpy.context.collection.objects.link(lo)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1600; scene.render.resolution_y = 1200
scene.render.film_transparent = False
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.color = (0.9, 0.9, 0.9)

cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if cam.name not in bpy.context.collection.objects: bpy.context.collection.objects.link(cam)
scene.camera = cam
cam.data.lens = 85
cam.location = Vector((cR.x, cR.y - 0.12, cR.z))
cam.rotation_euler = (cR - cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath = os.path.join(SHOT_DIR, f"{os.environ.get('RENDER_TAG', 'v47B')}_R_wireframe.png")
bpy.ops.render.render(write_still=True)
print("saved:", scene.render.filepath)