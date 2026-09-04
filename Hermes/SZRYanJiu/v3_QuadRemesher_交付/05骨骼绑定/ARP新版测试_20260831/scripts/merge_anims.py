"""合并多动画到04_动作测试.blend: 行走/跑步/跳跃 三动作, 动作编辑器切换
关键修复(用户反馈):
 1. 腿外八/姿势古怪: 我们骨架rest=模型自然站姿(腿分开, LeftUpLeg朝向差8.2度),
    Mixamo参考rest腿并拢。直接套局部旋转会继承rest差异 -> 外八。
    方案: 世界旋转拷贝烘焙——逐帧逐骨把我骨世界朝向对齐参考骨世界朝向,
    位置走我们自己骨架的rest链(保持骨长), 彻底消除rest姿态差异。
 2. 跑步播一半定格: Mixamo是循环动画, 我们只播动作范围。
    方案: 全部fcurve加CYCLIC修改器 + 场景帧范围拉长到3个循环周期。
用法: blender -b --python scripts/merge_anims.py
"""
import bpy, os
from mathutils import Matrix, Vector, Quaternion

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831"
RIG = os.path.join(BASE, "03_骨骼绑定.blend")
ANIM_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件"
OUT = os.path.join(BASE, "04_动作测试.blend")

# (名字, 文件, 是否循环)
ANIMS = [
    ("Standard Walk", "Standard Walk.fbx", True),
    ("Running", "Running.fbx", True),
    ("Jump", "Jump.fbx", False),  # 跳跃单次起跳, 不循环
]

def depth(pb):
    d, p = 0, pb
    while p.parent:
        d += 1; p = p.parent
    return d

def bake_anim(walk_arm, arm, body, anim_name, cyclic):
    """世界旋转拷贝烘焙: 逐帧逐骨把我骨世界朝向对齐参考骨, 位置走我们自己的rest链"""
    ref_act = walk_arm.animation_data.action
    fstart, fend = int(ref_act.frame_range[0]), int(ref_act.frame_range[1])

    # 腿长比: 我们骨架腿长 / 参考骨架腿长 (Hips垂直起伏按此缩放)
    wm_ref = walk_arm.matrix_world
    ref_hips_z = (wm_ref @ walk_arm.data.bones['mixamorig:Hips'].head_local).z
    ref_foot_z = (wm_ref @ walk_arm.data.bones['mixamorig:LeftFoot'].head_local).z
    our_hips_z = (arm.matrix_world @ arm.data.bones['mixamorig:Hips'].head_local).z
    our_foot_z = (arm.matrix_world @ arm.data.bones['mixamorig:LeftFoot'].head_local).z
    leg_ratio = (our_hips_z - our_foot_z) / (ref_hips_z - ref_foot_z)

    # rest朝向差异诊断(外八根因证据)
    for bn in ['mixamorig:LeftUpLeg', 'mixamorig:LeftLeg', 'mixamorig:LeftFoot']:
        if bn in walk_arm.data.bones and bn in arm.data.bones:
            ref_dir = (wm_ref @ walk_arm.data.bones[bn].matrix_local).to_quaternion() @ Vector((0,1,0))
            our_dir = (arm.matrix_world @ arm.data.bones[bn].matrix_local).to_quaternion() @ Vector((0,1,0))
            print(f"  rest朝向差 {bn}: {ref_dir.angle(our_dir)*57.2958:.1f}度")

    # 新动作: 复制参考动作拿slot结构, 清空fcurve后重烤
    rig_action = ref_act.copy()
    rig_action.name = anim_name
    rig_action.use_fake_user = True
    for layer in rig_action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in list(bag.fcurves):
                    bag.fcurves.remove(fc)

    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = rig_action
    data_slot = None
    for layer in rig_action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for s in rig_action.slots:
                    if s.handle == bag.slot_handle:
                        data_slot = s
                if data_slot: break
        if data_slot: break
    if data_slot:
        arm.animation_data.action_slot = data_slot

    dg = bpy.context.evaluated_depsgraph_get()
    wa_ev = walk_arm.evaluated_get(dg)
    ref_pb_map = {b.name: wa_ev.pose.bones[b.name] for b in walk_arm.data.bones}
    ours = sorted((pb for pb in arm.pose.bones if pb.name in ref_pb_map), key=depth)  # 父先子后

    arm_inv = arm.matrix_world.inverted()
    our_hips_rest_head = arm.data.bones['mixamorig:Hips'].head_local.copy()

    for f in range(fstart, fend + 1):
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        for pb in ours:
            rp = ref_pb_map[pb.name]
            desired_world = wm_ref @ rp.matrix  # 参考骨世界矩阵
            R = (arm_inv @ desired_world).to_quaternion()  # 参考世界朝向 -> 我们armature空间
            if pb.name == 'mixamorig:Hips':
                # Hips: 旋转拷贝 + 位置=rest位置+垂直起伏(参考Hips世界z变化×腿长比, 水平归零=原地)
                dz = (desired_world.translation.z - ref_hips_z) * leg_ratio
                pos = our_hips_rest_head + Vector((0, 0, dz))
                pb.matrix = Matrix.Translation(pos) @ R.to_matrix().to_4x4()
            else:
                # 其他骨: 头位置=父骨姿态下我们自己的rest链位置(保持骨长), 朝向=参考世界朝向
                if pb.parent:
                    rest_in_parent = pb.parent.bone.matrix_local.inverted() @ pb.bone.matrix_local
                    head_pos = (pb.parent.matrix @ rest_in_parent).translation
                else:
                    head_pos = pb.bone.matrix_local.translation
                pb.matrix = Matrix.Translation(head_pos) @ R.to_matrix().to_4x4()
        for pb in ours:
            pb.keyframe_insert('rotation_quaternion', frame=f)
            if pb.name == 'mixamorig:Hips':
                pb.keyframe_insert('location', frame=f)

    # CYCLES循环: 否则播完动作范围后fcurve常数外推=定格
    if cyclic:
        n = 0
        for layer in rig_action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for fc in bag.fcurves:
                        fc.modifiers.new(type='CYCLES')
                        n += 1
        print(f"  CYCLES: {n}条fcurve")

    # 贴地检测(双脚最低点>3cm=腾空)
    lf_i = {g.index for g in body.vertex_groups if 'LeftFoot' in g.name or 'LeftToe' in g.name}
    rf_i = {g.index for g in body.vertex_groups if 'RightFoot' in g.name or 'RightToe' in g.name}
    n_float = 0
    for f in range(fstart, fend + 1):
        bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
        vs = body.evaluated_get(dg).data.vertices
        lmin = min((v.co.z for v in vs if any(g.group in lf_i and g.weight>0.1 for g in v.groups)), default=9)
        rmin = min((v.co.z for v in vs if any(g.group in rf_i and g.weight>0.1 for g in v.groups)), default=9)
        if min(lmin, rmin) > 0.03:
            n_float += 1
    stats = {"frames": fend-fstart+1, "float_frames": n_float, "leg_ratio": leg_ratio, "range": (fstart, fend)}
    return rig_action, stats

# ===== 主流程 =====
bpy.ops.wm.open_mainfile(filepath=RIG)
arm = bpy.data.objects.get('MixamoSkeleton')
body = max((o for o in bpy.data.objects if o.type=='MESH' and o.name!='MixamoSkeleton'), key=lambda o: len(o.data.vertices))
for b in arm.data.bones:
    if not b.name.startswith("mixamorig:"):
        b.name = "mixamorig:" + b.name
for vg in body.vertex_groups:
    if not vg.name.startswith("mixamorig:"):
        vg.name = "mixamorig:" + vg.name
if arm.animation_data: arm.animation_data_clear()

results = {}
for anim_name, fname, cyclic in ANIMS:
    print(f"\n{'='*50}\n动画: {anim_name}")
    bpy.ops.import_scene.fbx(filepath=os.path.join(ANIM_DIR, fname))
    walk_arm = next((o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm and o.animation_data), None)
    assert walk_arm, f"{anim_name} FBX导入失败"
    act, stats = bake_anim(walk_arm, arm, body, anim_name, cyclic)
    results[anim_name] = stats
    print(f"  帧数{stats['frames']} 腿长比{stats['leg_ratio']:.3f} 腾空帧{stats['float_frames']}")
    bpy.data.objects.remove(walk_arm, do_unlink=True)  # 立即删, 防下个动画抓错骨架

# 活跃=行走; 场景帧范围拉长到3个循环(看得见循环效果)
walk_act = bpy.data.actions.get('Standard Walk')
arm.animation_data.action = walk_act
ws, we = results['Standard Walk']['range']
bpy.context.scene.frame_start, bpy.context.scene.frame_end = ws, ws + (we - ws) * 3

print(f"\n文件内动作: {[a.name for a in bpy.data.actions]}")
bpy.ops.wm.save_mainfile(filepath=OUT)  # 先落盘保动作
for a in list(bpy.data.actions):
    if a.name.startswith('Armature|'):
        bpy.data.actions.remove(a)
bpy.ops.wm.save_mainfile()
final = [a.name for a in bpy.data.actions]
print(f"清理后动作: {final}")
assert set(['Standard Walk','Running','Jump']) <= set(final), "动作丢失!"
print(f"已保存: {OUT}")
for k, v in results.items():
    print(f"  {k}: 帧{v['frames']} 腾空{v['float_frames']}")
print("========== MERGE_DONE ==========")
