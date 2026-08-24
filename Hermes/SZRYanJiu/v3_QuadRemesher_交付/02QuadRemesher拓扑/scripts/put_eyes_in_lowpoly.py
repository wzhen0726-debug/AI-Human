"""02低模 + 眼球验证 v2: 直接从已定案的高模眼球文件append现成眼球(位置/材质已验收).
比重新append零件再join更可靠, 且保证与高模版眼球位置完全一致."""
import bpy, os, json
import numpy as np
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
LOW_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend")
EYES_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_2_eyeball_placed.blend")
OUT_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_with_eyes.blend")
SHOT_DIR = os.path.join(DELIVERY, "02QuadRemesher拓扑", "screenshots")
os.makedirs(SHOT_DIR, exist_ok=True)

EYE_RADIUS = 14.5 / 1000.0   # 缩放后球半径(与管线一致)

bpy.ops.wm.open_mainfile(filepath=LOW_BLEND)
head = max([o for o in bpy.data.objects if o.type == 'MESH'],
           key=lambda o: len(o.data.vertices))
print(f"低模头部: {head.name} 顶点={len(head.data.vertices)}")
hp = np.array([head.matrix_world @ v.co for v in head.data.vertices])

# ---- append已定案的眼球(带材质+贴图+验收位置) ----
before = set(bpy.data.objects.keys())
for side in ("L", "R"):
    nm = f"Eye002_{side}"
    bpy.ops.wm.append(filepath=os.path.join(EYES_BLEND, "Object", nm),
                      directory=os.path.join(EYES_BLEND, "Object"),
                      filename=nm, autoselect=True)
new_eyes = [bpy.data.objects[n] for n in bpy.data.objects.keys()
            if n not in before and bpy.data.objects[n].type == 'MESH']
print(f"append到: {[o.name for o in new_eyes]}")
eyes = {}
for o in new_eyes:
    for side in ("L", "R"):
        if side in o.name:
            eyes[side] = o
print(f"眼球定位: {[(s, tuple(round(v,4) for v in o.location)) for s,o in eyes.items()]}")

# ---- 穿透统计: 皮肤顶点进入眼球球体的数量(眼球内部=被包住不可见, 属正常) ----
# 关键检查: 眼球前方可见区的皮肤是否穿到眼球外面(那才是穿帮)
for side, o in eyes.items():
    c = np.array(o.location, dtype=np.float64)
    d = np.linalg.norm(hp - c, axis=1)
    pen = EYE_RADIUS - d            # >0 = 顶点在球内(被眼球包住)
    front = hp[:, 1] < c[1]         # 眼球中心前方的皮肤
    hit = pen > 0.0002
    print(f"[穿透] {side}: 球内点数={hit.sum()} 正面可见区球内={int((hit&front).sum())} 最大穿入={pen.max()*1000:.2f}mm")

# ---- 给无贴图低模头一个基础肤色材质(否则EEVEE渲染灰黑) ----
if not head.data.materials:
    mat = bpy.data.materials.new("HeadSkin")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.45, 0.4, 1.0)
    head.data.materials.append(mat)
    print("已加基础肤色材质")

bpy.ops.wm.save_mainfile(filepath=OUT_BLEND)
print(f"已保存: {OUT_BLEND}")

# ---- 渲染对比 (灯位与01A验收一致: 40/15/20防过曝) ----
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1000; scene.render.resolution_y = 800
fc = sum((o.location for o in eyes.values()), Vector((0, 0, 0))) / len(eyes)
for name, loc_rel, energy in [("Key", Vector((0.1, -0.6, 0.35)), 40),
                              ("Fill", Vector((0.5, -0.2, 0.1)), 15),
                              ("Rim", Vector((0, 0.6, 0.3)), 20)]:
    ld = bpy.data.lights.new(name, type='AREA'); ld.energy = energy; ld.size = 0.6
    lo = bpy.data.objects.new(name, ld); lo.location = fc + loc_rel
    lo.rotation_euler = (fc - lo.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(lo)
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.62, 0.62, 0.64, 1.0); bg.inputs['Strength'].default_value = 0.6
cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if not cam.users_scene:
    scene.collection.objects.link(cam)
scene.camera = cam
for tag, loc in [("front", Vector((fc.x, fc.y - 0.25, fc.z + 0.004))),
                 ("close", Vector((fc.x, fc.y - 0.15, fc.z + 0.004))),
                 ("side", fc + Vector((0.25, 0, 0.004)))]:
    cam.location = loc
    cam.rotation_euler = (fc - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(SHOT_DIR, f"02_lowpoly_eyes_{tag}.png")
    bpy.ops.render.render(write_still=True)
    print(f"shot: 02_lowpoly_eyes_{tag}.png")
print("EYE_IN_LOWPOLY_DONE")
