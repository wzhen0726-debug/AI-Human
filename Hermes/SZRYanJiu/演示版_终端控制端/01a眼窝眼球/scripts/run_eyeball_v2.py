"""01_2 眼球摆入 v2 — 眼睛模型002 (MetaHuman风格 虹膜+巩膜+阴影)
2026-09-16 流程变更: 本脚本从01a环节挪到【02环节】调用(QR拓扑之后、眼窝碗之前);
  输出 01a眼窝眼球/输出/01_2_eyeball_placed.blend; 2026-09-17 起在【眼窝碗之后】调用,
  并在末尾把眼球并入 02 碗输出(正典 02_qr_150k_socket.blend), 供03 UV/04烘焙/05绑定全程携带。

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

def load_manual_finetune():
    """加载用户GUI手动验收的微调偏移(相对解剖默认位, mm). 文件不存在则返回零偏移.
    面板"保存到管线"写入此文件; 删除文件即回到纯解剖规律默认."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eyeball_finetune_manual.json")
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        print(f"加载手动微调定案: {p}")
        return d.get("dx_mm", 0.0), d.get("dy_mm", 0.0), d.get("dz_mm", 0.0)
    return 0.0, 0.0, 0.0

def compute_eye_position(side, corneal_dist, finetune=(0.0, 0.0, 0.0)):
    """解剖参考点定位(v4):
    x/z = 3DDFA 虹膜中心(iris_3ddfa.json, AI从原始贴图检测, 与手绘打点无关【稳定】, 左右对称化)
    y   = 眼睑开口平面y + 角膜顶点距 - 凸出量   (开口平面仍取用户标记轮廓)
    z  += 高度偏移(规律2: 虹膜底贴下睑 → 002为+1.4mm)
    + 手动微调偏移(GUI验收后由面板保存, 两眼同一偏移→同步)

    v86.4(2026-09-18, 用户实测"眼珠中心跑歪了, 最早是对的"):
      回归本源设计(本文件docstring: "位置基准不变: x/z=3DDFA")。此前 x/z 误用【手描轮廓中心】——
      半自动打点每轮重画 → 轮廓中心横向漂移, 实测眼珠从 09-14 的 ±35.05mm 漂到 ±36.70mm(外移1.65mm/只)。
      三个独立参照(3DDFA虹膜±34.2 / 原始扫描自带眼睛±34.5 / 09-14时期±35.05)一致指向内侧 →
      改回 3DDFA 锚定并对称化(用户要求左右严格对称); 缺文件时回退旧行为并告警。"""
    import json
    with open(EYE_XZ_JSON, encoding="utf-8") as f:
        cont = json.load(f)
    c = cont[side]["center"]
    rim_y = c[1]                                # 眼睑开口平面y(用户标记)
    dx, dy, dz = finetune
    _cx, _cz = None, None
    try:
        _ip = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "3ddfa", "iris_3ddfa.json")
        _ip = os.path.normpath(_ip)
        with open(_ip, encoding="utf-8") as _f:
            _ir = json.load(_f)
        _cl = _ir["L"]["center_3d"]; _cr = _ir["R"]["center_3d"]
        _cx = (abs(float(_cl[0])) + abs(float(_cr[0]))) / 2.0       # 对称化
        _cz = (float(_cl[2]) + float(_cr[2])) / 2.0
        if side == "L":
            _cx = -_cx
    except Exception as _e:
        print(f"  警告: 3DDFA虹膜锚点读取失败({_e}), 回退手描轮廓中心(会随打点漂移)")
    if _cx is None or _cz is None:
        _cx, _cz = c[0], c[2]
    cx = _cx + dx / 1000.0
    cz = _cz + EYE_Z_OFFSET_MM / 1000.0 + dz / 1000.0
    cy = rim_y + corneal_dist - EYE_PROTRUSION_MM / 1000.0 + dy / 1000.0
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

def import_eye_fbx():
    """从用户预制 Eye.fbx 导入单只眼(已合并的单网格, 瞳孔朝-Y, 贴图已接).
    FBX会带入 Camera/Cube/Light 垃圾, 用对象集合差集识别新增的mesh并删非mesh残留.
    返回 [eye_mesh] (单元素列表, 与append_eye_objects接口一致)."""
    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(filepath=EYE002_FBX)
    new_objs = [bpy.data.objects[n] for n in bpy.data.objects.keys() if n not in before]
    # 眼球mesh名字以Eye开头(第二次导入会变 Eye_Iris.001); 垃圾是 Camera/Cube/Light
    eye = next((o for o in new_objs if o.type == 'MESH' and o.name.startswith('Eye')), None)
    assert eye is not None, f"Eye.fbx未找到眼球mesh(以Eye开头的MESH)"
    for o in new_objs:
        if o is not eye:
            bpy.data.objects.remove(o, do_unlink=True)
    print(f"imported FBX eye: {eye.name} 顶点{len(eye.data.vertices)}")
    return [eye]

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
    print("=== 01_2 Eyeball v4 (解剖规律定位+手动微调覆盖, 换模型自动适配) ===")
    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
    finetune = load_manual_finetune()

    centers = []
    for side in ("L", "R"):
        objs = import_eye_fbx()          # 用户预制 Eye.fbx 单只眼(已合并)
        eye = build_single_eye(objs, f"Eye002_{side}")
        unparent_eye(eye)
        apply_eye_color(eye, EYE_COLOR, EYE_BLOODLINE)
        corneal_dist = measure_corneal_dist(eye)
        target, rim_y = compute_eye_position(side, corneal_dist, finetune)
        eye.location = target
        centers.append(target)
        print(f"place {side}: 角膜顶点距={corneal_dist*1000:.2f}mm(自动测量) "
              f"开口平面y={rim_y:.4f} 凸出量={EYE_PROTRUSION_MM}mm")
        print(f"  球心={tuple(round(x,4) for x in target)} 角膜顶点y={target[1]-corneal_dist:.4f}")

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print(f"Saved: {OUT_BLEND}")

    # 验证渲染(正面+特写, EEVEE三灯同run_eyeball.py)
    render_verification(centers[0], centers[1])
    # ---- 2026-09-17 新流程(用户): QR → 碗 → 眼球摆入 — 摆好后并入碗输出(正典), 幂等 ----
    try:
        _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        _sock = os.path.join(_root, "02QR拓扑", "输出", "02_qr_150k_socket.blend")
        if os.path.exists(_sock):
            bpy.ops.wm.open_mainfile(filepath=_sock)
            _has = [o.name for o in bpy.data.objects if o.name.startswith("Eye002")]
            if _has:
                # v86.5(2026-09-18 用户实测): 重摆时必须【替换】旧眼球, 不能跳过——
                #   实测案例: 01_2 已更新到新位置(±34.2), 但碗输出保留旧眼球(±36.70)且守卫跳过并入
                #   → 下游03~06全程带着旧位置, 用户检查到的就是旧的. 现改为先删旧再并入新.
                for _n in _has:
                    _ob = bpy.data.objects.get(_n)
                    if _ob is not None:
                        bpy.data.objects.remove(_ob, do_unlink=True)
                print(f"碗输出旧眼球已移除(替换模式): {_has}")
            with bpy.data.libraries.load(OUT_BLEND) as (_src, _dst):
                _dst.objects = [n for n in _src.objects if n.startswith("Eye002")]
            _eyes = [o for o in _dst.objects if o is not None]
            for _o in _eyes:
                bpy.context.scene.collection.objects.link(_o)
            bpy.ops.wm.save_as_mainfile(filepath=_sock)
            print(f"眼球已并入碗输出: {[o.name for o in _eyes]} → {os.path.basename(_sock)}")
        else:
            print(f"碗输出不存在({os.path.basename(_sock)}), 仅产出 01_2 (独立运行模式)")
    except Exception as _e:
        print(f"眼球并入碗输出失败: {_e}")
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
