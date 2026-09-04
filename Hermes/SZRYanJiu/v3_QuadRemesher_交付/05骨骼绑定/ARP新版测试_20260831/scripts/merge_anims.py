"""合并多动画到04_动作测试.blend: 一个文件含 行走/跑步/跳跃 三个动作, 动作编辑器下拉切换
方案: 逐个FBX导入→适配→立即删该参考骨架(避免多参考骨架同场导致next()抓错)
垂直起伏: 读参考骨架Hips世界z×腿长比, 写我们Hips局部y(已验证, 非逐帧补偿)
用法: blender -b --python scripts/merge_anims.py
"""
import bpy, os
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831"
RIG = os.path.join(BASE, "03_骨骼绑定.blend")
ANIM_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件"
OUT = os.path.join(BASE, "04_动作测试.blend")

ANIMS = [
    ("Standard Walk", "Standard Walk.fbx"),
    ("Running", "Running.fbx"),
    ("Jump", "Jump.fbx"),
]

def setup_anim(walk_arm, arm, body, anim_name):
    """把walk_arm的action适配到arm(我们骨架), 返回(action, stats)"""
    action = walk_arm.animation_data.action
    rig_action = action.copy()
    rig_action.name = anim_name

    data_slot = None
    for layer in rig_action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                if len(bag.fcurves) > 0:
                    data_slot = next((s for s in rig_action.slots if s.handle == bag.slot_handle), None)
    assert data_slot, "找不到动作数据slot"

    # 删Hips全部location(水平位移), 垂直起伏按参考腿长比重建
    for layer in rig_action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                if len(bag.fcurves) > 0:
                    for fc in list(bag.fcurves):
                        if 'mixamorig:Hips' in fc.data_path and 'location' in fc.data_path:
                            bag.fcurves.remove(fc)
                    break

    # 腿长比: 我们骨架腿长 / 参考骨架腿长
    wm_ref = walk_arm.matrix_world
    ref_hips_z = (wm_ref @ walk_arm.data.bones['mixamorig:Hips'].head_local).z
    ref_foot_z = (wm_ref @ walk_arm.data.bones['mixamorig:LeftFoot'].head_local).z
    our_hips_z = (arm.matrix_world @ arm.data.bones['mixamorig:Hips'].head_local).z
    our_foot_z = (arm.matrix_world @ arm.data.bones['mixamorig:LeftFoot'].head_local).z
    leg_ratio = (our_hips_z - our_foot_z) / (ref_hips_z - ref_foot_z)

    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = rig_action
    arm.animation_data.action_slot = data_slot

    # 逐帧恢复Hips垂直起伏(读参考骨架Hips世界z×腿长比, 写我们局部y=世界垂直)
    dg = bpy.context.evaluated_depsgraph_get()
    hips_pb = arm.pose.bones['mixamorig:Hips']
    fstart, fend = int(action.frame_range[0]), int(action.frame_range[1])
    for f in range(fstart, fend + 1):
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        wa_ev = walk_arm.evaluated_get(dg)
        ref_z = (wm_ref @ wa_ev.pose.bones['mixamorig:Hips'].head).z
        hips_pb.location.y = (ref_z - ref_hips_z) * leg_ratio
        hips_pb.keyframe_insert('location', index=1, frame=f)

    # 贴地检测(双脚最低点>3cm视为腾空)
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
    return rig_action, {"frames": fend-fstart+1, "float_frames": n_float, "leg_ratio": leg_ratio, "range": (fstart, fend)}

# 打开03骨架, 补mixamorig前缀
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
for anim_name, fname in ANIMS:
    print(f"\n{'='*50}\n动画: {anim_name}")
    bpy.ops.import_scene.fbx(filepath=os.path.join(ANIM_DIR, fname))
    # 找最新导入的参考骨架(排除我们的, 且有动画)
    walk_arm = next((o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm and o.animation_data), None)
    assert walk_arm, f"{anim_name} FBX导入失败"
    act, stats = setup_anim(walk_arm, arm, body, anim_name)
    act.use_fake_user = True
    results[anim_name] = stats
    print(f"  帧数{stats['frames']} 腿长比{stats['leg_ratio']:.3f} 腾空帧{stats['float_frames']}")
    # 立即删该参考骨架(避免下一个动画next()抓错)
    bpy.data.objects.remove(walk_arm, do_unlink=True)

# 活跃动作=行走, 帧范围对齐行走
walk_act = bpy.data.actions.get('Standard Walk')
arm.animation_data.action = walk_act
bpy.context.scene.frame_start, bpy.context.scene.frame_end = results['Standard Walk']['range']

# 保存(3个命名动作+参考动作都在, 先落盘保证动画不丢)
print(f"\n文件内动作: {[a.name for a in bpy.data.actions]}")
bpy.ops.wm.save_mainfile(filepath=OUT)
print(f"已保存: {OUT}")
for k, v in results.items():
    print(f"  {k}: 帧{v['frames']} 腾空{v['float_frames']}")
print("========== MERGE_DONE ==========")
