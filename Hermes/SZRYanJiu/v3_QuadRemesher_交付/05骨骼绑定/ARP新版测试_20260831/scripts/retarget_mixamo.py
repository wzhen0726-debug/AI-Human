"""04_动作测试.blend 生成: Mixamo动画绑定 (2026-09-04 用户方案第二步)

前提: 骨架rest朝向已归一化为Mixamo标准(先跑 normalize_rest.py, 产03_mixamo_rest.blend)。
归一化是测量驱动的(锚用户提供的T-Pose.fbx): 下个模型若rest本就标准, 差异≈0自动不改。

绑定方式: rest已一致, 直接复制参考动画的action(局部旋转通道精确生效),
只重建Hips垂直起伏通道(参考Hips世界z变化×实测腿长比, 写入数值探测出的垂直轴)。
帧范围完全按参考动画原始范围, 不铺周期/不加循环加工。
每个动画独立实测腿长比(参考骨架比例不同: Walk腿长0.893, Running/Jump 0.955)。

用法: blender -b --python scripts/retarget_mixamo.py  (需先跑normalize_rest.py)
"""
import bpy, os, math
from mathutils import Matrix, Vector, Quaternion

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831"
RIG = os.path.join(BASE, "03_mixamo_rest.blend")
ANIM_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件"
OUT = os.path.join(BASE, "04_动作测试.blend")
ANIMS = [("Standard Walk", "Standard Walk.fbx"), ("Running", "Running.fbx"), ("Jump", "Jump.fbx")]

def qdiff(a, b):
    b2 = b.copy()
    if a.dot(b2) < 0: b2.negate()
    return a.rotation_difference(b2).angle

def depth(pb):
    d, p = 0, pb
    while p.parent:
        d += 1; p = p.parent
    return d

# ---------- 打开归一化后骨架 ----------
bpy.ops.wm.open_mainfile(filepath=RIG)
arm = bpy.data.objects.get('MixamoSkeleton')
body = next(o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('tripo'))
for b in arm.data.bones:
    if not b.name.startswith("mixamorig:"): b.name = "mixamorig:" + b.name
for vg in body.vertex_groups:
    if not vg.name.startswith("mixamorig:"): vg.name = "mixamorig:" + vg.name
if arm.animation_data: arm.animation_data_clear()
ours_sorted = sorted(arm.pose.bones, key=depth)
dg = bpy.context.evaluated_depsgraph_get()
vs_before = [v.co.copy() for v in body.evaluated_get(dg).data.vertices]  # rest外观快照
keep = {arm.name, body.name, 'Eye002_L', 'Eye002_R'}

# Hips垂直轴探测(动画绑定前做一次, 此时无action干扰; 骨架不变轴不变)
def ev_hips_z():
    bpy.context.view_layer.update()
    return (arm.matrix_world @ arm.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones['mixamorig:Hips'].matrix).translation.z
pb_h = arm.pose.bones['mixamorig:Hips']
z0 = ev_hips_z()
dz_vals = []
for idx, axis in enumerate([Vector((1,0,0)), Vector((0,1,0)), Vector((0,0,1))]):
    pb_h.location = axis
    dz_vals.append(round(ev_hips_z() - z0, 4))
    pb_h.location = Vector((0,0,0))
best = max(range(3), key=lambda i: abs(dz_vals[i]))
print(f"Hips垂直轴探测(无动画干扰): dz={dz_vals} -> 轴{best}")
if abs(dz_vals[best]) < 0.9:
    raise AssertionError(f"找不到Hips垂直轴! dz={dz_vals}")
z_axis = best

# ========== 阶段B: 逐动画绑定(直接复制action, rest已一致) ==========
results = {}
for anim_name, fname in ANIMS:
    print(f"\n{'='*50}\n动画: {anim_name} ({fname})")
    bpy.ops.import_scene.fbx(filepath=os.path.join(ANIM_DIR, fname))
    refa = next(o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm and o.animation_data)
    assert refa, f"{anim_name} FBX导入失败"
    wm_ref = refa.matrix_world

    # 腿长比实测(每个动画的参考骨架比例不同)
    ref_hips_z = (wm_ref @ refa.data.bones['mixamorig:Hips'].head_local).z
    ref_foot_z = (wm_ref @ refa.data.bones['mixamorig:LeftFoot'].head_local).z
    our_hips_z2 = (arm.matrix_world @ arm.data.bones['mixamorig:Hips'].head_local).z
    our_foot_z2 = (arm.matrix_world @ arm.data.bones['mixamorig:LeftFoot'].head_local).z
    leg_ratio = (our_hips_z2 - our_foot_z2) / (ref_hips_z - ref_foot_z)

    # 复制参考action绑定(rest已一致, 旋转通道直接生效)
    ref_act = refa.animation_data.action
    rig_act = ref_act.copy()
    rig_act.name = anim_name
    rig_act.use_fake_user = True
    rig_act.use_frame_range = True  # 切换动作时场景帧范围跟随动作
    fstart, fend = int(ref_act.frame_range[0]), int(ref_act.frame_range[1])
    if arm.animation_data is None: arm.animation_data_create()
    arm.animation_data.action = rig_act
    slot = None
    for layer in rig_act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                if len(bag.fcurves) > 0:
                    for s in rig_act.slots:
                        if s.handle == bag.slot_handle: slot = s
                if slot: break
            if slot: break
        if slot: break
    if slot: arm.animation_data.action_slot = slot

    # 重建Hips垂直起伏通道(参考动画的Hips水平位移是原地的, 只保留垂直)
    for layer in rig_act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in list(bag.fcurves):
                    if 'mixamorig:Hips' in fc.data_path and 'location' in fc.data_path:
                        bag.fcurves.remove(fc)
    # 数值探测的垂直轴已在动画绑定前确定(此处无action干扰时探测才准确)
    ref_dg = bpy.context.evaluated_depsgraph_get()
    for f in range(fstart, fend + 1):
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        ref_z = (wm_ref @ refa.evaluated_get(ref_dg).pose.bones['mixamorig:Hips'].matrix).translation.z
        loc = Vector((0,0,0)); loc[z_axis] = (ref_z - ref_hips_z) * leg_ratio
        pb_h.location = loc
        pb_h.keyframe_insert('location', frame=f)

    # 清参考残留
    for o in list(bpy.data.objects):
        if o.name not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    results[anim_name] = {"range": (fstart, fend), "frames": fend-fstart+1, "leg_ratio": leg_ratio}
    print(f"  绑定完成: 帧{fstart}-{fend} ({fend-fstart+1}帧, 与参考一致) 腿长比{leg_ratio:.3f}")

# ========== 阶段C: 自查 ==========
scn = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
lf_i = {g.index for g in body.vertex_groups if 'LeftFoot' in g.name or 'LeftToe' in g.name}
rf_i = {g.index for g in body.vertex_groups if 'RightFoot' in g.name or 'RightToe' in g.name}
print("\n" + "="*50 + "\n自查")
all_pass = True
for anim_name, fname in ANIMS:
    arm.animation_data.action = bpy.data.actions[anim_name]
    fstart, fend = results[anim_name]['range']
    floats, sole_min, zs = [], [], []
    for f in range(fstart, fend + 1):
        scn.frame_set(f); bpy.context.view_layer.update()
        vs = body.evaluated_get(dg).data.vertices
        lmin = min((v.co.z for v in vs if any(g.group in lf_i and g.weight>0.1 for g in v.groups)), default=9)
        rmin = min((v.co.z for v in vs if any(g.group in rf_i and g.weight>0.1 for g in v.groups)), default=9)
        sole_min.append(min(lmin, rmin))
        if min(lmin, rmin) > 0.03: floats.append(f)
        zs.append((arm.matrix_world @ arm.evaluated_get(dg).pose.bones['mixamorig:Hips'].matrix).translation.z)
    amp = (max(zs)-min(zs))*100
    ok = amp > 1.0
    all_pass &= ok
    print(f"  {anim_name}: {results[anim_name]['frames']}帧 Hips起伏{amp:.1f}cm "
          f"腾空{len(floats)}帧{floats[:6] if floats else ''} 脚底最低{min(sole_min)*100:.1f}cm {'PASS' if ok else 'FAIL'}")
assert all_pass, "自查未通过!"

# ========== 保存 ==========
walk = bpy.data.actions.get('Standard Walk')
arm.animation_data.action = walk
scn.frame_start, scn.frame_end = results['Standard Walk']['range']
print(f"\n文件内动作: {[a.name for a in bpy.data.actions]}")
bpy.ops.wm.save_mainfile(filepath=OUT)
for a in list(bpy.data.actions):
    if a.name.startswith('Armature|'):
        bpy.data.actions.remove(a)
bpy.ops.wm.save_mainfile()
final = [a.name for a in bpy.data.actions]
objs = [o.name for o in bpy.data.objects]
print(f"清理后动作: {final}")
print(f"场景对象: {objs}")
assert set(n for n,_ in ANIMS) <= set(final), "动作丢失!"
print(f"已保存: {OUT}")
print("========== RETARGET_DONE ==========")
