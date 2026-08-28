"""ARP绑定 v3 (2026-08-27 根因修复):
用户反馈: ①骨骼多处断开(肩/肘/踝) ②手部脚部骨骼位置对不上.
根因①: 方案A朝向对齐用 spec_y 重写每根骨tail → 覆盖了指向子骨的tail → 链条断裂.
根因②: 手指偏移没有做左右手真镜像(yh坐标系), thumb方向拍脑袋.
修复原则:
  A. 连接优先: 凡有子骨的bone, tail精确=子骨head (链条永不断)
  B. 叶骨(无子骨)tail = head + spec实测y轴 * 长度 (方向照抄Mixamo)
  C. 手指在每只手自己的坐标系(xh=臂向,yh=上×臂向)内展开 → 天然左右镜像正确
     thumb的左右侧符号由spec实测Thumb方向与yh的点积符号决定(数据驱动不猜)
  D. 脚掌/脚趾方向也用spec实测y轴
位置仍全部来自用户点位; 眼球绑Head; 光标归零."""
import bpy, os, json
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
SRC = os.path.join(BASE, "_工作区_过程文件", "A_半自动打点", "07_arp_markers.blend")
SPEC = os.path.join(BASE, "_工作区_过程文件", "logs", "mixamo_rest_spec.json")
PTS_JSON = os.path.join(BASE, "_工作区_过程文件", "logs", "user_pts_actual.json")
OUT_BLEND = os.path.join(BASE, "ARP版交付", "02_ARP绑定.blend")
OUT_GLB = os.path.join(BASE, "ARP版交付", "03_Godot输出.glb")
BODY = "tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR"

# ===== 用户点 =====
bpy.ops.wm.open_mainfile(filepath=SRC)
with open(PTS_JSON, encoding="utf-8") as f:
    UP = {k: Vector(v) for k, v in json.load(f).items()}

pt_sh_R, pt_el_R, pt_wr_R = UP["4肩"], UP["5肘"], UP["6手腕"]
pt_kn_R, pt_an_R = UP["9膝"], UP["10脚踝"]
crotch, neck_pt = UP["1骨盆中心"], UP["3颈根"]
mirror = lambda v: Vector((-v.x, v.y, v.z))
pt_sh_L, pt_el_L, pt_wr_L = mirror(pt_sh_R), mirror(pt_el_R), mirror(pt_wr_R)
pt_kn_L, pt_an_L = mirror(pt_kn_R), mirror(pt_an_R)

# ===== 清场 =====
with open(SPEC, encoding="utf-8") as f:
    spec = json.load(f)["bones"]

for o in list(bpy.data.objects):
    if o.type == 'ARMATURE':
        bpy.data.objects.remove(o, do_unlink=True)
del_objs = [o for o in bpy.data.objects
            if o.type != 'MESH' or (o.name != BODY and 'Eye' not in o.name)]
for o in del_objs:
    bpy.data.objects.remove(o, do_unlink=True)

bpy.context.scene.cursor.location = (0, 0, 0)
bpy.ops.object.add(type='ARMATURE', enter_editmode=True)
arm = bpy.context.object
arm.name = arm.data.name = 'MixamoSkeleton'
eb = arm.data.edit_bones

heads = {}          # name -> Vector 世界坐标
childmap = {}       # name -> [子name]

def bone(name, head, parent=None):
    heads[name] = Vector(head)
    if parent:
        childmap.setdefault(parent, []).append(name)

sh_mid = (pt_sh_R + pt_sh_L) / 2

# ---- 中轴 ----
bone("Hips", crotch)
bone("Spine", crotch, "Hips")
s1 = crotch + (sh_mid - crotch) * 0.33
s2 = crotch + (sh_mid - crotch) * 0.66
bone("Spine1", s1, "Spine")
bone("Spine2", s2, "Spine1")
bone("Neck", sh_mid, "Spine2")
bone("Head", neck_pt, "Neck")

# ---- 四肢 ----
for src, S in (("L", "Left"), ("R", "Right")):
    # 注意: 手写管线已验证映射 src=R(用户右手标,+X)→模型左→Mixamo'Left'
    # 这里反过来命名保持一致: src='L'(=+X主侧)→'Left'
    pre = {"L": "Left", "R": "Right"}[src]
    sh = pt_sh_R if src == "L" else pt_sh_L
    el = pt_el_R if src == "L" else pt_el_L
    wr = pt_wr_R if src == "L" else pt_wr_L
    kn = pt_kn_R if src == "L" else pt_kn_L
    an = pt_an_R if src == "L" else pt_an_L
    sx = 1.0 if src == "L" else -1.0    # 髋偏移方向

    bone(f"{pre}Shoulder", sh_mid + (sh - sh_mid) * 0.2, "Spine2")
    bone(f"{pre}Arm", sh, f"{pre}Shoulder")
    bone(f"{pre}ForeArm", el, f"{pre}Arm")
    bone(f"{pre}Hand", wr, f"{pre}ForeArm")

    # === 手指: 每手自己的坐标系, 展开天然镜像 ===
    xh = (wr - el).normalized()
    zh = Vector((0, 0, 1))
    yh = zh.cross(xh).normalized()      # 左手(+X伸)→+Y(向后), 右手→-Y(向前) 自动镜像
    # thumb侧: 用spec实测Thumb1方向在yh上的投影符号决定 (数据驱动)
    ty = Vector(spec[f"mixamorig:{pre}HandThumb1"]["y"]).normalized()
    tsign = 1.0 if ty.dot(yh) >= 0 else -1.0
    H = f"{pre}Hand"
    spread = {"Index": -0.020, "Middle": 0.0, "Ring": 0.017, "Pinky": 0.032}
    seglens = {
        "Thumb": [0.045, 0.032, 0.028],
        "Index": [0.040, 0.022, 0.020],
        "Middle": [0.045, 0.025, 0.021],
        "Ring": [0.042, 0.022, 0.019],
        "Pinky": [0.035, 0.018, 0.016],
    }
    alongs = {"Thumb": 0.035, "Index": 0.072, "Middle": 0.076, "Ring": 0.072, "Pinky": 0.066}
    # 拇指根
    tb = wr + xh * alongs["Thumb"] + yh * (tsign * 0.024) + zh * 0.004
    bone(f"{pre}HandThumb1", tb, H)
    # 其余四指根
    for fname, off in spread.items():
        fb = wr + xh * alongs[fname] + yh * off
        bone(f"{pre}Hand{fname}1", fb, H)
    # 各指后续节: head=前节head+该节段沿spec方向推进, 连接自动成立
    for fname in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
        y1 = Vector(spec[f"mixamorig:{pre}Hand{fname}1"]["y"]).normalized()
        p = heads[f"{pre}Hand{fname}1"]
        prev_n = f"{pre}Hand{fname}1"
        for i in range(2, 4):
            n = f"{pre}Hand{fname}{i}"
            bone(n, p + y1 * seglens[fname][i-2], prev_n)
            p = heads[n]
            prev_n = n

    # === 腿脚 ===
    bone(f"{pre}UpLeg", crotch + Vector((sx * 0.08, 0, 0)), "Hips")
    bone(f"{pre}Leg", kn, f"{pre}UpLeg")
    bone(f"{pre}Foot", an, f"{pre}Leg")
    fy = Vector(spec[f"mixamorig:{pre}Foot"]["y"]).normalized()
    ball = an + fy * 0.155                       # 脚掌: Mixamo实测方向
    bone(f"{pre}ToeBase", ball, f"{pre}Foot")
    tyb = Vector(spec[f"mixamorig:{pre}ToeBase"]["y"]).normalized()
    _ = tyb  # ToeBase tail叶骨用spec方向, 见下方第二遍

print(f"骨架规划: {len(heads)}骨")

# ===== 第二遍: 建骨. 连接优先原则 =====
def eb_add(name):
    b = eb.new(name)
    b.head = heads[name]
    kids = childmap.get(name)
    if kids:
        b.tail = heads[kids[0]]              # 连接优先: tail=第一个子骨head
        b.use_connect = True                 # 刚性连接, 后续子骨head不会再动
    else:
        sb = spec.get("mixamorig:" + name)
        yd = Vector(sb["y"]).normalized() if sb else Vector((0, 0, 1))
        ln = (sb["length"] / 100.0) if sb else 0.05   # spec是cm
        b.tail = heads[name] + yd * max(ln, 0.01)
        b.use_connect = False
    return b

for name in heads:
    b = eb_add(name)
    par = None
    for pname, kids in childmap.items():
        if name in kids:
            par = pname
            break
    if par and par in eb:
        b.parent = eb[par]

# ===== roll对齐(Mixamo z轴) — align_roll不改head/tail位置 =====
aligned = 0
for b in eb:
    sb = spec.get("mixamorig:" + b.name)
    if sb and Vector(sb["z"]).length > 0.01:
        b.align_roll(Vector(sb["z"]))
        aligned += 1
print(f"roll对齐: {aligned}/{len(eb)}")
bpy.ops.object.mode_set(mode='OBJECT')

# ===== 权重 =====
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
import mathutils
head_b = arm.data.bones.get('Head')
tail_mat = mathutils.Matrix.Translation((0, head_b.length, 0))
parent_mat = arm.matrix_world @ head_b.matrix_local @ tail_mat
for o in bpy.data.objects:
    if o.type == 'MESH' and 'eye' in o.name.lower():
        M = o.matrix_world.copy()
        o.parent = arm
        o.parent_type = 'BONE'
        o.parent_bone = 'Head'
        o.matrix_basis = parent_mat.inverted() @ M

# 姿态清零
for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.rotation_quaternion = (1, 0, 0, 0)
    pb.location = (0, 0, 0)

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"Saved: {OUT_BLEND}")
bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format='GLB',
    export_apply=True, export_texcoords=True, export_normals=True,
    export_materials='EXPORT')
print(f"GLB: {os.path.getsize(OUT_GLB)/(1024*1024):.1f} MB")
zero = sum(1 for v in body.data.vertices if not any(g.weight > 0.001 for g in v.groups))
print(f"权重覆盖: {len(body.data.vertices)-zero}/{len(body.data.vertices)}")
print("ARP_BIND_V3_DONE")
