import bpy, os, sys
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]

def load_3ddfa():
    import json
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    return Vector(d["L"]["center_3d"]), Vector(d["R"]["center_3d"])
cL, cR = load_3ddfa()
center = Vector(((cL[0]+cR[0])/2, min(cL[1], cR[1]), (cL[2]+cR[2])/2))

# ============ v40: 标准三灯光照(修复验证图过暗) ============
# 删旧灯
for o in [x for x in bpy.data.objects if x.type == 'LIGHT']:
    bpy.data.objects.remove(o, do_unlink=True)

def add_light(name, loc, energy, size=1.0):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.size = size
    lo = bpy.data.objects.new(name, ld)
    lo.location = loc
    look = center - loc
    lo.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.collection.objects.link(lo)
    return lo

# 主光(前上左), 补光(前上右弱), 轮廓光(上后)
add_light("key", Vector((center.x-0.35, center.y-0.45, center.z+0.35)), 120, 0.6)
add_light("fill", Vector((center.x+0.35, center.y-0.40, center.z+0.15)), 40, 1.0)
add_light("rim", Vector((center.x, center.y+0.45, center.z+0.40)), 60, 0.5)

# 环境光
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.6, 0.6, 0.6, 1.0)
    bg.inputs['Strength'].default_value = 0.8

# ============ 法线检查材质 ============
mat_norm = bpy.data.materials.new("norm")
mat_norm.use_nodes = True
nt = mat_norm.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
out = nt.nodes.new("ShaderNodeOutputMaterial")
geo = nt.nodes.new("ShaderNodeNewGeometry")
mix = nt.nodes.new("ShaderNodeMix")
mix.data_type = 'RGBA'
mix.blend_type = 'MIX'
mix.inputs[6].default_value = (0.8, 0.1, 0.1, 1.0)
mix.inputs[7].default_value = (0.2, 0.8, 0.2, 1.0)
nt.links.new(geo.outputs['Backfacing'], mix.inputs['Factor'])
nt.links.new(mix.outputs['Result'], out.inputs['Surface'])

# ============ 皮肤纹理材质 ============
mat_tex = None
for m in bpy.data.materials:
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                mat_tex = m
                break
        if mat_tex: break
if mat_tex is None:
    print("!! 找不到贴图材质")

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1200
scene.render.resolution_y = 1200

cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if cam.name not in bpy.context.collection.objects:
    bpy.context.collection.objects.link(cam)
scene.camera = cam

for prefix, mat in [("v39_norm", mat_norm), ("v39_tex", mat_tex)]:
    if mat is None: continue
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for name, pos in [("front", Vector((center.x, center.y - 0.30, center.z))),
                      ("sideL", Vector((center.x - 0.30, center.y, center.z)))]:
        cam.location = pos
        look = center - pos
        cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(SHOT_DIR, f"{prefix}_{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"shot: {scene.render.filepath}")

# ============ 眼部特写(放大检查边缘+交缝) ============
obj.data.materials.clear()
obj.data.materials.append(mat_tex)
for side_name, eye_c in [("L", cL), ("R", cR)]:
    for name, pos in [
        ("eye_front", Vector((eye_c.x, eye_c.y - 0.12, eye_c.z))),
        ("eye_side", Vector((eye_c.x - 0.10, eye_c.y - 0.02, eye_c.z))),
    ]:
        cam.location = pos
        look = eye_c - pos
        cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
        # 放大: 相机靠近,FOV 减小
        cam.data.lens = 85
        scene.render.filepath = os.path.join(SHOT_DIR, f"v39_{side_name}_{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"shot: {scene.render.filepath}")
    cam.data.lens = 50  # 恢复

print("渲染完成")
