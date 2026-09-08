# -*- coding: utf-8 -*-
"""05重定向金标准验证(v3标准, 2026-09-08).

v3不再要求"绝对世界朝向==Mixamo参考"(那会把我们岔开的腿扳成Mixamo垂直腿→内八猫步).
新金标准三条:
  ① 增量一致: 我们骨骼的世界旋转增量 == 参考的世界旋转增量(动作被正确搬运)
     定义 D_b(t) = R_rest_b^-1 @ W_b(t), 比较 D_ours vs D_ref 夹角
  ② rest保持: 第1帧(rest附近)我们的姿态 = 我们自己的rest, 不是参考的rest
     比较 R_our_rest vs R_ref_rest 夹角应≈我们原本的站姿差(大腿外展~8°, 不是0°)
  ③ 内八检查: 大腿外展角/脚掌yaw/踝离中线 应保持我们自己的比例
     (我们外展8.18° 踝±143mm; Mixamo外展0.35° 踝±91mm)
"""
import bpy, os, math
import numpy as np
from mathutils import Vector, Quaternion

B05 = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付\05骨骼绑定\ARP新版测试_20260831"
ANIM_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\原始文件\Mixamo动画文件"
P = "mixamorig:"
BONE_Y = Vector((0, 1, 0))

def act_frames(act):
    ks = []
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for kp in fc.keyframe_points:
                        ks.append(kp.co.x)
    if ks: return int(round(min(ks))), int(round(max(ks)))
    fr = act.frame_range; return int(fr[0]), int(fr[1])

def bind(arm, act):
    arm.animation_data.action = act
    for s in act.slots:
        try:
            arm.animation_data.action_slot = s; return
        except RuntimeError: continue

# ---- 打开我们的04 ----
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(B05, "04_动作测试.blend"))
arm = bpy.data.objects['MixamoSkeleton']
aw = arm.matrix_world
R_our_rest = {b.name: (aw @ b.matrix_local).to_quaternion() for b in arm.data.bones}
our_act = bpy.data.actions['Standard Walk']
assert our_act, "04里没有Standard Walk动作!"

# ---- 导入参考 ----
bpy.ops.import_scene.fbx(filepath=os.path.join(ANIM_DIR, "Standard Walk.fbx"))
ref = next(o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm and o.animation_data)
wm = ref.matrix_world
R_ref_rest = {b.name: (wm @ b.matrix_local).to_quaternion() for b in ref.data.bones}
ract = ref.animation_data.action
assert our_act != ract, "action共享污染! 两边读到同一动作会得到假阳性"
bind(arm, our_act); bind(ref, ract)
f0, f1 = act_frames(our_act)
rf0, rf1 = act_frames(ract)
print(f"帧范围: 我们={f0}-{f1} 参考={rf0}-{rf1}")
assert (f0, f1) == (rf0, rf1), f"帧范围不一致!"

CHK = [P+n for n in ('LeftUpLeg','LeftLeg','LeftFoot','RightUpLeg','RightLeg','RightFoot',
                     'LeftArm','LeftForeArm','RightArm','RightForeArm','Spine','Spine1','Spine2','Head')]

# ========== ① 增量一致 ==========
worst = (0.0, '', 0)
per = {}
for f in range(f0, f1+1):
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    oe = arm.evaluated_get(dg); re = ref.evaluated_get(dg)
    for bn in CHK:
        Wo = (aw @ oe.pose.bones[bn].matrix).to_quaternion()
        Wr = (wm @ re.pose.bones[bn].matrix).to_quaternion()
        Do = R_our_rest[bn].inverted() @ Wo
        Dr = R_ref_rest[bn].inverted() @ Wr
        if Do.dot(Dr) < 0: Dr.negate()
        a = math.degrees(Do.rotation_difference(Dr).angle)
        per.setdefault(bn, []).append(a)
        if a > worst[0]: worst = (a, bn, f)
print("\n① 世界旋转增量一致性(我们 vs 参考, 应≈0):")
for bn in CHK:
    v = per[bn]
    print(f"   {bn:<26} max={max(v):.3f}° avg={sum(v)/len(v):.3f}°")
ok1 = worst[0] < 2.0
print(f"   最差 {worst[0]:.3f}° ({worst[1]} 帧{worst[2]}) → {'PASS' if ok1 else 'FAIL'}")

# ========== ② rest保持(不该变成Mixamo的站姿) ==========
print("\n② rest朝向差(应≠0 — 我们是岔开腿, Mixamo是垂直腿):")
rest_diff = {}
for bn in [P+'LeftUpLeg', P+'RightUpLeg', P+'LeftFoot', P+'RightFoot', P+'Hips', P+'Spine']:
    a = R_our_rest[bn].rotation_difference(R_ref_rest[bn]).angle
    rest_diff[bn] = math.degrees(a)
    print(f"   {bn:<26} {math.degrees(a):.2f}°")
leg_diff = (rest_diff[P+'LeftUpLeg'] + rest_diff[P+'RightUpLeg'])/2
ok2 = leg_diff > 3.0
print(f"   大腿rest朝向差均值={leg_diff:.2f}° → {'PASS(保留了自己站姿)' if ok2 else 'FAIL(被扳成Mixamo站姿=会内八)'}")

# ========== ③ 内八检查: 外展/踝间距 ==========
def splay_yaw(arm, bn, sg, f):
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    pb = arm.evaluated_get(dg).pose.bones[bn]
    d = (arm.matrix_world.to_3x3() @ (pb.matrix.to_3x3() @ BONE_Y)).normalized()
    az = math.degrees(math.atan2(-sg*d.x, -d.z))
    yaw = math.degrees(math.atan2(sg*d.x, -d.y))
    fx = (arm.matrix_world @ pb.head).x * 1000
    return az, yaw, fx

print("\n③ 行走全周期 外展/踝x — 判据: 外展角全程同号且不跨0(跨0=腿摆到垂直/内收=内八):")
ok3 = True
for side, sg in (("Left", +1), ("Right", -1)):
    azs, yaws, fxs = [], [], []
    for f in range(f0, f1+1):
        az, yaw, fx = splay_yaw(arm, P+side+'UpLeg', sg, f)
        _, yf, _ = splay_yaw(arm, P+side+'Foot', sg, f)
        azs.append(az); yaws.append(yf); fxs.append(fx)
    az_min, az_max, az_avg = min(azs), max(azs), float(np.mean(azs))
    # 同号判定: min/max同号 = 全程外展(或全程内收), 未跨过垂直位
    crosses_zero = (az_min < 0 < az_max)
    rest_az = math.degrees(R_our_rest[P+side+'UpLeg'].rotation_difference(R_ref_rest[P+side+'UpLeg']).angle)
    print(f"   {side}大腿外展: 范围[{az_min:+.2f},{az_max:+.2f}]° avg={az_avg:+.2f}° "
          f"跨0={'是⚠' if crosses_zero else '否'}")
    print(f"   {side}踝离中线: 最小={min(abs(x) for x in fxs):.1f}mm 范围[{min(fxs):+.1f},{max(fxs):+.1f}]mm")
    # 判据1: 不跨0(腿始终保持外展方向, 不摆到垂直/内收)
    if crosses_zero:
        print(f"     ⚠ 外展角跨越0° → 腿在周期中被摆到垂直/内收 = 内八倾向"); ok3 = False
    # 判据2: 平均外展幅度接近我们rest(rest幅度按与Mixamo的差衡量, 我们腿更岔开)
    if abs(az_avg) < 3.0:
        print(f"     ⚠ 平均外展仅{az_avg:+.2f}°(<3°) → 接近Mixamo垂直腿"); ok3 = False
    # 判据3: 踝不跨中线(猫步特征)
    if min(abs(x) for x in fxs) < 50:
        print(f"     ⚠ 踝离中线仅{min(abs(x) for x in fxs):.1f}mm(<50) → 猫步倾向"); ok3 = False
    if not (crosses_zero or abs(az_avg)<3.0 or min(abs(x) for x in fxs)<50):
        print(f"     ✓ 全程保持外展{az_avg:+.1f}° · 踝间距≥{min(abs(x) for x in fxs):.0f}mm · 无内八/猫步")
print(f"   → {'PASS' if ok3 else 'FAIL'}")

print("\n" + "="*60)
print(f"总判定: ①增量{ok1} ②rest{ok2} ③内八{ok3} → {'ALL PASS' if (ok1 and ok2 and ok3) else 'FAIL'}")
print("VERIFY_V3_DONE")
