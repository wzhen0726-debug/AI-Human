"""从标记点blend读取位置 → 生成骨骼+权重 → 导出GLB (参照01a的read_eyelid_markers.py)

用法:
  blender --background --factory-startup --python rig_from_markers.py -- --markers <markers.blend> [--output <out.glb>]
"""
import bpy, os, sys, json, math, mathutils
import numpy as np
from mathutils import Vector

PREFIX = "LM_"
MARKER_IDS = [
    ("HeadTop", "头顶"), ("NeckBase", "颈根"), ("Crotch", "会阴"),
    ("Shoulder_L", "左肩"), ("Elbow_L", "左肘"), ("Wrist_L", "左腕"),
    ("Shoulder_R", "右肩"), ("Elbow_R", "右肘"), ("Wrist_R", "右腕"),
    ("Knee_L", "左膝"), ("Ankle_L", "左踝"),
    ("Knee_R", "右膝"), ("Ankle_R", "右踝"),
]


def find_marker(mid):
    """在场景中找标记点Empty对象(兼容01a中英文命名 LM_01_头顶_headtop 和旧版 LM_HeadTop)"""
    # 方法1: 从LM_Rig/LM_R/LM_L集合
    for cname in ("LM_Rig", "LM_R", "LM_L"):
        coll = bpy.data.collections.get(cname)
        if coll:
            for o in coll.objects:
                if o.name.startswith(f"{PREFIX}{mid}"):
                    return o
    # 方法2: 模糊匹配(中英文命名里含标记ID, 不区分大小写)
    mid_low = mid.lower().replace("_", "")
    for o in bpy.data.objects:
        nm_low = o.name.lower().replace("_", "")
        if nm_low.startswith("lm") and mid_low in nm_low:
            return o
    return None


def find_body():
    best, best_faces = None, 0
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        if 'eye' in o.name.lower():
            continue
        n = len(o.data.polygons)
        if n > best_faces:
            best, best_faces = o, n
    return best


def find_armature():
    for o in bpy.data.objects:
        if o.type == 'ARMATURE':
            return o
    return None


def read_markers():
    """读取所有标记点位置(世界坐标)"""
    pos = {}
    for mid, cname in MARKER_IDS:
        m = find_marker(mid)
        if m is None:
            print(f"WARNING: 找不到标记点 {mid}")
            continue
        pos[mid] = m.location.copy()
        print(f"  {mid}: ({pos[mid].x:.4f}, {pos[mid].y:.4f}, {pos[mid].z:.4f})")
    return pos


def build_skeleton(pos):
    """从标记点位置构建Mixamo标准22骨骼"""
    body = find_body()
    if body is None:
        return "找不到身体网格"

    # 删除旧骨架
    old = find_armature()
    if old:
        for o in bpy.data.objects:
            for mod in list(o.modifiers):
                if mod.type == 'ARMATURE' and mod.object == old:
                    o.modifiers.remove(mod)
        bpy.data.objects.remove(old, do_unlink=True)

    # 创建骨架
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True)
    arm = bpy.context.object
    arm.name = arm.data.name = 'MixamoSkeleton'
    eb = arm.data.edit_bones

    def add(name, head, tail, parent=None):
        b = eb.new(name)
        b.head = head
        b.tail = tail
        if parent and parent in eb:
            b.parent = eb[parent]
            b.use_connect = False
        return b

    hiptop = pos["Crotch"]
    neck = pos["NeckBase"]
    head = pos["HeadTop"]
    shoulder_mid = (pos["Shoulder_L"] + pos["Shoulder_R"]) / 2

    # 躯干链
    add("Hips", hiptop, hiptop + Vector((0, 0, 0.05)))
    s0 = hiptop
    s3 = shoulder_mid
    s1 = s0 + (s3 - s0) * 0.33
    s2 = s0 + (s3 - s0) * 0.66
    add("Spine", s0, s1, parent="Hips")
    add("Spine1", s1, s2, parent="Spine")
    add("Spine2", s2, s3, parent="Spine1")
    add("Neck", s3, neck, parent="Spine2")
    add("Head", neck, head, parent="Neck")

    # 手臂 (含手骨: 掌骨+5指各3节, 朝向沿手臂方向延伸)
    for side, pre in [("L", "Left"), ("R", "Right")]:
        sh = pos[f"Shoulder_{side}"]
        el = pos[f"Elbow_{side}"]
        wr = pos[f"Wrist_{side}"]

        # Mixamo规范: Shoulder从脊柱旁画到肩关节
        sh_head = shoulder_mid + (sh - shoulder_mid) * 0.2
        add(f"{pre}Shoulder", sh_head, sh, parent="Spine2")
        add(f"{pre}Arm", sh, el, parent=f"{pre}Shoulder")
        add(f"{pre}ForeArm", el, wr, parent=f"{pre}Arm")
        # 手掌: 沿前臂方向延伸, 长度约9cm(成人手掌)
        hand_dir = (wr - el).normalized() if (wr - el).length > 0.001 else Vector((0.1 if side == 'L' else -0.1, 0, 0))
        palm_end = wr + hand_dir * 0.09
        add(f"{pre}Hand", wr, palm_end, parent=f"{pre}ForeArm")
        # 手指: 5指, 每指3节, 沿手臂方向延伸, 绕z轴扇形展开(掌心朝下-z, 拇指朝前)
        import math
        # 展开角(度, 正=朝模型前方): 拇指最大, 小指偏后
        finger_spread = {"Thumb": 25, "Index": 10, "Middle": 3, "Ring": -3, "Pinky": -10}
        finger_lens = {"Thumb": [0.045, 0.032, 0.028], "Index": [0.040, 0.022, 0.020],
                       "Middle": [0.045, 0.025, 0.021], "Ring": [0.042, 0.022, 0.019],
                       "Pinky": [0.035, 0.018, 0.016]}
        rot_sign = 1.0 if side == 'L' else -1.0   # L臂朝-x, 正旋转朝前; R臂朝+x, 需反向
        for fname, spread_deg in finger_spread.items():
            ang = math.radians(spread_deg * rot_sign)
            fdir = hand_dir.copy()
            fdir.rotate(mathutils.Euler((0, 0, ang)))
            if fname == "Thumb":
                # 拇指额外上翘(掌心朝下, 拇指略向上)
                fdir.rotate(mathutils.Euler((0, -0.35 * rot_sign, 0)))
            fdir.normalize()
            fbase = wr + hand_dir * 0.075 + fdir * 0.015   # 掌骨末端
            prev = fbase
            for seg_i, seg_len in enumerate(finger_lens[fname], 1):
                fseg_end = prev + fdir * seg_len
                seg_name = f"{pre}Hand{fname}{seg_i}"
                add(seg_name, prev, fseg_end, parent=f"{pre}Hand" if seg_i == 1 else f"{pre}Hand{fname}{seg_i-1}")
                prev = fseg_end

    # 腿 (含脚骨: 脚跟→脚掌→脚趾, 脚尖朝前)
    for side, pre in [("L", "Left"), ("R", "Right")]:
        hip_s = hiptop + Vector((-0.08 if side == 'L' else 0.08, 0, 0))
        kn = pos[f"Knee_{side}"]
        an = pos[f"Ankle_{side}"]

        add(f"{pre}UpLeg", hip_s, kn, parent="Hips")
        add(f"{pre}Leg", kn, an, parent=f"{pre}UpLeg")
        # 脚: 踝→脚跟(后下方)→脚掌(前)→脚趾(前)
        # 脚跟: 踝后方下方
        heel = an + Vector((0, 0.04, -0.04))
        # 脚掌: 踝前方(脚长~25cm, 踝到趾根~18cm)
        ball = an + Vector((0, -0.16, -0.06))
        # 脚趾: 脚掌前方(~7cm)
        toe_tip = an + Vector((0, -0.23, -0.07))
        add(f"{pre}Foot", an, heel, parent=f"{pre}Leg")
        add(f"{pre}ToeBase", heel, ball, parent=f"{pre}Foot")
        add(f"{pre}Toe", ball, toe_tip, parent=f"{pre}ToeBase")

    bpy.ops.object.mode_set(mode='OBJECT')
    return None


def bind_weights():
    body = find_body()
    arm = find_armature()
    if body is None or arm is None:
        return "找不到body/arm"

    for mod in list(body.modifiers):
        if mod.type == 'ARMATURE':
            body.modifiers.remove(mod)

    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')

    # 眼球parent到Head
    # 关键: parent_type=BONE时, Blender的父矩阵 = 骨骼rest矩阵的tail端
    # (head沿骨骼Y轴到尾端, 与骨骼同朝向), 必须按此换算, 否则眼球飞走
    head_b = arm.data.bones.get('Head')
    if head_b:
        # 复现Blender的BONE父级矩阵: 原点在tail(骨骼局部Y轴末端), 轴向=骨骼rest轴向
        import mathutils
        tail_mat = mathutils.Matrix.Translation((0, head_b.length, 0))
        parent_mat = arm.matrix_world @ head_b.matrix_local @ tail_mat
        for o in bpy.data.objects:
            if o.type == 'MESH' and 'eye' in o.name.lower():
                world_pos = o.matrix_world.translation.copy()
                o.parent = arm
                o.parent_type = 'BONE'
                o.parent_bone = 'Head'
                o.location = parent_mat.inverted() @ world_pos
                print(f"眼球 {o.name}: 世界({world_pos.x:.3f},{world_pos.y:.3f},{world_pos.z:.3f}) → Head局部({o.location.x:.3f},{o.location.y:.3f},{o.location.z:.3f})")
    return None


def verify():
    arm = find_armature()
    body = find_body()
    if arm is None:
        return
    print(f"\n=== 骨骼 ({len(arm.data.bones)}根) ===")
    for b in arm.data.bones:
        print(f"  {b.name:14s} head=({b.head_local.x:7.3f},{b.head_local.y:7.3f},{b.head_local.z:7.3f})")

    zero = 0
    total = len(body.data.vertices)
    for v in body.data.vertices:
        if not any(g.weight > 0.001 for g in v.groups):
            zero += 1
    print(f"权重覆盖: {total - zero}/{total} ({100 * (total - zero) / total:.1f}%)")


def main():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    markers_path = None
    output_path = None
    for i, arg in enumerate(argv):
        if arg == "--markers" and i + 1 < len(argv):
            markers_path = argv[i + 1]
        if arg == "--output" and i + 1 < len(argv):
            output_path = argv[i + 1]

    # 默认路径(2026-08-25整理后目录结构)
    base_05 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not markers_path:
        markers_path = os.path.join(base_05, "A_半自动打点", "06_rig_markers.blend")
    if not output_path:
        output_path = os.path.join(base_05, "B_骨骼绑定", "06_rig_final.glb")

    if markers_path:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.wm.open_mainfile(filepath=markers_path)

    # 读取标记点
    print("=== 读取标记点 ===")
    pos = read_markers()
    if len(pos) < 10:
        print(f"ERROR: 标记点不足 ({len(pos)}/13)")
        return

    # 构建骨骼
    print("\n=== 构建骨骼 ===")
    err = build_skeleton(pos)
    if err:
        print(f"ERROR: {err}")
        return

    # 绑定权重
    print("\n=== 绑定权重 ===")
    err = bind_weights()
    if err:
        print(f"ERROR: {err}")
        return

    # 验证
    verify()

    # 保存前: 姿态纯净检查+自动清零(根因修复2026-08-25)
    # 教训: 验证测试的pose残留被保存进交付文件 → 头骨28.6°前倾导致眼珠虹膜朝下
    # 规则: 交付文件永远保持rest pose, 检测到的姿态一律清零
    arm = find_armature()
    print("\n=== 姿态纯净检查 ===")
    dirty = []
    if arm:
        for pb in arm.pose.bones:
            r = np.array(pb.rotation_euler)
            q = np.array(pb.rotation_quaternion)
            l = np.array(pb.location)
            rot_bad = (abs(r).max() > 1e-4) or (abs(q - np.array([1.0, 0, 0, 0])).max() > 1e-4)
            if rot_bad or abs(l).max() > 1e-4:
                dirty.append(pb.name)
                # 清零该骨骼的pose变换(恢复rest)
                pb.rotation_euler = (0, 0, 0)
                pb.rotation_quaternion = (1, 0, 0, 0)
                pb.location = (0, 0, 0)
        if dirty:
            print(f"警告: 检测到并清零残留姿态: {dirty}")
            print("(交付文件必须保持rest pose; 验证测试请在临时副本上做)")
        else:
            print("姿态纯净 ✓ (所有pose bone为单位变换)")

    # 保存
    blend_out = output_path.replace('.glb', '.blend') if output_path else "06_rig_final.blend"
    bpy.ops.wm.save_as_mainfile(filepath=blend_out)
    print(f"\nSaved: {blend_out}")

    if output_path:
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            export_format='GLB',
            export_apply=True,
            export_texcoords=True,
            export_normals=True,
            export_materials='EXPORT',
        )
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"GLB: {output_path} ({size_mb:.1f} MB)")

    print("Done.")


if __name__ == "__main__":
    main()