"""v37 渲染验证: 法线方向着色(正=绿/反=红) + UV棋盘格, 正面/侧面特写.
用shader的Backfacing让反法线面变红, 明确显示面朝向问题.
"""
import bpy, os, json, sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]

def load_3ddfa():
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    return Vector(d["L"]["center_3d"]), Vector(d["R"]["center_3d"])
cL, cR = load_3ddfa()

# 清除所有材质, 建两个材质: 法线检查(反=红) + UV棋盘格
mat_norm = bpy.data.materials.new("norm_check")
mat_norm.use_nodes = True
nt = mat_norm.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
out = nt.nodes.new("ShaderNodeOutputMaterial")
out.location = (300, 0)
geo = nt.nodes.new("ShaderNodeNewGeometry")
geo.location = (-200, 0)
mix = nt.nodes.new("ShaderNodeMix")
mix.data_type = 'RGBA'
mix.blend_type = 'MIX'
mix.location = (100, 0)
# front = green (0.2,0.8,0.2), back = red (0.8,0.1,0.1)
mix.inputs[6].default_value = (0.8, 0.1, 0.1, 1.0)  # A = back (red)
mix.inputs[7].default_value = (0.2, 0.8, 0.2, 1.0)  # B = front (green)
nt.links.new(geo.outputs['Backfacing'], mix.inputs['Factor'])
nt.links.new(mix.outputs['Result'], out.inputs['Surface'])

mat_uv = bpy.data.materials.new("uv_check")
mat_uv.use_nodes = True
ut = mat_uv.node_tree
for n in list(ut.nodes): ut.nodes.remove(n)
o2 = ut.nodes.new("ShaderNodeOutputMaterial")
o2.location = (400, 0)
tc = ut.nodes.new("ShaderNodeTexCoord")
tc.location = (-300, 0)
ck = ut.nodes.new("ShaderNodeTexChecker")
ck.location = (0, 0)
ck.inputs['Scale'].default_value = 50.0
bsdf = ut.nodes.new("ShaderNodeBsdfPrincipled")
bsdf.location = (200, 0)
ut.links.new(tc.outputs['UV'], ck.inputs['Vector'])
ut.links.new(ck.outputs['Color'], bsdf.inputs['Base Color'])
ut.links.new(bsdf.outputs['BSDF'], o2.inputs['Surface'])

# 场景设置
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1200
scene.render.resolution_y = 1200

cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.collection.objects.link(cam) if not cam.users_scene else None
scene.camera = cam

face_center = Vector(((cL[0]+cR[0])/2, min(cL[1], cR[1]), (cL[2]+cR[2])/2))
center = face_center

def render(prefix, mat, dist=0.30):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for name, pos in [
        ("front", Vector((center.x, center.y - dist, center.z))),
        ("sideL", Vector((center.x - dist, center.y, center.z))),
    ]:
        cam.location = pos
        look = center - pos
        cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(SHOT_DIR, f"{prefix}_{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"shot: {scene.render.filepath}")

# 法线检查渲染
render("v37_norm", mat_norm)
# UV棋盘格渲染
render("v37_uv", mat_uv)

# 保存独立blend供用户在GUI检查
out_check = os.path.join(os.path.dirname(OUT_BLEND), "01_1_eye_socket_v37_check.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_check)
print(f"Saved check blend: {out_check}")
print("=== 渲染完成 ===")
