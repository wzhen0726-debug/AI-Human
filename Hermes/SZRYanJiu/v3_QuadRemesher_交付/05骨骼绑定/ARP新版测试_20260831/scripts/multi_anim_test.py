"""多动画测试: 对03骨骼绑定.blend套多个Mixamo动画, 每个独立产物+自检
用法: blender -b --python multi_anim_test.py
动画: Standard Walk / Running / Jump
产物: anim_StandardWalk.blend / anim_Running.blend / anim_Jump.blend
"""
import bpy, os
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831"
RIG = os.path.join(BASE, "03_骨骼绑定.blend")
ANIM_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件"
OUT = os.path.join(BASE, "多动画测试")
os.makedirs(OUT, exist_ok=True)

ANIMS = [
    ("Standard Walk", "Standard Walk.fbx"),
    ("Running", "Running.fbx"),
    ("Jump", "Jump.fbx"),
]

def setup_anim(walk_arm, arm, body):
    """把walk_arm的action适配到arm(我们骨架), 返回(stats)"""
    action = walk_arm.animation_data.action
    rig_action = action.copy()
    rig_action.name = "Anim"

    # 找数据slot
    data_slot = None
    for layer in rig_action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                if len(bag.fcurves) > 0:
                    data_slot = next((s for s in rig_action.slots if s.handle == bag.slot_handle), None)
    assert data_slot

    # 删Hips的x/z水平位移(原地), 保留垂直起伏——但轴向因骨架而异, 统一全删Hips location再重建垂直
    removed = 0
    for layer in rig_action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                if len(bag.fcurves) > 0:
                    for fc in list(bag.fcurves):
                        if 'mixamorig:Hips' in fc.data_path and 'location' in fc.data_path:
                            bag.fcurves.remove(fc); removed += 1
                    break

    # 腿长比: 我们骨架 vs 这个动画的参考骨架
    wm_ref = walk_arm.matrix_world
    ref_hips_z = (wm_ref @ walk_arm.data.bones['mixamorig:Hips'].head_local).z
    ref_foot_z = (wm_ref @ walk_arm.data.bones['mixamorig:LeftFoot'].head_local).z
    our_hips_z = (arm.matrix_world @ arm.data.bones['mixamorig:Hips'].head_local).z
    our_foot_z = (arm.matrix_world @ arm.data.bones['mixamorig:LeftFoot'].head_local).z
    leg_ratio = (our_hips_z - our_foot_z) / (ref_hips_z - ref_foot_z)

    # 绑定
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = rig_action
    arm.animation_data.action_slot = data_slot

    # 逐帧恢复Hips垂直起伏(读参考世界z, 按腿长比缩, 写我们局部y=世界垂直)
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

    # 贴地检测
    lf_i = {g.index for g in body.vertex_groups if 'LeftFoot' in g.name or 'LeftToe' in g.name}
    rf_i = {g.index for g in body.vertex_groups if 'RightFoot' in g.name or 'RightToe' in g.name}
    n_float = 0
    bev0 = body.evaluated_get(dg)
    for f in range(fstart, fend + 1):
        bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
        vs = body.evaluated_get(dg).data.vertices
        lmin = min((v.co.z for v in vs if any(g.group in lf_i and g.weight>0.1 for g in v.groups)), default=9)
        rmin = min((v.co.z for v in vs if any(g.group in rf_i and g.weight>0.1 for g in v.groups)), default=9)
        if min(lmin, rmin) > 0.03:
            n_float += 1
    return {"frames": fend-fstart+1, "float_frames": n_float, "leg_ratio": leg_ratio}

for anim_name, fname in ANIMS:
    fpath = os.path.join(ANIM_DIR, fname)
    print(f"\n{'='*50}\n动画: {anim_name} ({fname})")
    bpy.ops.wm.open_mainfile(filepath=RIG)
    arm = bpy.data.objects.get('MixamoSkeleton')
    body = max((o for o in bpy.data.objects if o.type=='MESH' and o.name!='MixamoSkeleton'), key=lambda o: len(o.data.vertices))
    # 03保存时骨名还没加mixamorig前缀(前缀在步骤7加的), 这里先补上
    for b in arm.data.bones:
        if not b.name.startswith("mixamorig:"):
            b.name = "mixamorig:" + b.name
    for vg in body.vertex_groups:
        if not vg.name.startswith("mixamorig:"):
            vg.name = "mixamorig:" + vg.name
    # 眼球等独立物体(走parent_bone不走蒙皮)不强制改名
    # 清旧动画
    if arm.animation_data: arm.animation_data_clear()
    bpy.ops.import_scene.fbx(filepath=fpath)
    walk_arm = next((o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm and o.animation_data), None)
    assert walk_arm, f"{anim_name} FBX导入失败"
    stats = setup_anim(walk_arm, arm, body)
    # 删参考骨架
    for o in [o for o in bpy.data.objects if o != arm and o != body and 'Eye' not in o.name]:
        if o.type in ('ARMATURE','MESH'):
            bpy.data.objects.remove(o, do_unlink=True)
    out = os.path.join(OUT, f"anim_{anim_name.replace(' ','')}.blend")
    bpy.ops.wm.save_mainfile(filepath=out)
    print(f"  帧数{stats['frames']} 腿长比{stats['leg_ratio']:.3f} 腾空帧{stats['float_frames']}")
    print(f"  保存: {out}")

print("\n========== MULTI_ANIM_DONE ==========")
