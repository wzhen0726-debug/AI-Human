"""ARP全新测试 — 步骤3+4+5+6+7: 提取55骨→align_roll→use_connect→权重→行走验证
输入: 02_go_detect骨架.blend
输出: 03_骨骼绑定.blend, 04_行走测试.blend"""
import bpy, sys, os, json
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
OUT = os.path.join(BASE, "ARP新版测试_20260831")
IN = os.path.join(OUT, "02_go_detect骨架.blend")
WALK_FBX = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx"
SPEC = os.path.join(BASE, "_工作区_过程文件", "logs", "mixamo_rest_spec.json")

bpy.ops.wm.open_mainfile(filepath=IN)
rig = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
body = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices))
print(f"rig={rig.name}({len(rig.data.bones)}骨), body={body.name}({len(body.data.vertices)}顶点)")

# ============ 步骤3: 参考骨提取55骨 (ARP参考骨位置 + Mixamo roll对齐) ============
# 路线定案(2026-09-01): 位置=ARP参考骨(T-pose贴合模型), 朝向=align_roll对齐Mixamo spec的z轴
# 用户标记点仅作校验报告, 不覆盖骨骼位置(覆盖会导致姿态与Mixamo动画不匹配)
print("\n########## 步骤3: 参考骨提取(55骨Mixamo命名) ##########")
mw = rig.matrix_world
def whead(name): return mw @ rig.data.bones[name].head_local
def wtail(name): return mw @ rig.data.bones[name].tail_local

# 读用户标记点: 必须用 matrix_world.translation(含镜像约束求值结果)!
# _sym点靠COPY_LOCATION约束镜像跟随主点, o.location只读约束前局部值(错的/不对称),
# matrix_world.translation才是约束后的真实镜像位置(严格对称)。
MK = {}
with bpy.data.libraries.load(os.path.join(OUT, "01_AI打点.blend")) as (src, dst):
    dst.objects = [n for n in src.objects if n.endswith('_loc') or n.endswith('_loc_sym')]
# library加载后需link到场景才能求值约束
_linked = []
for o in dst.objects:
    bpy.context.scene.collection.objects.link(o)
    _linked.append(o)
bpy.context.view_layer.update()  # 触发约束求值
dg = bpy.context.evaluated_depsgraph_get()
for o in _linked:
    MK[o.name] = o.evaluated_get(dg).matrix_world.translation.copy()
for o in _linked:
    bpy.data.objects.remove(o, do_unlink=True)
assert len(MK) > 0 and any(v.length > 0.1 for v in MK.values()), f"标记点读取失败: {MK}"
# 对称自检
_sym_err = []
for base in ['shoulder','elbow','hand','thigh','knee','foot']:
    a, b = MK.get(base+'_loc'), MK.get(base+'_loc_sym')
    if a is not None and b is not None:
        if abs(a.x+b.x) > 0.002 or abs(a.y-b.y) > 0.002 or abs(a.z-b.z) > 0.002:
            _sym_err.append(base)
print(f"标记点 {len(MK)}个, 对称自检: {'全部严格对称' if not _sym_err else '不对称:'+str(_sym_err)}")
assert not _sym_err, f"标记点不对称: {_sym_err} — 读取方法错了(应含约束)"

MAP = [("Hips", None, "root_ref.x", "root_ref.x"),
       ("Spine", "Hips", "spine_01_ref.x", "spine_01_ref.x"),
       ("Spine1", "Spine", "spine_02_ref.x", "spine_02_ref.x"),
       ("Spine2", "Spine1", "spine_03_ref.x", "spine_03_ref.x"),
       ("Neck", "Spine2", "neck_ref.x", "neck_ref.x"),
       ("Head", "Neck", "head_ref.x", "head_ref.x"),
       ("HeadTop_End", "Head", "SPECIAL_HEADTOP", None)]
for side, pre in [("l", "Left"), ("r", "Right")]:
    s = "." + side
    MAP += [
        (f"{pre}Shoulder", "Spine2", f"shoulder_ref{s}", f"shoulder_ref{s}"),
        (f"{pre}Arm", f"{pre}Shoulder", f"arm_ref{s}", f"arm_ref{s}"),
        (f"{pre}ForeArm", f"{pre}Arm", f"forearm_ref{s}", f"forearm_ref{s}"),
        (f"{pre}Hand", f"{pre}ForeArm", f"hand_ref{s}", f"HEAD_middle1_ref{s}"),
        (f"{pre}HandThumb1", f"{pre}Hand", f"thumb1_ref{s}", f"thumb1_ref{s}"),
        (f"{pre}HandThumb2", f"{pre}HandThumb1", f"thumb2_ref{s}", f"thumb2_ref{s}"),
        (f"{pre}HandThumb3", f"{pre}HandThumb2", f"thumb3_ref{s}", f"thumb3_ref{s}"),
    ]
    for f in ["index", "middle", "ring", "pinky"]:
        F = f.capitalize()
        MAP += [
            (f"{pre}Hand{F}1", f"{pre}Hand", f"{f}1_ref{s}", f"{f}1_ref{s}"),
            (f"{pre}Hand{F}2", f"{pre}Hand{F}1", f"{f}2_ref{s}", f"{f}2_ref{s}"),
            (f"{pre}Hand{F}3", f"{pre}Hand{F}2", f"{f}3_ref{s}", f"{f}3_ref{s}"),
        ]
    MAP += [
        (f"{pre}UpLeg", "Hips", f"thigh_ref{s}", f"thigh_ref{s}"),
        (f"{pre}Leg", f"{pre}UpLeg", f"leg_ref{s}", f"leg_ref{s}"),
        (f"{pre}Foot", f"{pre}Leg", f"foot_ref{s}", f"foot_ref{s}"),
        (f"{pre}ToeBase", f"{pre}Foot", f"toes_ref{s}", f"toes_ref{s}"),
        (f"{pre}Toe_End", f"{pre}ToeBase", "SPECIAL_TOE", s),
    ]

body.modifiers.clear()
body.vertex_groups.clear()

arm_data = bpy.data.armatures.new("MixamoSkeleton")
arm = bpy.data.objects.new("MixamoSkeleton", arm_data)
bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm_data.edit_bones

created = {}
# 头顶/脚趾/零长度保护: 用骨骼自身长度比例, 不写死绝对值(适配任意身高)
for name, parent, hsrc, tsrc in MAP:
    b = eb.new(name)
    if tsrc and tsrc.startswith("HEAD_"):
        b.head = whead(hsrc); b.tail = whead(tsrc[5:])
    elif hsrc == "SPECIAL_HEADTOP":
        # 头顶: 沿Head骨方向延伸 Head骨长度的0.6倍(经验比例, 相对值)
        h = wtail("head_ref.x")
        hd = wtail("head_ref.x") - whead("head_ref.x")
        ext = max(hd.length * 0.6, 0.02)  # 保底2cm
        b.head = h; b.tail = h + hd.normalized() * ext
    elif hsrc == "SPECIAL_TOE":
        # 脚趾末端: 沿脚趾方向延伸 脚骨(Foot)长度的0.3倍(相对值)
        h = wtail(f"toes_ref{tsrc}")
        d = (wtail(f"toes_ref{tsrc}") - whead(f"toes_ref{tsrc}")).normalized()
        foot_len = (wtail(f"foot_ref{tsrc}") - whead(f"foot_ref{tsrc}")).length
        ext = max(foot_len * 0.3, 0.01)  # 保底1cm
        b.head = h; b.tail = h + d * ext
    else:
        b.head = whead(hsrc); b.tail = wtail(tsrc if tsrc else hsrc)
    # 零长度保护: 阈值=模型身高的0.3%(约5mm@1.7m), 延伸量=阈值
    min_len = max((wtail("head_ref.x").z - whead("foot_ref.l").z) * 0.003, 0.002)
    if (b.tail - b.head).length < min_len:
        b.tail = b.head + Vector((0, 0, min_len))
    created[name] = b

# ---- 关节对齐: 所有关节严格按用户标记点(用户打哪骨骼就在哪) ----
# 用户原则是权威: 点打在哪, 骨骼就在哪。不做任何中心化/解剖修正——用户可调点来改变骨骼。
# 标记点已严格对称(matrix_world含镜像约束)。只覆盖用户打过点的关节, 未打点的(脊柱/手指等)用ARP参考骨。
def mp(base):
    """读 base_loc / base_loc_sym 返回 (左,右) 世界坐标"""
    return MK.get(base + '_loc'), MK.get(base + '_loc_sym')

# 手臂: 肩/肘/腕
sho = mp('shoulder'); elb = mp('elbow'); wst = mp('hand')
# 腿: 胯/膝/踝
thi = mp('thigh'); kne = mp('knee'); ank = mp('foot')

for pre, i in [("Left", 0), ("Right", 1)]:  # i=0主点(+x左), i=1镜像(-x右)
    # 手臂
    if sho[0] is not None:
        created[f"{pre}Arm"].head = sho[i].copy()
        created[f"{pre}Shoulder"].tail = sho[i].copy()
    if elb[0] is not None:
        created[f"{pre}Arm"].tail = elb[i].copy()
        created[f"{pre}ForeArm"].head = elb[i].copy()
    if wst[0] is not None:
        created[f"{pre}ForeArm"].tail = wst[i].copy()
        created[f"{pre}Hand"].head = wst[i].copy()
    # 腿: 胯=thigh, 膝=knee, 踝=foot (UpLeg.tail=Leg.head=膝点 保持连贯)
    if thi[0] is not None:
        created[f"{pre}UpLeg"].head = thi[i].copy()
    if kne[0] is not None:
        created[f"{pre}UpLeg"].tail = kne[i].copy()
        created[f"{pre}Leg"].head = kne[i].copy()
    if ank[0] is not None:
        created[f"{pre}Leg"].tail = ank[i].copy()
        created[f"{pre}Foot"].head = ank[i].copy()

print("关节对齐用户标记点:")
for n in ["LeftUpLeg","LeftLeg","LeftFoot","LeftArm","LeftForeArm","LeftHand"]:
    b = created[n]
    print(f"  {n}: head=({b.head.x:.3f},{b.head.y:.3f},{b.head.z:.3f}) tail=({b.tail.x:.3f},{b.tail.y:.3f},{b.tail.z:.3f})")

for name, parent, _, _ in MAP:
    if parent: created[name].parent = created[parent]
print(f"新骨架: {len(created)}骨 (全部关节按用户标记点)")

# 标记点校验报告: 关键关节 骨位置 vs 用户标记点 距离
print("\n标记点校验(骨head vs 用户标记点, cm):")
CHK = [('LeftArm','shoulder_loc'), ('LeftForeArm','elbow_loc'), ('LeftHand','hand_loc'),
       ('LeftUpLeg','thigh_loc'), ('LeftLeg','knee_loc'), ('LeftFoot','foot_loc'),
       ('Hips','root_loc'), ('Neck','neck_loc')]
for bone, mkn in CHK:
    b = created[bone]; mp = MK.get(mkn)
    if mp:
        d = (b.head - mp).length * 100
        print(f"  {bone}: 骨=({b.head.x:.3f},{b.head.y:.3f},{b.head.z:.3f}) vs 标记=({mp.x:.3f},{mp.y:.3f},{mp.z:.3f}) 差{d:.1f}cm")

# ============ 步骤4: align_roll ============
print("\n########## 步骤4: align_roll对齐Mixamo ##########")
spec = json.load(open(SPEC, encoding="utf-8"))["bones"]
aligned, skipped = 0, []
for b in eb:
    sb = spec.get("mixamorig:" + b.name)
    if not sb:
        skipped.append(b.name); continue
    z = Vector(sb["z"])
    if z.length > 0.01:
        b.align_roll(z)
    aligned += 1
print(f"roll对齐: {aligned}骨, 跳过: {skipped}")

# ============ 步骤5: use_connect ============
n_conn = 0
for b in eb:
    if b.parent and (b.head - b.parent.tail).length < 0.002:
        b.use_connect = True; n_conn += 1
print(f"use_connect: {n_conn}根")
bpy.ops.object.mode_set(mode='OBJECT')

bpy.data.objects.remove(rig, do_unlink=True)

# ============ 步骤6: 自动权重 ============
print("\n########## 步骤6: 自动权重 ##########")
for o in bpy.data.objects: o.select_set(False)
body.select_set(True); arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
print(f"权重顶点组: {len(body.vertex_groups)}")

step06 = os.path.join(OUT, "03_骨骼绑定.blend")
bpy.ops.wm.save_mainfile(filepath=step06)
print(f"保存: {step06}")

# ============ 步骤7: 行走动画验证 ============
print("\n########## 步骤7: 行走动画验证 ##########")
for b in arm.data.bones:
    if not b.name.startswith("mixamorig:"):
        b.name = "mixamorig:" + b.name
for vg in body.vertex_groups:
    if not vg.name.startswith("mixamorig:"):
        vg.name = "mixamorig:" + vg.name

bpy.ops.import_scene.fbx(filepath=WALK_FBX)
walk_arm = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE' and o.name != 'MixamoSkeleton' and o.animation_data and o.animation_data.action:
        walk_arm = o
assert walk_arm, "行走FBX导入失败"
action = walk_arm.animation_data.action
rig_action = action.copy()
rig_action.name = "Walk_noroot"

data_slot = None
removed = 0
remapped = 0
# Hips垂直起伏恢复: 从参考骨架逐帧实测, 不写死任何绝对值。
# 参考骨架与我们的局部轴向不同(实测: 参考Hips局部y=世界垂直, 我们Hips局部y=世界垂直, 已验证),
# 但单位不同(参考cm scale0.01, 我们m scale1)。所以读参考的"世界z起伏"(已含单位换算), 按腿长比缩放。
# 腿长比 leg_ratio 由两边实测腿长得出, 不写死。
wm_ref = walk_arm.matrix_world
ref_hips_z = (wm_ref @ walk_arm.data.bones['mixamorig:Hips'].head_local).z
ref_foot_z = (wm_ref @ walk_arm.data.bones['mixamorig:LeftFoot'].head_local).z
our_hips_z = (arm.matrix_world @ arm.data.bones['mixamorig:Hips'].head_local).z
our_foot_z = (arm.matrix_world @ arm.data.bones['mixamorig:LeftFoot'].head_local).z
leg_ratio = (our_hips_z - our_foot_z) / (ref_hips_z - ref_foot_z)
print(f"腿长比: 我们{our_hips_z-our_foot_z:.3f}/参考{ref_hips_z-ref_foot_z:.3f} = {leg_ratio:.4f}")

for layer in rig_action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            if len(bag.fcurves) > 0:
                data_slot = next((s for s in rig_action.slots if s.handle == bag.slot_handle), None)
                for fc in list(bag.fcurves):
                    if 'mixamorig:Hips' in fc.data_path and 'location' in fc.data_path:
                        if fc.array_index == 2:  # 我们局部z=垂直 → 用参考局部y换算
                            for kp in fc.keyframe_points:
                                pass  # 这条曲线值是参考z(前后),无垂直意义,下面统一重建
                        bag.fcurves.remove(fc); removed += 1
                break
assert data_slot
print(f"删Hips原location {removed}条")

# Hips的location三轴从参考动画删除(参考骨架局部轴和我们不同, 直接搬会错)。
# 但Hips垂直起伏(正常行走重心上下2-5cm)必须恢复, 否则滑步僵硬。
# 方法: 逐帧读参考骨架Hips世界z, 按腿长比缩放到我们身高, 写入我们Hips局部y(=世界垂直,已实测)。
# 水平(前进/左右)删除=原地走(walk in place)。
if arm.animation_data is None:
    arm.animation_data_create()
arm.animation_data.action = rig_action
arm.animation_data.action_slot = data_slot

# 逐帧读参考Hips世界z → 我们Hips局部y补偿
# 参考静止世界z=ref_hips_z, 我们静止our_hips_z。每帧: 参考起伏=ref_z-ref_hips_z, 按腿长比缩, 加到我们的基准。
# 我们Hips局部y=世界z偏移(局部y+0.1→世界z+0.1已实测), 所以 location.y = (目标世界z - 静止世界z)
print("恢复Hips垂直起伏:")
dg_tmp = bpy.context.evaluated_depsgraph_get()
hips_pb = arm.pose.bones['mixamorig:Hips']
n_kp = 0
fstart = int(action.frame_range[0]); fend = int(action.frame_range[1])
for f in range(fstart, fend + 1):
    bpy.context.scene.frame_set(f)
    bpy.context.view_layer.update()
    wa_ev = walk_arm.evaluated_get(dg_tmp)
    ref_z = (wm_ref @ wa_ev.pose.bones['mixamorig:Hips'].head).z
    # 参考起伏(世界,米) → 按腿长比缩 → 我们的目标世界z → 局部y偏移
    ref_delta = (ref_z - ref_hips_z) * leg_ratio
    hips_pb.location.y = ref_delta  # 局部y即世界z偏移
    hips_pb.keyframe_insert('location', index=1, frame=f)
    n_kp += 1
print(f"  写入{n_kp}帧, 起伏范围参考实测")

del_names = [o.name for o in bpy.data.objects if o.name != 'MixamoSkeleton' and o.name != body.name and 'Eye' not in o.name]
for nm in del_names:
    o = bpy.data.objects.get(nm)
    if o and o.type in ('ARMATURE', 'MESH'):
        bpy.data.objects.remove(o, do_unlink=True)

scn = bpy.context.scene
scn.frame_start = int(action.frame_range[0])
scn.frame_end = int(action.frame_range[1])

# (已撤销逐帧贴地补偿——那是邪修, 导致身体晃动且无法程序化。贴地问题留待从源头解决)

dg = bpy.context.evaluated_depsgraph_get()
body_ev = body.evaluated_get(dg)
scn.frame_set(1); bpy.context.view_layer.update()
base_v = [v.co.copy() for v in body_ev.data.vertices[:3000]]
lh1 = (arm.matrix_world @ arm.pose.bones['mixamorig:LeftHand'].matrix).translation.copy()
scn.frame_set(18); bpy.context.view_layer.update()
moved = sum(1 for i, v in enumerate(body_ev.data.vertices[:3000]) if (v.co - base_v[i]).length > 0.01)
lh18 = (arm.matrix_world @ arm.pose.bones['mixamorig:LeftHand'].matrix).translation.copy()
rf18 = (arm.matrix_world @ arm.pose.bones['mixamorig:RightFoot'].matrix).translation.copy()
print(f"mesh变形: {moved}/3000")
print(f"帧18左手: z={lh18.z:.3f}, 摆臂{(lh18-lh1).length*100:.1f}cm")
print(f"帧18右脚: z={rf18.z:.3f}")
ok = moved > 500 and lh18.z < 1.8 and (lh18-lh1).length > 0.02
print(f"行走验证: {'PASS 通过' if ok else 'FAIL 失败'}")

step07 = os.path.join(OUT, "04_行走测试.blend")
bpy.ops.wm.save_mainfile(filepath=step07)
print(f"保存: {step07}")
print("\n========== STEPS_3_TO_7_DONE ==========")
