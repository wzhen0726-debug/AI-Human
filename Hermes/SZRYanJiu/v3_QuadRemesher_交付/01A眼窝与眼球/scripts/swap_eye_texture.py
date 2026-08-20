"""swap_eye_texture.py - 把眼球灰色占位贴图换成真实MetaHuman眼球贴图
eye_01.glb自带T_Gray_Eyes_D(灰色占位). 备份maps/pifu/里有MI_Face_Eye_Left/Right_BaseColor(真实虹膜).
左右眼mesh名带L/R, 分别赋对应贴图. 保存回01_2 blend并渲染验证.
"""
import bpy, os, sys
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *

MAPS = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\低模导出备份勿动\maps\pifu"

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
eyes = [o for o in bpy.data.objects if o.type == 'MESH' and 'Eye' in o.name]
print(f"eyes: {[o.name for o in eyes]}")

# 检查现有材质贴图节点
for o in eyes:
    side = "L" if "_L" in o.name else "R"
    tex_path = os.path.join(MAPS, f"MI_Face_Eye_{'Left' if side=='L' else 'Right'}_NewMetaHumanCharacter_Head_BaseColor.png")
    img = bpy.data.images.load(tex_path, check_existing=True)
    img.colorspace_settings.name = 'sRGB'
    print(f"{o.name}: loaded {img.name} {img.size[0]}x{img.size[1]}")
    for mat in o.data.materials:
        if not mat or not mat.use_nodes: continue
        # 复制材质(避免两眼共享)
        mat.name = f"M_RealEye_{side}"
        for n in mat.node_tree.nodes:
            if n.type == 'TEX_IMAGE':
                old = n.image.name if n.image else None
                n.image = img
                print(f"  {mat.name}: TEX_IMAGE {old} -> {img.name}")

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"Saved: {OUT_BLEND}")

# 渲染验证(同run_eyeball的AREA三灯)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 800; scene.render.resolution_y = 800
import json
with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])
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
cam.data.lens = 85
for name, pos in [("front", Vector((face_center.x, face_center.y - 0.30, face_center.z))),
                  ("close", Vector((face_center.x, face_center.y - 0.12, face_center.z)))]:
    cam.location = pos
    look = face_center - pos
    cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(SHOT_DIR, f"01_2_realtex_{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"shot: {scene.render.filepath}")
print("SWAP DONE")
