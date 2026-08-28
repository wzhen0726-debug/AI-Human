"""ARP用户点的Mixamo绑定 (2026-08-27): 100%复用手写版方案A管线, 只换输入.
输入: ARP模板07_arp_markers.blend的用户17点(10主+7镜像)
映射: 01骨盆中心→crotch, 03颈根→neck, 04肩→shoulder_R(+X主), 05肘/06腕,
      08大腿根上段→knee插值基准, 09膝, 10脚踝
输出: ARP版交付/02_ARP绑定.blend + .glb
注意: 用户ARP点位无"头顶"(下巴在头部, 颈根有), Head尾用颈根+0.20m估算;"""
import bpy, os, json
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
SRC = os.path.join(BASE, "_工作区_过程文件", "A_半自动打点", "07_arp_markers.blend")
SPEC = os.path.join(BASE, "_工作区_过程文件", "logs", "mixamo_rest_spec.json")
OUT_BLEND = os.path.join(BASE, "ARP版交付", "02_ARP绑定.blend")
OUT_GLB = os.path.join(BASE, "ARP版交付", "03_Godot输出.glb")
BODY = "tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR"

# ===== 1) 读用户点 =====
bpy.ops.wm.open_mainfile(filepath=SRC)
import re
user, mirror_map = {}, {}
for o in bpy.data.objects:
    m = re.match(r"^(\d+)_(.+?)(_对侧镜像)?$", o.name)
    if not m:
        continue
    idx, mir = int(m.group(1)), bool(m.group(3))
    loc = o.matrix_world.translation.copy()
    if mir:
        mirror_map[idx] = loc
    else:
        user[idx] = loc

def g(i):
    return user.get(i) or mirror_map.get(i)

pt = {}
pt["crotch"]   = g(1)
pt["chin"]     = g(2)
pt["neck"]     = g(3)
pt["shoulder_R"] = g(4)               # +X主=模型左侧=Mixamo Left → 手写管线src='R'
pt["elbow_R"]    = g(5)
pt["wrist_R"]    = g(6)
pt["thigh_top_R"]= g(8)
pt["knee_R"]     = g(9)
pt["ankle_R"]    = g(10)

# 左侧 = 主侧x取反(y/z同), 与镜像球同规则
for k in ("shoulder", "elbow", "wrist", "thigh_top", "knee", "ankle"):
    x, y, z = pt[f"{k}_R"]
    pt[f"{k}_L"] = Vector((-x, y, z))

# 头顶: 用户没打, 用颈根+0.25m(成年头长含头顶余量); 下巴点仅做参考不建骨
pt["headtop"] = pt["neck"] + Vector((0, 0, 0.25))
for k, v in pt.items():
    assert v is not None, f"缺点{k}"
print(f"用户点就绪: crotch={tuple(round(c,3) for c in pt['crotch'])}")

# ===== 2~6) 复用方案A管线核心 =====
with open(SPEC, encoding="utf-8") as f:
    spec = json.load(f)["bones"]

for o in list(bpy.data.objects):
    if o.type == 'ARMATURE':
        for ob in bpy.data.objects:
            for mod in list(ob.modifiers):
                if mod.type == 'ARMATURE' and mod.object == o:
                    ob.modifiers.remove(mod)
        bpy.data.objects.remove(o, do_unlink=True)

# 删标记球和说明牌(cs_*不存在于这文件, 是上一版的垃圾; 这里的标记球是NN_中文名)
keep_body = BODY
del_objs = [o for o in bpy.data.objects if o.type != 'MESH' or (o.name != keep_body and 'Eye' not in o.name and len(o.data.vertices) < 400)]
for o in del_objs:
    bpy.data.objects.remove(o, do_unlink=True)

# 根因修复(2026-08-27): object.add在3D光标处创建 → 用户打点后光标停在别处,
# 整个骨架被平移(Hips差17.5cm). 创建前必须光标归零!
bpy.context.scene.cursor.location = (0, 0, 0)
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

hiptop = pt["crotch"]
neck = pt["neck"]
head_top = pt["headtop"]
shoulder_mid = (pt["shoulder_R"] + pt["shoulder_L"]) / 2

add("Hips", hiptop, hiptop + Vector((0, 0, 0.05)))
s0, s3 = hiptop, shoulder_mid
s1 = s0 + (s3 - s0) * 0.33
s2 = s0 + (s3 - s0) * 0.66
add("Spine", s0, s1, "Hips")
add("Spine1", s1, s2, "Spine")
add("Spine2", s2, s3, "Spine1")
add("Neck", s3, neck, "Spine2")
add("Head", neck, head_top, "Neck")

fwd = Vector((0, -1, 0))
for src in ("R", "L"):
    pre = "Left" if src == "R" else "Right"
    sh, el, wr = pt[f"shoulder_{src}"], pt[f"elbow_{src}"], pt[f"wrist_{src}"]
    sh_head = shoulder_mid + (sh - shoulder_mid) * 0.2
    add(f"{pre}Shoulder", sh_head, sh, "Spine2")
    add(f"{pre}Arm", sh, el, f"{pre}Shoulder")
    add(f"{pre}ForeArm", el, wr, f"{pre}ForeArm" if False else f"{pre}Arm")
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
        # 注意: 左手side_off取反(沿掌宽方向镜像), 否则左右手指交叉错位
        so = side_off if src == "R" else -side_off
        fbase = wr + hand_dir * along + fwd * so
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

# 朝向对齐(方案A核心): Y=Mixamo世界Y轴方向, roll=align到Mixamo世界Z轴
aligned, skipped = 0, []
for b in eb:
    sb = spec.get("mixamorig:" + b.name)
    if not sb:
        skipped.append(b.name)
        continue
    cur_len = max(b.length, 0.005)
    y_dir = Vector(sb["y"]).normalized()
    b.tail = b.head + y_dir * cur_len
    z_dir = Vector(sb["z"])
    if z_dir.length > 0.01:
        b.align_roll(z_dir)
    aligned += 1

bpy.ops.object.mode_set(mode='OBJECT')
print(f"朝向对齐: {aligned}, 跳过{skipped}")

body = bpy.data.objects.get(BODY)
for mod in list(body.modifiers):
    if mod.type == 'ARMATURE':
        body.modifiers.remove(mod)
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type='ARMATURE_AUTO')

# 眼球绑Head骨
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
print("ARP_BIND_DONE")
