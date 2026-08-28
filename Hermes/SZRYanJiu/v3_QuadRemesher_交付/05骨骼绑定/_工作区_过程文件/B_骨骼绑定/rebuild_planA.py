"""方案A重建手写版骨架 (2026-08-27, 用户选定).
原理: 骨骼朝向/roll完全照抄Mixamo参考骨架(实测世界轴), 位置用用户打的标记点.
关键: Mixamo FBX导入后世界轴已与我们模型同朝向(都面朝-Y, Z-up), 无需坐标映射.
      (证据: spec中Hips y=[0,0,1]朝上, LeftArm y=+X=模型左侧, 与我们一致)
实现: 每骨 head=标记点位置, 方向=Mixamo世界Y轴, 长度=标记点间距,
      roll=align_roll(Mixamo世界Z轴)."""
import bpy, os, json
from mathutils import Vector

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(BASE, "logs", "mixamo_rest_spec.json")
MARKERS = os.path.join(BASE, "A_半自动打点", "06_rig_markers.blend")
OUT_BLEND = os.path.join(BASE, "B_骨骼绑定", "06_rig_final.blend")
OUT_GLB = os.path.join(BASE, "B_骨骼绑定", "06_rig_final.glb")
BODY = "tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR"

with open(SPEC, encoding="utf-8") as f:
    spec = json.load(f)["bones"]

# ===== 1) 读用户标记点 =====
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=MARKERS)

def get_lm(name_part):
    for o in bpy.data.objects:
        if o.name.startswith("LM_") and name_part in o.name:
            return o.matrix_world.translation.copy()
    return None

pt = {}
pt["headtop"] = get_lm("头顶")
pt["neck"]    = get_lm("颈根")
pt["crotch"]  = get_lm("会阴")
for s in ("R", "L"):
    cn = "右" if s == "R" else "左"
    pt[f"shoulder_{s}"] = get_lm(f"{cn}肩")
    pt[f"elbow_{s}"]    = get_lm(f"{cn}肘")
    pt[f"wrist_{s}"]    = get_lm(f"{cn}腕")
    pt[f"knee_{s}"]     = get_lm(f"{cn}膝")
    pt[f"ankle_{s}"]    = get_lm(f"{cn}踝")
for k, v in pt.items():
    assert v, f"缺标记: {k}"
print("用户标记点读取OK")

# ===== 2) 删除旧骨架 =====
for o in list(bpy.data.objects):
    if o.type == 'ARMATURE':
        for ob in bpy.data.objects:
            for mod in list(ob.modifiers):
                if mod.type == 'ARMATURE' and mod.object == o:
                    ob.modifiers.remove(mod)
        bpy.data.objects.remove(o, do_unlink=True)

bpy.ops.object.add(type='ARMATURE', enter_editmode=True)
arm = bpy.context.object
arm.name = arm.data.name = 'MixamoSkeleton'
eb = arm.data.edit_bones

def add(name, head, tail, parent=None):
    b = eb.new(name)
    b.head = head
    b.tail = tail
    if b.length < 0.001:
        b.tail = head + Vector((0, 0, 0.02))
    if parent and parent in eb:
        b.parent = eb[parent]
        b.use_connect = False
    return b

# ===== 3) 从标记点建骨(位置), 朝向稍后统一对齐Mixamo =====
hiptop = pt["crotch"]
neck = pt["neck"]
head = pt["headtop"]
shoulder_mid = (pt["shoulder_R"] + pt["shoulder_L"]) / 2

add("Hips", hiptop, hiptop + Vector((0, 0, 0.05)))
s0, s3 = hiptop, shoulder_mid
s1 = s0 + (s3 - s0) * 0.33
s2 = s0 + (s3 - s0) * 0.66
add("Spine", s0, s1, "Hips")
add("Spine1", s1, s2, "Spine")
add("Spine2", s2, s3, "Spine1")
add("Neck", s3, neck, "Spine2")
add("Head", neck, head, "Neck")

fwd = Vector((0, -1, 0))
for src in ("R", "L"):
    pre = "Left" if src == "R" else "Right"   # +X(用户右肩)=模型左侧=Mixamo Left
    sh, el, wr = pt[f"shoulder_{src}"], pt[f"elbow_{src}"], pt[f"wrist_{src}"]
    sh_head = shoulder_mid + (sh - shoulder_mid) * 0.2
    add(f"{pre}Shoulder", sh_head, sh, "Spine2")
    add(f"{pre}Arm", sh, el, f"{pre}Shoulder")
    add(f"{pre}ForeArm", el, wr, f"{pre}Arm")
    hand_dir = (wr - el).normalized()
    add(f"{pre}Hand", wr, wr + hand_dir * 0.09, f"{pre}ForeArm")
    fingers = [
        ("Thumb",  0.040, -0.048, [0.045, 0.032, 0.028]),
        ("Index",  0.075, -0.022, [0.040, 0.022, 0.020]),
        ("Middle", 0.078,  0.000, [0.045, 0.025, 0.021]),
        ("Ring",   0.075,  0.020, [0.042, 0.022, 0.019]),
        ("Pinky",  0.070,  0.038, [0.035, 0.018, 0.016]),
    ]
    for fname, along, side_off, lens in fingers:
        fbase = wr + hand_dir * along + fwd * side_off
        if fname == "Thumb":
            fdir = (hand_dir + fwd * 0.50 + Vector((0, 0, -0.45))).normalized()
        else:
            fdir = hand_dir.copy()
        prev = fbase
        for i, seg_len in enumerate(lens, 1):
            add(f"{pre}Hand{fname}{i}", prev, prev + fdir * seg_len,
                f"{pre}Hand" if i == 1 else f"{pre}Hand{fname}{i-1}")
            prev = prev + fdir * seg_len

    hip_s = hiptop + Vector((0.08 if src == "L" else -0.08, 0, 0))
    kn, an = pt[f"knee_{src}"], pt[f"ankle_{src}"]
    add(f"{pre}UpLeg", hip_s, kn, "Hips")
    add(f"{pre}Leg", kn, an, f"{pre}UpLeg")
    ball = an + fwd * 0.16 + Vector((0, 0, -0.06))
    toe_tip = an + fwd * 0.23 + Vector((0, 0, -0.07))
    add(f"{pre}Foot", an, ball, f"{pre}Leg")
    add(f"{pre}ToeBase", ball, toe_tip, f"{pre}Foot")

# ===== 4) 朝向对齐: 方向=Mixamo世界Y轴, roll=Mixamo世界Z轴 =====
aligned, skipped = 0, []
for b in eb:
    sb = spec.get("mixamorig:" + b.name)
    if not sb:
        skipped.append(b.name)
        continue
    cur_len = b.length
    if cur_len < 0.005:
        cur_len = sb["length"] * 0.01
    y_dir = Vector(sb["y"]).normalized()
    b.tail = b.head + y_dir * cur_len
    z_dir = Vector(sb["z"])
    if z_dir.length > 0.01:
        b.align_roll(z_dir)
    aligned += 1

bpy.ops.object.mode_set(mode='OBJECT')
print(f"朝向对齐: {aligned}骨, 跳过: {skipped}")

# ===== 5) 绑定权重 =====
body = bpy.data.objects.get(BODY)
if body:
    for mod in list(body.modifiers):
        if mod.type == 'ARMATURE':
            body.modifiers.remove(mod)
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')

head_b = arm.data.bones.get('Head')
if head_b:
    import mathutils
    tail_mat = mathutils.Matrix.Translation((0, head_b.length, 0))
    parent_mat = arm.matrix_world @ head_b.matrix_local @ tail_mat
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'eye' in o.name.lower():
            M = o.matrix_world.copy()
            o.parent = arm
            o.parent_type = 'BONE'
            o.parent_bone = 'Head'
            o.matrix_basis = parent_mat.inverted() @ M

# ===== 6) 姿态清零+保存 =====
for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.rotation_quaternion = (1, 0, 0, 0)
    pb.location = (0, 0, 0)

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"Saved: {OUT_BLEND}")

bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format='GLB',
    export_apply=True, export_texcoords=True, export_normals=True,
    export_materials='EXPORT')
print(f"GLB: {OUT_GLB} ({os.path.getsize(OUT_GLB)/(1024*1024):.1f} MB)")

zero = sum(1 for v in body.data.vertices if not any(g.weight > 0.001 for g in v.groups))
total = len(body.data.vertices)
print(f"权重覆盖: {total-zero}/{total} ({100*(total-zero)/total:.1f}%)")
print("REBUILD_A_DONE")
