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
# 2026-09-09: 输入改为03B(骨骼标准化版). rest已对齐Mixamo T-Pose(55骨朝向差max=0.0003°),
#   所以 C=R_our^-1@R_ref→单位矩阵, 下面的增量公式直接等价于绝对朝向匹配 —
#   且不会重演v2的内八/猫步(v2病根是"骨骼扳竖直但网格没动"运行时蒙皮硬挤;
#   03B是rest层面骨骼与网格一起重摆, 始终匹配).
RIG = os.path.join(BASE, "03B_骨骼标准化.blend")
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

# Hips位移雅可比探测(动画绑定前, 无action干扰): 局部轴 → 世界位移的3x3映射
# 上一版只探测"哪个局部轴对应世界Z", 然后只搬运垂直起伏 → 丢弃参考Hips的左右/前后重心移动
# (实测参考Walk的Hips x摆幅41.6mm y摆幅57.0mm, 我们0.0mm). 后果: 参考靠Hips侧移把落地脚
# 保持在离中线57mm, 我们Hips不动→落地脚收到9.6mm = **猫步**. 之前v3靠8°外八rest撑住掩盖了它,
# 03B把腿摆直后暴露.
def ev_hips_pos():
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    return (aw @ arm.evaluated_get(dg).pose.bones[PREF+'Hips'].matrix).translation.copy()
pb_h = arm.pose.bones[PREF+'Hips']
p0 = ev_hips_pos()
J = []            # J[j] = 局部轴j单位位移 → 世界位移向量
for axis in [Vector((1,0,0)), Vector((0,1,0)), Vector((0,0,1))]:
    pb_h.location = axis
    J.append(ev_hips_pos() - p0)
    pb_h.location = Vector((0,0,0))
Jm = Matrix((*J,)).transposed()          # 列=各局部轴的世界响应
print(f"Hips位移雅可比(局部轴→世界): x轴={tuple(round(v,4) for v in J[0])} "
      f"y轴={tuple(round(v,4) for v in J[1])} z轴={tuple(round(v,4) for v in J[2])}")
det = Jm.determinant()
print(f"  det={det:.6f} {'(可逆✓)' if abs(det) > 1e-6 else '(不可逆✗)'}")
assert abs(det) > 1e-6, f"Hips雅可比不可逆, 无法搬运位移! det={det} J={J}"
Jinv = Jm.inverted()
# 垂直轴仍记录(供日志/自查参考)
z_axis = max(range(3), key=lambda i: abs(J[i].z))
assert abs(J[z_axis].z) > 0.9, f"找不到Hips垂直轴! J={J}"
print(f"  垂直轴=局部{z_axis} (世界z响应={J[z_axis].z:.4f})")

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
    ref_hips_rest = (wm_ref @ rb[PREF+'Hips'].head_local).copy()      # 完整3D基准(不只z)
    ref_hips_z = ref_hips_rest.z
    ref_foot_z = (wm_ref @ rb[PREF+'LeftFoot'].head_local).z
    leg_ratio = (our_hips_z - our_foot_z) / (ref_hips_z - ref_foot_z)
    # 骨盆宽比: 左右侧移量按骨盆宽缩放(不是腿长比!). 我们骨盆比参考窄,
    # 用腿长比会把Hips侧移搬过头 → 落地脚被拉向中线 → R腿着地踝只剩24.2mm.
    ref_upleg_x = abs((wm_ref @ rb[PREF+'LeftUpLeg'].head_local).x)
    our_upleg_x = abs((aw @ arm.data.bones[PREF+'LeftUpLeg'].matrix_local).translation.x)
    hip_ratio = our_upleg_x / ref_upleg_x if ref_upleg_x > 1e-9 else leg_ratio
    print(f"  腿长比={leg_ratio:.4f} 骨盆宽比={hip_ratio:.4f} (我们UpLeg|x|={our_upleg_x*1000:.1f}mm 参考={ref_upleg_x*1000:.1f}mm)")

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
    ref_ankle = {'Left': [], 'Right': []}   # 参考踝世界(x,z)逐帧, 用于推导判据基准(不硬编码阈值)
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
        # Hips位移: 完整三轴搬运(垂直起伏 + 左右重心侧移 + 前后推进)
        # ⚠不能只搬z: 参考Walk的Hips x摆幅41.6mm/y摆幅57.0mm是**重心侧移**, 正是它把落地脚
        #   保持在离中线57mm. 只搬z → 我们Hips x/y摆幅0.0mm → 落地脚收到9.6mm = 猫步.
        #   实测三动画的Hips首末差均=0.00%(纯周期摆动walk-in-place), 所以完整搬运不会让角色飘走.
        ref_p = (wm_ref @ ref_ev.pose.bones[PREF+'Hips'].matrix).translation
        d_world = ref_p - ref_hips_rest
        # 分轴缩放: 左右侧移按骨盆宽比, 垂直/前后按腿长比
        d_scaled = Vector((d_world.x * hip_ratio, d_world.y * leg_ratio, d_world.z * leg_ratio))
        pb_h.location = Jinv @ d_scaled                      # 世界→局部(雅可比逆变换)
        pb_h.keyframe_insert('location', frame=f)
        # 参考踝世界位置(用于推导"参考自己的着地踝离中线" — 判据基准, 不硬编码阈值)
        for side in ('Left', 'Right'):
            rb_ = ref_ev.pose.bones.get(PREF+side+'Foot')
            if rb_ is not None:
                p = (wm_ref @ rb_.matrix).translation
                ref_ankle[side].append((p.x, p.z))
        if f == fstart or f == fend:
            print(f"  帧{f}: 已写{len(mapped)}骨")

    # 清参考残留
    for o in list(bpy.data.objects):
        if o.name not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    results[anim_name] = {"range": (fstart, fend), "frames": fend-fstart+1,
                          "leg_ratio": leg_ratio, "hip_ratio": hip_ratio,
                          "n_mapped": len(mapped), "ref_ankle": ref_ankle}
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
    ankle_x = {'L': [], 'R': []}     # 着地相踝离中线|x|(猫步判据)
    for f in range(fstart, fend + 1):
        scn.frame_set(f); bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        arm_ev = arm.evaluated_get(dg)
        vs = body.evaluated_get(dg).data.vertices
        lmin = min((v.co.z for v in vs if any(g.group in lf_i and g.weight>0.1 for g in v.groups)), default=9)
        rmin = min((v.co.z for v in vs if any(g.group in rf_i and g.weight>0.1 for g in v.groups)), default=9)
        if min(lmin, rmin) > 0.03: floats.append(f)
        zs.append((aw @ arm_ev.pose.bones[PREF+'Hips'].matrix).translation.z)
        # 踝世界x(着地相才计入猫步判据 — 摆动相脚收向中线是正常的)
        for side, foot_z in (('L', lmin), ('R', rmin)):
            if foot_z < 0.03:                        # 该脚着地
                ax = (aw @ arm_ev.pose.bones[PREF+('Left' if side=='L' else 'Right')+'Foot'].matrix).translation.x
                ankle_x[side].append(abs(ax) * 1000)
        for bn in CHK:
            q = arm_ev.pose.bones[bn].rotation_quaternion.copy()
            if bn in prev_q:
                a = q.rotation_difference(prev_q[bn]).angle
                max_step = max(max_step, math.degrees(a))
            prev_q[bn] = q
    amp = (max(zs)-min(zs))*100
    ok = amp > 1.0 and max_step < 45.0
    # 只有行走要求全程贴地; 跑/跳本来就有腾空相(与已验证旧版行为一致)
    if anim_name == 'Standard Walk':
        ok &= len(floats) == 0
        # ⚠猫步判据(用户最关心项): 着地相踝离中线不能太小.
        #   旧版只搬Hips垂直z → 丢弃参考的左右重心侧移(实测Hips x摆幅41.6mm) →
        #   落地脚被收到离中线9.6mm = T台猫步. 修复(完整三轴搬运+骨盆宽比缩放)后达46.4mm.
        # ⚠阈值不能硬编码: 参考自身这个walk左右不对称, R腿着地踝min仅31.1mm(L腿56.5mm).
        #   照搬参考行为时R腿本就该≈31.1×骨盆宽比. 所以基准从**参考实测**推导:
        #   阈值 = 参考同侧着地踝min × 骨盆宽比 × 0.75(容忍LBS/体型差异的安全系数).
        ra = results[anim_name].get('ref_ankle', {})
        hr = results[anim_name].get('hip_ratio', 1.0)
        for side, ref_side in (('L', 'Left'), ('R', 'Right')):
            if not ankle_x[side]: continue
            amin = min(ankle_x[side])
            # 参考同侧"着地相"踝|x|最小值.
            # ⚠着地判据不能用绝对z<0.03(那是脚部**顶点**的地面接触阈值; 踝**骨**在~105mm高处,
            #   永远不<0.03 → 会一个着地帧都匹配不到, 误退兜底阈值). 踝骨z在脚着地时最低,
            #   所以用"踝骨z 相对该侧周期最低点 <40mm"判着地(参考网格已删, 只能骨相对判).
            rp_all = ra.get(ref_side, [])
            rp = []
            if rp_all:
                zmin = min(z for _, z in rp_all)
                rp = [abs(x) * 1000 for x, z in rp_all if z - zmin < 0.04]
            if rp:
                thresh = min(rp) * hr * 0.75
                src = f"参考{ref_side}着地踝min={min(rp):.1f}×骨盆比{hr:.3f}×0.75"
            else:
                thresh, src = 25.0, "参考无着地数据→兜底25mm"
            flag = "✓" if amin >= thresh else "✗猫步"
            print(f"   {side}腿着地踝: min={amin:.1f}mm 阈值={thresh:.1f}mm ({src}) {flag}")
            if amin < thresh: ok = False
    all_pass &= ok
    _ax = {s: (f"min{min(v):.0f}/均{sum(v)/len(v):.0f}" if v else "无") for s, v in ankle_x.items()}
    print(f"3) {anim_name}: {results[anim_name]['frames']}帧 Hips起伏{amp:.1f}cm 腾空{len(floats)}帧"
          f"{floats[:6] if floats else ''} 关键骨最大帧间转角{max_step:.1f}° "
          f"着地踝x[L{_ax['L']} R{_ax['R']}]mm {'PASS' if ok else 'FAIL'}")
import os as _os
if not all_pass:
    if _os.environ.get("RT_SAVE_ANYWAY") == "1":
        print("⚠自查未通过, 但RT_SAVE_ANYWAY=1 → 继续保存供诊断")
    else:
        assert False, "自查未通过!"

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
