"""01_2 眼球摆入 v2 — 眼睛模型002 (MetaHuman风格 虹膜+巩膜+阴影)

与run_eyeball.py(001 GLB)的区别:
1. 模型源: Eye.blend append (贴图打包在blend内, 支持19色变体)
2. 几何: 巩膜半径12.45mm → 缩放14.5/12.45对齐原验证角膜位置(角膜前极不变)
3. 朝向: 虹膜法线已朝-Y(正前方), 无需旋转
4. 颜色: EYE_COLOR/EYE_BLOODLINE配置切换, 或事后跑switch_eyeball_color.py

位置基准不变: x/z=3DDFA, y=拟合虚拟眼球球心 + PUSH_BACK.
"""
import bpy, os, sys, json
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *
from eye002_config import *

def measure_corneal_dist(eye):
    """自动测量角膜顶点距: 眼球对象原点(球心)到最前点(角膜顶点)的距离.
    换任何眼睛模型都自动适配, 不用手写半径/顶点位置."""
    ys = [v.co.y for v in eye.data.vertices]
    return abs(min(ys))

def compute_eye_position(side, corneal_dist):
    """解剖参考点定位(v3):
    x/z = 眼睑开口中心(用户手动标记, 与眼窝同基准)
    y   = 眼睑开口平面y + 角膜顶点距 - 凸出量
    深度参考是开口平面(左右几乎完全对称) → 两眼深度自动同步, 不再用拟合球心
    (拟合球心左右差0.4mm是上一版两眼不同步的根因)."""
    import json
    with open(EYE_XZ_JSON, encoding="utf-8") as f:
        cont = json.load(f)
    c = cont[side]["center"]
    rim_y = c[1]                                # 眼睑开口平面y(用户标记)
    cx = c[0]
    cz = c[2] + EYE_Z_OFFSET_MM / 1000.0        # 高度微调
    cy = rim_y + corneal_dist - EYE_PROTRUSION_MM / 1000.0
    return np.array([cx, cy, cz], dtype=np.float32), rim_y

def append_eye_objects():
    """从Eye.blend append虹膜/巩膜/阴影片(带材质+打包贴图).
    教训1: append后selected_objects会累积, 必须用对象集合差集识别本次新增.
    教训2: Eye.blend的父empty(Eye1)会跟着append进来, join后清除parent并删empty."""
    before = set(bpy.data.objects.keys())
    for name in EYE002_OBJECTS:
        bpy.ops.wm.append(filepath=os.path.join(EYE002_BLEND, "Object", name),
                          directory=os.path.join(EYE002_BLEND, "Object"),
                          filename=name, autoselect=True)
    objs = [bpy.data.objects[n] for n in bpy.data.objects.keys()
            if n not in before and bpy.data.objects[n].type == 'MESH']
    print(f"appended: {[o.name for o in objs]}")
    return objs

def unparent_eye(eye):
    """取消父节点(Eye1 empty), 保持世界变换. 层级简化为一只眼一个对象."""
    if eye.parent is not None:
        mat_world = eye.matrix_world.copy()
        eye.parent = None
        eye.matrix_world = mat_world
    # 删除残留的Eye1类empty(无子节点后). 教训: remove后对象引用失效, 先存名字再打印.
    for o in list(bpy.data.objects):
        if o.type == 'EMPTY' and o.name.startswith("Eye1") and not o.children:
            nm = o.name
            bpy.data.objects.remove(o, do_unlink=True)
            print(f"  删除残留父empty: {nm}")

def build_single_eye(objs, name):
    """合并三个mesh为一个眼球对象, 缩放到EYE_RADIUS_TARGET."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    eye = bpy.context.view_layer.objects.active
    eye.name = name
    # 缩放: 巩膜中位半径→目标半径 (角膜位置与001方案对齐)
    eye.location = (0, 0, 0)
    eye.scale = (EYE002_SCALE, EYE002_SCALE, EYE002_SCALE)
    bpy.ops.object.transform_apply(scale=True)
    return eye

def apply_eye_color(eye, color, bloodline):
    """切换颜色: 找材质中含'_D'的TEX_IMAGE节点换贴图(注册表路径)."""
    reg = json.load(open(EYE002_REGISTRY, encoding="utf-8"))
    variants = reg["colors"].get(color)
    if not variants:
        raise KeyError(f"未知颜色{color}, 可选: {list(reg['colors'].keys())}")
    tex_path = variants.get(bloodline) or variants.get("base")
    if bloodline not in variants:
        print(f"  {color}无{bloodline}变体, 回退base")
    tex_name = os.path.basename(tex_path)
    img = bpy.data.images.load(tex_path, check_existing=True)
    img.name = tex_name
    swapped = 0
    for slot in eye.data.materials:
        if not slot or not slot.use_nodes:
            continue
        for n in slot.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image and "_D" in n.image.name:
                n.image = img
                swapped += 1
    print(f"  {eye.name} 颜色={color}/{bloodline}: 替换{swapped}个贴图节点 → {tex_name}")

def main():
    print("=== 01_2 Eyeball v3 (解剖参考点定位, 换模型自动适配) ===")
    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)

    centers = []
    for side in ("L", "R"):
        objs = append_eye_objects()
        eye = build_single_eye(objs, f"Eye002_{side}")
        unparent_eye(eye)
        apply_eye_color(eye, EYE_COLOR, EYE_BLOODLINE)
        corneal_dist = measure_corneal_dist(eye)
        target, rim_y = compute_eye_position(side, corneal_dist)
        eye.location = target
        centers.append(target)
        print(f"place {side}: 角膜顶点距={corneal_dist*1000:.2f}mm(自动测量) "
              f"开口平面y={rim_y:.4f} 凸出量={EYE_PROTRUSION_MM}mm")
        print(f"  球心={tuple(round(x,4) for x in target)} 角膜顶点y={target[1]-corneal_dist:.4f}")

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print(f"Saved: {OUT_BLEND}")

    # 验证渲染(正面+特写, EEVEE三灯同run_eyeball.py)
    render_verification(centers[0], centers[1])
    print("=== Done ===")

def render_verification(cL, cR):
    from eye_socket_config import SHOT_DIR as _sd
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1000; scene.render.resolution_y = 800
    face_center = Vector(((cL[0]+cR[0])/2, min(cL[1], cR[1]), (cL[2]+cR[2])/2))
    # 灯位置相对face_center(旧版用绝对坐标z=0.5远低于眼睛, 渲染成仰视怪光)
    for name, loc_rel, energy in [("Key", Vector((0.1, -0.6, 0.35)), 40),
                                  ("Fill", Vector((0.5, -0.2, 0.1)), 15),
                                  ("Rim", Vector((0, 0.6, 0.3)), 20)]:
        ld = bpy.data.lights.new(name, type='AREA'); ld.energy = energy; ld.size = 0.6
        lo = bpy.data.objects.new(name, ld); lo.location = face_center + loc_rel
        lo.rotation_euler = (face_center - lo.location).to_track_quat('-Z', 'Y').to_euler()
        scene.collection.objects.link(lo)
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (0.6, 0.6, 0.6, 1.0); bg.inputs['Strength'].default_value = 0.8
    cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    if not cam.users_scene:
        scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 85
    for name, pos in [("front", Vector((face_center.x, face_center.y - 0.30, face_center.z))),
                      ("close", Vector((face_center.x, face_center.y - 0.12, face_center.z)))]:
        cam.location = pos
        cam.rotation_euler = (face_center - pos).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(SHOT_DIR, f"01_2_eye002_{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"shot: {scene.render.filepath}")

if __name__ == "__main__":
    main()
