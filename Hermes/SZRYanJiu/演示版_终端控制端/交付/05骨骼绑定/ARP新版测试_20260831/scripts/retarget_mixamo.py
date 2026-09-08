"""04_动作测试.blend 生成: Mixamo动画绑定 — rest保持+增量重定向版 (2026-09-08 v3)

v3定案(修内八/猫步): 骨架结构不动, 且**保留我们自己的rest朝向**, 只叠加Mixamo的运动增量:
    D_b(t)  = R_ref_rest_b^-1 @ W_ref_b(t)              [参考骨相对自身rest的世界旋转增量]
    q_b(t)  = A_b^-1 @ D_parent(t)^-1 @ A_b @ D_b(t)    [写入我们骨骼的局部四元数]
    A_b     = R_our_rest_parent^-1 @ R_our_rest_b       [我们骨架的rest相对朝向]
  效果: 我们的姿态 = 自己的rest站姿 ⊕ 参考的动作。外展/外八/踝间距全部保持自身比例。

**内八根因(v2的C补偿是错的, 实测数据)**:
  v2曾加 rest补偿常量 C_b = R_our_rest^-1 @ R_ref_rest 使绝对世界朝向==参考(当时自查0.000°"全过"),
  但这等于把我们的站姿扳成Mixamo演员的站姿。实测两者rest差异巨大:
    大腿外展: 我们8.18° vs Mixamo 0.35°(近乎垂直)
    脚掌外八: 我们+9.37° vs Mixamo +1.53°
    踝部离中线: 我们±142.9mm vs Mixamo±91.2mm
  C补偿后大腿被扭垂直、脚被扭正直、脚落点向中线收拢 → 网格在自己岔开的rest上被向内扭
  → 用户看到的"内八感 + T台猫步"。教训: 绝对朝向匹配≠动作正确, 重定向的目标是
  "自己的站姿 + 参考的动作", 绝不能把角色扳成参考演员的体型/站姿。

**action帧范围坑**: 只设 use_frame_range=True 而不设 frame_start/frame_end, 会让
  act.frame_range 恒为 [1,1] → 任何按它遍历的脚本只跑1帧(诊断时误以为动画只有1帧)。
  必须显式 act.frame_start, act.frame_end = fstart, fend。

Hips平移: 只重建垂直起伏(参考Hips世界z变化×实测腿长比, 写入数值探测出的垂直轴)。
帧范围按参考动画原始范围. 四元数逐帧符号连续化(dot<0取反)防插值长弧抖动.
参考rest用每个动画FBX自带的绑定姿势(Mixamo各文件角色比例不同, 腿长比逐个实测)。

用法: blender -b --python scripts/retarget_mixamo.py
"""
import bpy, os, math
from mathutils import Matrix, Vector, Quaternion

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付\05骨骼绑定\ARP新版测试_20260831"
RIG = os.path.join(BASE, "03_骨骼绑定.blend")
ANIM_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\原始文件\Mixamo动画文件"
OUT = os.path.join(BASE, "04_动作测试.blend")
ANIMS = [("Standard Walk", "Standard Walk.fbx"), ("Running", "Running.fbx"), ("Jump", "Jump.fbx")]
PREF = "mixamorig:"

# ---------- 打开健康骨架(03, 结构不动) ----------
bpy.ops.wm.open_mainfile(filepath=RIG)
arm = bpy.data.objects.get('MixamoSkeleton')
body = next(o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('tripo'))
eyes = [o for o in bpy.data.objects if o.name.startswith('Eye002')]
print(f"输入骨架: {len(arm.data.bones)}骨 连接骨={sum(1 for b in arm.data.bones if b.use_connect)} "
      f"身体顶点组={len(body.vertex_groups)} 眼球={[e.name for e in eyes]}")
assert len(body.vertex_groups) >= 50, "身体蒙皮权重缺失!"
for e in eyes:
    assert any('Head' in vg.name for vg in e.vertex_groups), f"{e.name}未蒙皮到Head!"

# 统一mixamorig:前缀(先改骨名, 再防御式同步顶点组名)
for b in arm.data.bones:
    if not b.name.startswith(PREF): b.name = PREF + b.name
boneset = {b.name for b in arm.data.bones}
for meshobj in [body] + eyes:
    for vg in meshobj.vertex_groups:
        if vg.name not in boneset and (PREF + vg.name) in boneset:
            vg.name = PREF + vg.name
if arm.animation_data: arm.animation_data_clear()

# ---------- 结构快照(结束时必须逐字节一致) ----------
snap = {b.name: (b.head_local.copy(), b.tail_local.copy(), b.use_connect,
                 b.parent.name if b.parent else None) for b in arm.data.bones}

# ---------- 我们的rest世界朝向 ----------
aw = arm.matrix_world
R_our = {b.name: (aw @ b.matrix_local).to_quaternion() for b in arm.data.bones}
A = {}   # A_b = R_our_parent^-1 @ R_our_b ; 根骨 parent=identity
for b in arm.data.bones:
    p = b.parent
    A[b.name] = (R_our[p.name].inverted() @ R_our[b.name]) if p else R_our[b.name].copy()

# Hips垂直轴探测(动画绑定前, 无action干扰)
def ev_hips_z():
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    return (aw @ arm.evaluated_get(dg).pose.bones[PREF+'Hips'].matrix).translation.z
pb_h = arm.pose.bones[PREF+'Hips']
z0 = ev_hips_z(); dz_vals = []
for axis in [Vector((1,0,0)), Vector((0,1,0)), Vector((0,0,1))]:
    pb_h.location = axis
    dz_vals.append(round(ev_hips_z() - z0, 4))
    pb_h.location = Vector((0,0,0))
z_axis = max(range(3), key=lambda i: abs(dz_vals[i]))
print(f"Hips垂直轴探测: dz={dz_vals} -> 轴{z_axis}")
assert abs(dz_vals[z_axis]) > 0.9, f"找不到Hips垂直轴! dz={dz_vals}"

for pb in arm.pose.bones:
    pb.rotation_mode = 'QUATERNION'

our_hips_z = (aw @ arm.data.bones[PREF+'Hips'].matrix_local).translation.z
our_foot_z = (aw @ arm.data.bones[PREF+'LeftFoot'].matrix_local).translation.z

keep = {arm.name, body.name, 'Eye002_L', 'Eye002_R'}
results = {}
for anim_name, fname in ANIMS:
    print(f"\n{'='*50}\n动画: {anim_name} ({fname})")
    bpy.ops.import_scene.fbx(filepath=os.path.join(ANIM_DIR, fname))
    refa = next(o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm and o.animation_data)
    assert refa, f"{anim_name} FBX导入失败"
    # 删参考网格(加速逐帧求值), 只留参考骨架
    for o in list(bpy.data.objects):
        if o.name not in keep and o != refa and o.type == 'MESH':
            bpy.data.objects.remove(o, do_unlink=True)
    wm_ref = refa.matrix_world
    rb = refa.data.bones
    # 参考rest世界朝向/位置(此FBX自带绑定姿势; 参考骨名与我们同名=已带前缀)
    R_ref_rest = {n: (wm_ref @ rb[n].matrix_local).to_quaternion() for n in rb.keys() if n in A}
    ref_hips_z = (wm_ref @ rb[PREF+'Hips'].head_local).z
    ref_foot_z = (wm_ref @ rb[PREF+'LeftFoot'].head_local).z
    leg_ratio = (our_hips_z - our_foot_z) / (ref_hips_z - ref_foot_z)
    print(f"  腿长比(实测): {leg_ratio:.3f}")

    # 映射表: 我们骨名 -> 参考骨名(同前缀名) ; 需要父骨也在参考里
    mapped = {}
    for b in arm.data.bones:
        if b.name in R_ref_rest:
            p = b.parent
            if p is None or p.name in R_ref_rest:
                mapped[b.name] = b.name
    print(f"  可重定向骨: {len(mapped)}/{len(arm.data.bones)}")

    ref_act = refa.animation_data.action
    fstart, fend = int(ref_act.frame_range[0]), int(ref_act.frame_range[1])

    # 新建action并绑定(不显式建slot: keyframe_insert会自动建正确的OBJECT槽;
    #  显式slots.new(id_type='ARMATURE')建的槽对object动画数据无效, 会导致后续赋值RuntimeError)
    act = bpy.data.actions.new(anim_name)
    act.use_fake_user = True
    # 显式设帧范围(只设use_frame_range会让act.frame_range恒为[1,1], 下游按它遍历只跑1帧)
    act.frame_start, act.frame_end = fstart, fend
    act.use_frame_range = True  # 切换动作时场景帧范围跟随动作
    if arm.animation_data is None: arm.animation_data_create()
    arm.animation_data.action = act

    sign_prev = {}
    dg = bpy.context.evaluated_depsgraph_get()
    for f in range(fstart, fend + 1):
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        ref_ev = refa.evaluated_get(dg)
        # 参考骨当前世界四元数
        W_ref = {n: (wm_ref @ ref_ev.pose.bones[n].matrix).to_quaternion()
                 for n in mapped.values()}
        # D_b(t) = R_ref_rest^-1 @ W_ref(t): 参考骨相对自身rest的世界旋转增量.
        # 不做绝对朝向补偿(见文件头"内八根因"): 我们要的是"自己的站姿 + 参考的动作",
        # 不是"变成参考的站姿".
        Dt = {n: R_ref_rest[n].inverted() @ W_ref[n] for n in W_ref}
        for bn in mapped:
            pb = arm.pose.bones[bn]
            p = arm.data.bones[bn].parent
            Dp = Dt.get(p.name, Quaternion((1,0,0,0))) if p else Quaternion((1,0,0,0))
            q = A[bn].inverted() @ Dp.inverted() @ A[bn] @ Dt[bn]
            # 符号连续化: 与上一帧点积<0则取反(防插值走长弧)
            pq = sign_prev.get(bn)
            if pq is not None and pq.dot(q) < 0: q.negate()
            sign_prev[bn] = q.copy()
            pb.rotation_quaternion = q
            pb.keyframe_insert('rotation_quaternion', frame=f)
        # Hips垂直起伏
        ref_z = (wm_ref @ ref_ev.pose.bones[PREF+'Hips'].matrix).translation.z
        loc = Vector((0,0,0)); loc[z_axis] = (ref_z - ref_hips_z) * leg_ratio
        pb_h.location = loc
        pb_h.keyframe_insert('location', frame=f)
        if f == fstart or f == fend:
            print(f"  帧{f}: 已写{len(mapped)}骨")

    # 清参考残留
    for o in list(bpy.data.objects):
        if o.name not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    results[anim_name] = {"range": (fstart, fend), "frames": fend-fstart+1,
                          "leg_ratio": leg_ratio, "n_mapped": len(mapped)}
    print(f"  绑定完成: 帧{fstart}-{fend} ({fend-fstart+1}帧)")

# ========== 自查 ==========
scn = bpy.context.scene
print("\n" + "="*50 + "\n自查")
all_pass = True

# 1) 结构一致性: 骨骼head/tail/connect/parent与03快照完全一致
bad = 0
for b in arm.data.bones:
    h, t, c, p = snap[b.name]
    if (b.head_local - h).length > 1e-9 or (b.tail_local - t).length > 1e-9 \
       or b.use_connect != c or (b.parent.name if b.parent else None) != p:
        bad += 1
n_conn = sum(1 for b in arm.data.bones if b.use_connect)
print(f"1) 结构: 与03快照差异骨={bad} 连接骨={n_conn}/{len(arm.data.bones)} "
      f"{'PASS' if bad==0 and n_conn>=41 else 'FAIL'}")
all_pass &= (bad == 0 and n_conn >= 41)

# 2) 关节重叠: 膝/踝/肘/腕 tail==child head
overlap_bad = []
for pn, cn in [(PREF+'LeftUpLeg',PREF+'LeftLeg'),(PREF+'LeftLeg',PREF+'LeftFoot'),
               (PREF+'RightUpLeg',PREF+'RightLeg'),(PREF+'RightLeg',PREF+'RightFoot'),
               (PREF+'LeftArm',PREF+'LeftForeArm'),(PREF+'LeftForeArm',PREF+'LeftHand'),
               (PREF+'RightArm',PREF+'RightForeArm'),(PREF+'RightForeArm',PREF+'RightHand'),
               (PREF+'Spine',PREF+'Spine1'),(PREF+'Spine1',PREF+'Spine2')]:
    p = arm.data.bones.get(pn); c = arm.data.bones.get(cn)
    if p and c:
        d = (c.head_local - p.tail_local).length
        if d > 1e-6: overlap_bad.append((cn, d*1000))
print(f"2) 链关节重叠: 错位={overlap_bad if overlap_bad else 0} {'PASS' if not overlap_bad else 'FAIL'}")
all_pass &= not overlap_bad

# 3) 动画有效性: Hips起伏 + 脚贴地 + 四元数无跳变
dg = bpy.context.evaluated_depsgraph_get()
lf_i = {g.index for g in body.vertex_groups if 'LeftFoot' in g.name or 'LeftToe' in g.name}
rf_i = {g.index for g in body.vertex_groups if 'RightFoot' in g.name or 'RightToe' in g.name}
CHK = [PREF+n for n in ('LeftFoot','RightFoot','LeftHand','RightHand','LeftLeg','RightLeg','Spine2','Head')]
for anim_name, fname in ANIMS:
    act = bpy.data.actions[anim_name]
    arm.animation_data.action = act
    # 选带fcurves的正确槽(自动建的OBJECT槽)
    for s in act.slots:
        try:
            arm.animation_data.action_slot = s
            break
        except RuntimeError:
            continue
    fstart, fend = results[anim_name]['range']
    floats, zs, max_step = [], [], 0.0
    prev_q = {}
    for f in range(fstart, fend + 1):
        scn.frame_set(f); bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        arm_ev = arm.evaluated_get(dg)
        vs = body.evaluated_get(dg).data.vertices
        lmin = min((v.co.z for v in vs if any(g.group in lf_i and g.weight>0.1 for g in v.groups)), default=9)
        rmin = min((v.co.z for v in vs if any(g.group in rf_i and g.weight>0.1 for g in v.groups)), default=9)
        if min(lmin, rmin) > 0.03: floats.append(f)
        zs.append((aw @ arm_ev.pose.bones[PREF+'Hips'].matrix).translation.z)
        for bn in CHK:
            q = arm_ev.pose.bones[bn].rotation_quaternion.copy()
            if bn in prev_q:
                a = q.rotation_difference(prev_q[bn]).angle
                max_step = max(max_step, math.degrees(a))
            prev_q[bn] = q
    amp = (max(zs)-min(zs))*100
    ok = amp > 1.0 and max_step < 45.0
    # 只有行走要求全程贴地; 跑/跳本来就有腾空相(与已验证旧版行为一致)
    if anim_name == 'Standard Walk': ok &= len(floats) == 0
    all_pass &= ok
    print(f"3) {anim_name}: {results[anim_name]['frames']}帧 Hips起伏{amp:.1f}cm 腾空{len(floats)}帧"
          f"{floats[:6] if floats else ''} 关键骨最大帧间转角{max_step:.1f}° {'PASS' if ok else 'FAIL'}")
assert all_pass, "自查未通过!"

# ========== 保存 ==========
walk = bpy.data.actions.get('Standard Walk')
arm.animation_data.action = walk
for s in walk.slots:
    try:
        arm.animation_data.action_slot = s
        break
    except RuntimeError:
        continue
scn.frame_start, scn.frame_end = results['Standard Walk']['range']
scn.frame_set(scn.frame_start)
bpy.ops.wm.save_mainfile(filepath=OUT)
# 清无关action
for a in list(bpy.data.actions):
    if a.name not in [n for n,_ in ANIMS]:
        try: bpy.data.actions.remove(a)
        except Exception: pass
bpy.ops.wm.save_mainfile()
final = [a.name for a in bpy.data.actions]
print(f"\n文件内动作: {final}")
print(f"场景对象: {[o.name for o in bpy.data.objects]}")
assert set(n for n,_ in ANIMS) <= set(final), "动作丢失!"
print(f"已保存: {OUT}")
print("========== RETARGET_DONE ==========")
