"""合并多动画到04_动作测试.blend (v8: 直接计算局部四元数, 无读回, 符号连续化可靠)
修复用户反馈: 抖动(四元数符号翻转) + 扭曲帧 + 残留模型
烘焙设计:
 1. 目标: 我骨世界旋转 = 参考骨世界旋转 (矩阵空间已实证: 误差0.00°)
 2. 局部四元数 L 直接解算: L = (arm_world @ eval(parent) @ rest_rel)^-1 @ W
    eval链自己维护(父先子后), 不依赖Blender读回
 3. 符号连续化在 L 上做(自己持有值, 无stale问题)
 4. pb.rotation_quaternion = L 直接写入 (位置: 非Hips骨旋转不改头位置, 保持在rest链上)
 5. Hips: location = rest位置+垂直起伏(参考z×腿长比), 水平归零=原地
 6. 循环动画显式铺3周期(末帧==首帧去掉), 不用CYCLES修改器
 7. 清03垃圾+FBX参考物, 只留骨架/身体/眼球
用法: blender -b --python scripts/merge_anims.py
"""
import bpy, os, math
from mathutils import Matrix, Vector, Quaternion

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831"
RIG = os.path.join(BASE, "03_骨骼绑定.blend")
ANIM_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件"
OUT = os.path.join(BASE, "04_动作测试.blend")
N_CYCLES = 3

ANIMS = [
    ("Standard Walk", "Standard Walk.fbx"),
    ("Running", "Running.fbx"),
    ("Jump", "Jump.fbx"),
]

def depth(pb):
    d, p = 0, pb
    while p.parent:
        d += 1; p = p.parent
    return d

def qdiff(a, b):
    """四元数夹角(处理q与-q同一旋转: 先对齐符号)"""
    b2 = b.copy()
    if a.dot(b2) < 0: b2.negate()
    return a.rotation_difference(b2).angle

def cleanup_ref(arm, body):
    keep = {arm.name, body.name, 'Eye002_L', 'Eye002_R'}
    for o in list(bpy.data.objects):
        if o.name not in keep:
            bpy.data.objects.remove(o, do_unlink=True)

def bake_anim(walk_arm, arm, body, anim_name):
    ref_act = walk_arm.animation_data.action
    fstart, fend = int(ref_act.frame_range[0]), int(ref_act.frame_range[1])

    wm_ref = walk_arm.matrix_world
    ref_hips_z = (wm_ref @ walk_arm.data.bones['mixamorig:Hips'].head_local).z
    ref_foot_z = (wm_ref @ walk_arm.data.bones['mixamorig:LeftFoot'].head_local).z
    our_hips_z = (arm.matrix_world @ arm.data.bones['mixamorig:Hips'].head_local).z
    our_foot_z = (arm.matrix_world @ arm.data.bones['mixamorig:LeftFoot'].head_local).z
    leg_ratio = (our_hips_z - our_foot_z) / (ref_hips_z - ref_foot_z)

    rig_action = bpy.data.actions.new(name=anim_name)
    rig_action.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = rig_action
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.matrix_basis = Matrix.Identity(4)

    dg = bpy.context.evaluated_depsgraph_get()
    wa_ev = walk_arm.evaluated_get(dg)
    ref_pb_map = {b.name: wa_ev.pose.bones[b.name] for b in walk_arm.data.bones}
    ours = sorted((pb for pb in arm.pose.bones if pb.name in ref_pb_map), key=depth)

    arm_world_q = arm.matrix_world.to_quaternion()
    our_hips_rest_head = arm.data.bones['mixamorig:Hips'].head_local.copy()
    prev_quat = {}  # 每骨上一关键帧的局部四元数(符号连续化用)

    # 数值探测: Hips的pb.location哪个局部轴 = 世界+Z (rest骨有旋转, 不能写死)
    def ev_hips_world_z():
        bpy.context.view_layer.update()
        return (arm.matrix_world @ arm.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones['mixamorig:Hips'].matrix).translation.z
    pb_h = arm.pose.bones['mixamorig:Hips']
    z0 = ev_hips_world_z()
    z_axis_idx = None
    for idx, axis in enumerate([Vector((1,0,0)), Vector((0,1,0)), Vector((0,0,1))]):
        pb_h.location = axis  # 沿该局部轴移1米
        dz_test = ev_hips_world_z() - z0
        pb_h.location = Vector((0,0,0))
        if abs(dz_test - 1.0) < 0.01:
            z_axis_idx = idx
    assert z_axis_idx is not None, "找不到Hips location对应世界Z的局部轴!"
    print(f"  Hips location 世界Z轴 = 局部轴{z_axis_idx}")

    def set_frame(f_ref, f_key):
        bpy.context.scene.frame_set(f_ref)
        bpy.context.view_layer.update()
        # 自维护已实现世界旋转链(父先子后): C_b = 已实现世界旋转, 应等于参考世界旋转
        # 根骨: C = arm_world @ rest_root @ L  => L = rest_root^-1 @ arm_world^-1 @ W (rest旋转必须算入!)
        # 子骨: C = C_parent @ rest_rel @ L   => L = rest_rel^-1 @ C_parent^-1 @ W
        eval_q = {}
        for pb in ours:
            rp = ref_pb_map[pb.name]
            desired_world = wm_ref @ rp.matrix
            W_q = desired_world.to_quaternion()
            if pb.parent:
                rest_rel_q = (pb.parent.bone.matrix_local.inverted() @ pb.bone.matrix_local).to_quaternion()
                chain_q = eval_q[pb.parent.name] @ rest_rel_q
            else:
                chain_q = arm_world_q @ pb.bone.matrix_local.to_quaternion()
            L = chain_q.inverted() @ W_q
            # 符号连续化(在存储通道basis四元数上做, 防插值穿半球)
            pq = prev_quat.get(pb.name)
            if pq is not None and L.dot(pq) < 0:
                L.negate()
            prev_quat[pb.name] = L.copy()
            eval_q[pb.name] = chain_q @ L  # = 参考世界旋转(供子骨用)
            # 写入
            pb.rotation_quaternion = L
            if pb.name == 'mixamorig:Hips':
                dz = (desired_world.translation.z - ref_hips_z) * leg_ratio
                loc = Vector((0, 0, 0)); loc[z_axis_idx] = dz
                pb.location = loc  # 沿探测出的局部轴=世界Z
        for pb in ours:
            pb.keyframe_insert('rotation_quaternion', frame=f_key)
            if pb.name == 'mixamorig:Hips':
                pb.keyframe_insert('location', frame=f_key)

    # 循环检测
    def ref_sig(f):
        bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
        hp = wa_ev.pose.bones['mixamorig:Hips']
        return (hp.matrix.to_quaternion(),
                wa_ev.pose.bones['mixamorig:LeftFoot'].matrix.translation.copy(),
                wa_ev.pose.bones['mixamorig:RightFoot'].matrix.translation.copy())
    sig_s, sig_e = ref_sig(fstart), ref_sig(fend)
    is_cyclic = (sig_s[0].rotation_difference(sig_e[0]).angle < 0.1
                 and (sig_s[1]-sig_e[1]).length < 0.02 and (sig_s[2]-sig_e[2]).length < 0.02)
    print(f"  循环检测: {'循环' if is_cyclic else '非循环'}")

    # 参考动画自身的逐骨最大帧间差(自查基准: 我们应与之吻合)
    def ref_quats(f):
        bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
        return {bn: wa_ev.pose.bones[bn].matrix.to_quaternion().copy() for bn in ref_pb_map}
    ref_maxdiff = {}
    prev_r = ref_quats(fstart)
    for f in range(fstart + 1, fend + 1):
        cur_r = ref_quats(f)
        for bn in cur_r:
            d = qdiff(prev_r[bn], cur_r[bn])
            if d > ref_maxdiff.get(bn, 0): ref_maxdiff[bn] = d
        prev_r = cur_r

    if is_cyclic:
        bake_end = fend - 1
        cl = bake_end - fstart + 1
        for c in range(N_CYCLES):
            for i, f in enumerate(range(fstart, bake_end + 1)):
                set_frame(f, 1 + c * cl + i)
        total = N_CYCLES * cl
    else:
        for f in range(fstart, fend + 1):
            set_frame(f, f - fstart + 1)
        total = fend - fstart + 1

    print(f"  action slots={len(rig_action.slots)} layers={len(rig_action.layers)}")

    lf_i = {g.index for g in body.vertex_groups if 'LeftFoot' in g.name or 'LeftToe' in g.name}
    rf_i = {g.index for g in body.vertex_groups if 'RightFoot' in g.name or 'RightToe' in g.name}
    n_float = 0
    check_end = ((total - 1) // N_CYCLES + 1) if is_cyclic else total
    for f in range(1, check_end + 1):
        bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
        vs = body.evaluated_get(dg).data.vertices
        lmin = min((v.co.z for v in vs if any(g.group in lf_i and g.weight>0.1 for g in v.groups)), default=9)
        rmin = min((v.co.z for v in vs if any(g.group in rf_i and g.weight>0.1 for g in v.groups)), default=9)
        if min(lmin, rmin) > 0.03:
            n_float += 1
    stats = {"frames": total, "float_frames": n_float, "leg_ratio": leg_ratio, "cyclic": is_cyclic, "ref_maxdiff": ref_maxdiff}
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
for anim_name, fname in ANIMS:
    print(f"\n{'='*50}\n动画: {anim_name}")
    bpy.ops.import_scene.fbx(filepath=os.path.join(ANIM_DIR, fname))
    walk_arm = next((o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm and o.animation_data), None)
    assert walk_arm, f"{anim_name} FBX导入失败"
    act, stats = bake_anim(walk_arm, arm, body, anim_name)
    results[anim_name] = stats
    print(f"  帧数{stats['frames']} 腿长比{stats['leg_ratio']:.3f} 腾空帧{stats['float_frames']}")
    cleanup_ref(arm, body)

# ===== 自查 =====
scn = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
def bones_quat_at(f):
    scn.frame_set(f); bpy.context.view_layer.update()
    return {b.name: b.matrix.to_quaternion().copy() for b in arm.evaluated_get(dg).pose.bones}

print("\n=== 自查1: 循环连续性 ===")
all_pass = True
for an in ['Standard Walk', 'Running']:
    if not results[an]['cyclic']: continue
    arm.animation_data.action = bpy.data.actions[an]
    cl = (results[an]['frames'] - 1) // N_CYCLES + 1
    max_err, bf, bb = 0.0, -1, ''
    for f in [2, 5, cl//2, cl-1]:
        q1 = bones_quat_at(f); q2 = bones_quat_at(f+cl); q3 = bones_quat_at(f+2*cl)
        for bn in q1:
            d = max(qdiff(q1[bn], q2[bn]), qdiff(q1[bn], q3[bn]))
            if d > max_err: max_err, bf, bb = d, f, bn
    ok = max_err < 0.02
    all_pass &= ok
    print(f"  {an}: 周期差最大{math.degrees(max_err):.2f}度(帧{bf},{bb}) {'PASS' if ok else 'FAIL'}")

print("=== 自查2: 绝对姿态(帧1我们的世界旋转==参考世界旋转, 抓rest链偏移) ===")
arm.animation_data.action = bpy.data.actions['Standard Walk']
bpy.ops.import_scene.fbx(filepath=os.path.join(ANIM_DIR, "Standard Walk.fbx"))
walk_arm = next(o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm and o.animation_data)
wm_ref = walk_arm.matrix_world
ref_ev = walk_arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
scn.frame_set(1); bpy.context.view_layer.update()
ref_wq = {b.name: (wm_ref @ ref_ev.pose.bones[b.name].matrix).to_quaternion().copy() for b in walk_arm.data.bones}
max_abs, bb = 0.0, ''
our_ev = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
for b in arm.data.bones:
    if b.name not in ref_wq: continue
    oq = our_ev.pose.bones[b.name].matrix.to_quaternion()
    d = qdiff(oq, ref_wq[b.name])
    if d > max_abs: max_abs, bb = d, b.name
ok = max_abs < 0.05
all_pass &= ok
print(f"  绝对姿态最大偏差: {math.degrees(max_abs):.2f}度 ({bb}) {'PASS' if ok else 'FAIL'}")
bpy.data.objects.remove(walk_arm, do_unlink=True)
cleanup_ref(arm, body)  # 删自查导入的FBX残留(人体网格/关节球)

print("=== 自查3: 帧间平滑(逐骨对照参考基准: 偏差>20度=扭曲/翻转) ===")
for an, _ in ANIMS:
    arm.animation_data.action = bpy.data.actions[an]
    n = results[an]['frames']
    ref_md = results[an]['ref_maxdiff']
    bad = []
    prev = bones_quat_at(1)
    ours_max = {}
    for f in range(2, min(n, 105) + 1):
        cur = bones_quat_at(f)
        for bn in cur:
            d = qdiff(prev[bn], cur[bn])
            if d > ours_max.get(bn, 0): ours_max[bn] = d
        prev = cur
    # 逐骨对照: 我们的最大帧间差 与 参考最大帧间差 的差值
    for bn in ours_max:
        refd = ref_md.get(bn, 0)
        dev = abs(ours_max[bn] - refd)
        if dev > 0.35:  # 偏差>20度 = 该骨有翻转/扭曲
            bad.append((bn, math.degrees(ours_max[bn]), math.degrees(refd), math.degrees(dev)))
    ok = len(bad) == 0
    all_pass &= ok
    print(f"  {an}: {'PASS' if ok else f'FAIL {len(bad)}骨'}")
    for bn, od, rd, dv in sorted(bad, key=lambda x:-x[3])[:5]:
        print(f"    {bn}: 我们{od:.1f}° vs 参考{rd:.1f}° (偏差{dv:.1f}°)")
assert all_pass, "帧间平滑自查未通过!"

# ===== 保存 =====
walk_act = bpy.data.actions.get('Standard Walk')
arm.animation_data.action = walk_act
scn.frame_start, scn.frame_end = 1, results['Standard Walk']['frames']
print(f"\n文件内动作: {[a.name for a in bpy.data.actions]}")
bpy.ops.wm.save_mainfile(filepath=OUT)
for a in list(bpy.data.actions):
    if a.name.startswith('Armature|') or a.name == 'Armature':
        bpy.data.actions.remove(a)
bpy.ops.wm.save_mainfile()
final = [a.name for a in bpy.data.actions]
objs = [o.name for o in bpy.data.objects]
print(f"清理后动作: {final}")
print(f"场景对象: {objs}")
assert set(['Standard Walk','Running','Jump']) <= set(final), "动作丢失!"
print(f"已保存: {OUT}")
for k, v in results.items():
    print(f"  {k}: 帧{v['frames']} 循环={v['cyclic']} 腾空{v['float_frames']}")
print("========== MERGE_DONE ==========")
