"""ARP全新测试 — 步骤3+4+5+6+7: 提取55骨→align_roll→use_connect→权重→行走验证
输入: 02_go_detect骨架.blend
输出: 03_骨骼绑定.blend, 04_动作测试.blend"""
import bpy, sys, os, json
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\05骨骼绑定"
OUT = os.path.join(BASE, "ARP新版测试_20260831")
IN = os.path.join(OUT, "02_go_detect骨架.blend")
WALK_FBX = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\原始文件\Mixamo动画文件\Standard Walk.fbx"
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

# ============ 步骤6.5: 并入眼球并绑到Head骨 ============
# 2026-09-16 用户要求: 眼球从02起全程连贯(02输出/03UV/04烘焙/导出都含眼球)。
# 本步骤: 若网格里已带眼球则直接蒙皮Head骨; 若没有(旧文件)才从01_2并入。
print("\n########## 步骤6.5: 并入眼球 ##########")
# V2.1 P1-6: 修死路径(旧目录名 01A眼窝与眼球/models 已废) → 现路径 01a眼窝眼球/输出/
#   BASE=05骨骼绑定, 单个 .. 即项目根(已验证). 仅在"网格未随02带眼球"的兜底分支使用;
#   正常流程眼球从02起已随网格连贯(见下方 _eye_existing 分支)。
EYE_BLEND = os.path.join(BASE, "..", "01a眼窝眼球", "输出", "01_2_eyeball_placed.blend")
EYE_BLEND = os.path.normpath(EYE_BLEND)
head_head = None  # Head骨世界位置
mw_arm = arm.matrix_world
head_bone = arm.data.bones.get('Head')
# 2026-09-16 用户要求: 眼球从02起全程连贯(02输出→03UV→04烘焙都含眼球) → 此处不再重复并入
_eye_existing = [o for o in bpy.data.objects if o.name.startswith('Eye002')]
if head_bone and _eye_existing:
    eyes = _eye_existing
    bpy.context.view_layer.update()
    print(f"眼球已随网格传来(02起连贯): {[o.name for o in eyes]}")
elif head_bone and os.path.exists(EYE_BLEND):
    # 兼容: 旧流程/网格里没有眼球时, 从01_2 link并入(保持其世界位置)
    with bpy.data.libraries.load(EYE_BLEND) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith('Eye002')]
    eyes = [o for o in dst.objects if o is not None]
    for o in eyes:
        bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.update()
else:
    eyes = []
    print(f"  警告: 眼球blend不存在({EYE_BLEND})或无Head骨, 跳过")

# 蒙皮(两种情况都要做, 2026-09-16修正: 原缩进导致已有眼球分支漏蒙皮)
# 眼球蒙皮到Head骨: 顶点组全部指向Head(权重1.0) + Armature修改器
# 这样眼球保持世界位置, 跟随Head骨动(不动顶点, 只加修改器); 3B标准化时随网格一起重摆
# v86.2(2026-09-18): 顶点组名跟随【骨架实际Head骨名】—— 此前硬编码'mixamorig:Head', 而本步骨架
#   骨名无前缀(Head) → 名不对骨 → 03/03B里动骨骼眼球不跟随(实测位移0.00mm); 直到retarget统一
#   加前缀才碰巧对上. 现在按实际骨名取, 前后两个阶段都对.
_hb = next((b.name for b in arm.data.bones if b.name.split(':')[-1].lower() == 'head'), None)
for o in eyes:
    if _hb is None:
        print(f"  警告: 骨架无 Head 骨, {o.name} 蒙皮跳过")
        continue
    vg = o.vertex_groups.get(_hb) or o.vertex_groups.new(name=_hb)
    for g in list(o.vertex_groups):          # 清掉与骨名不符的历史遗留组(如 mixamorig:Head)
        if g.name != _hb:
            o.vertex_groups.remove(g)
    vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
    _mods = [m for m in o.modifiers if m.type == 'ARMATURE']
    if not _mods:
        mod = o.modifiers.new('Armature', 'ARMATURE')
        mod.object = arm
        mod.use_deform_preserve_volume = True
    else:                                    # 已有修改器但目标不对也要纠正
        for m in _mods:
            if m.object is not arm:
                print(f"  {o.name}: ARMATURE修改器目标 {getattr(m.object,'name',None)} → {arm.name} 纠正")
                m.object = arm
            m.use_deform_preserve_volume = True
    # v86.3(2026-09-18, 用户实测"物体模式移动骨架1m眼珠不动"): 眼珠还必须【父级到骨架物体】!
    #   根因: ARMATURE修改器只承载【骨骼形变】, 不含【骨架物体自身位移】; 身体跟随是因为它被父级到骨架.
    #   实测: 移骨架+1m → 身体1000mm / 眼珠0.0mm. 补父级(保持世界位置: matrix_parent_inverse 抵消).
    if o.parent is not arm:
        _p0 = tuple(round(float(v), 4) for v in o.matrix_world.translation)
        o.parent = arm
        o.parent_type = 'OBJECT'
        o.matrix_parent_inverse = arm.matrix_world.inverted()
        bpy.context.view_layer.update()
        _p1 = tuple(round(float(v), 4) for v in o.matrix_world.translation)
        print(f"  {o.name}: 已父级到骨架(世界位置 {_p0} → {_p1}, 应不变)")
if eyes:
    print(f"眼球蒙皮 {len(eyes)}个 (Head骨, 位置不变)")
    # 验证眼球世界位置
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    for o in eyes:
        p = o.evaluated_get(dg).matrix_world.translation
        print(f"  {o.name} 绑定后世界位置: ({p.x:.3f},{p.y:.3f},{p.z:.3f})")

step06 = os.path.join(OUT, "03_骨骼绑定.blend")
bpy.ops.wm.save_mainfile(filepath=step06)
print(f"保存: {step06}")

# ============ (V2.1 L-05) 原"步骤7: 行走动画验证"已移除 ============
#   移除依据(全部核实): ①03_骨骼绑定.blend 在步骤7之前已保存(=③B/④的唯一输入, 骨名无前缀,
#   与 normalize_to_tpose 的预期一致); ②步骤7给骨/顶点组加的 mixamorig: 前缀只作用于本文件
#   会话内的 04_动作测试.blend, 而该文件被 05④ retarget_mixamo.py 完全覆盖(其输入=03B);
#   ③retarget 自己统一加前缀。故步骤7(FBX导入+36帧求值+存盘)为纯冗余死代码。
#   done_mark 保留原字符串 STEPS_3_TO_7_DONE(控制台校验用, 不改名以免动总控口径)。
print("\n========== STEPS_3_TO_7_DONE ==========")
