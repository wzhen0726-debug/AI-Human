"""补渲染: 真线框图(用Wireframe修改器, display_type不影响渲染)."""
import bpy, os
import numpy as np
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
LOW_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_with_eyes.blend")
OUT = os.path.join(DELIVERY, "汇报素材")

bpy.ops.wm.open_mainfile(filepath=LOW_BLEND)
head = max([o for o in bpy.data.objects if o.type == 'MESH' and 'Eye' not in o.name],
           key=lambda o: len(o.data.vertices))
eyes = [o for o in bpy.data.objects if o.name.startswith("Eye002")]
verts = head.data.vertices
hp = np.array([head.matrix_world @ verts[i].co for i in range(0, len(verts), 20)])
mn, mx = hp.min(axis=0), hp.max(axis=0)
center = Vector(((mn + mx) / 2).tolist())
size = float((mx - mn).max())

# 给头部加Wireframe修改器(把边变成真实几何, 渲染可见)
wf = head.modifiers.new("WireShow", 'WIREFRAME')
wf.thickness = size * 0.0004       # 线宽≈0.4mm(相对模型尺寸)
wf.use_replace = False             # 保留面+叠加线, 半透明效果更好
# 头部面设为半透明深色, 突出四边形网格
mat = bpy.data.materials.new("WireMat")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.35, 0.5, 0.75, 1.0)
bsdf.inputs["Alpha"].default_value = 0.25
mat.blend_method = 'BLEND' if hasattr(mat, 'blend_method') else 'BLEND'
head.data.materials.clear()
head.data.materials.append(mat)

s = bpy.context.scene
s.render.engine = 'BLENDER_EEVEE'
s.render.resolution_x = 1000; s.render.resolution_y = 1100
for name, loc_rel, energy in [("Key", Vector((0.25, -1.2, 0.7)), 40),
                              ("Fill", Vector((1.0, -0.4, 0.2)), 15),
                              ("Rim", Vector((0, 1.2, 0.6)), 20)]:
    ld = bpy.data.lights.new(name, type='AREA'); ld.energy = energy; ld.size = 1.2
    lo = bpy.data.objects.new(name, ld); lo.location = center + loc_rel
    lo.rotation_euler = (center - lo.location).to_track_quat('-Z', 'Y').to_euler()
    s.collection.objects.link(lo)
if s.world is None:
    s.world = bpy.data.worlds.new("World")
s.world.use_nodes = True
bg = s.world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.92, 0.92, 0.93, 1.0); bg.inputs['Strength'].default_value = 0.7

cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if not cam.users_scene:
    s.collection.objects.link(cam)
s.camera = cam
cam.data.lens = 85
for tag, off in [("wire_front", Vector((0, -size*1.35, size*0.05))),
                 ("wire_side", Vector((size*1.35, 0, size*0.05)))]:
    cam.location = center + off
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    s.render.filepath = os.path.join(OUT, f"低模_{tag}.png")
    bpy.ops.render.render(write_still=True)
    print(f"shot: 低模_{tag}.png")
print("WIRE_RENDER_DONE")
