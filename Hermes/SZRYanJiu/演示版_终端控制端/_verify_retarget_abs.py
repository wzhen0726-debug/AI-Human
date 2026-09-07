# -*- coding: utf-8 -*-
"""金标准验证v3(绝对朝向): 新04每骨世界朝向 W_our(t) 与参考 W_ref(t) 逐帧夹角应≈0."""
import bpy, os, math

B05 = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付\05骨骼绑定\ARP新版测试_20260831"
ANIM = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\原始文件\Mixamo动画文件\Standard Walk.fbx"
bpy.ops.wm.open_mainfile(filepath=os.path.join(B05, "04_动作测试.blend"))
arm = bpy.data.objects['MixamoSkeleton']
aw = arm.matrix_world
our_act = bpy.data.actions['Standard Walk']

bpy.ops.import_scene.fbx(filepath=ANIM)
refa = next(o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm and o.animation_data)
# 防污染: 两骨架各绑各的action
assert our_act != refa.animation_data.action, "action是同一对象, 会被污染!"
arm.animation_data.action = our_act
for s in our_act.slots:
    try:
        arm.animation_data.action_slot = s; break
    except RuntimeError: continue
wm = refa.matrix_world

CHK = ['mixamorig:'+n for n in ('LeftUpLeg','LeftLeg','LeftFoot','RightUpLeg','RightLeg','RightFoot',
                                'LeftArm','LeftForeArm','RightArm','RightForeArm','Spine','Spine1','Spine2','Head')]
worst = (0, '', 0)
per_bone = {}
for f in range(1, 37):
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    our_ev = arm.evaluated_get(dg); ref_ev = refa.evaluated_get(dg)
    for bn in CHK:
        Wo = (aw @ our_ev.pose.bones[bn].matrix).to_quaternion()
        Wr = (wm @ ref_ev.pose.bones[bn].matrix).to_quaternion()
        if Wo.dot(Wr) < 0: Wr.negate()
        a = math.degrees(Wo.rotation_difference(Wr).angle)
        per_bone.setdefault(bn, []).append(a)
        if a > worst[0]: worst = (a, bn, f)
print("绝对世界朝向对比(Walk 36帧 × 14骨):")
for bn in CHK:
    v = per_bone[bn]
    print(f"  {bn:<28} max={max(v):.3f}° avg={sum(v)/len(v):.3f}°")
print(f"最差: {worst[0]:.3f}° ({worst[1]} 帧{worst[2]})")
# 参考真的在动?
bpy.context.scene.frame_set(1); bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
q1 = (wm @ refa.evaluated_get(dg).pose.bones['mixamorig:LeftUpLeg'].matrix).to_quaternion()
bpy.context.scene.frame_set(18); bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
q2 = (wm @ refa.evaluated_get(dg).pose.bones['mixamorig:LeftUpLeg'].matrix).to_quaternion()
print(f"参考LeftUpLeg f1vsf18世界朝向差: {math.degrees(q1.rotation_difference(q2).angle):.2f}° (应>1°)")
print("VERIFY_ABS " + ("PASS" if worst[0] < 2.0 else "FAIL"))
