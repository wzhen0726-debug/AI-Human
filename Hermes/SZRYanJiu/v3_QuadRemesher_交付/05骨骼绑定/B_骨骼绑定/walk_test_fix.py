"""修复行走动画: 去掉Hips位移(根动作), 只保留旋转, 原地播放走路循环.
根因: Mixamo动画的Hips location是全局坐标(走路位移), 覆盖到不同骨架导致飞走."""
import bpy, os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
WALK_FBX = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx"
RIG = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.blend")
OUT = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "07_走动画测试.blend")

bpy.ops.wm.open_mainfile(filepath=RIG)

rig_arm = None
body = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE' and o.name == 'rig':
        rig_arm = o
    elif o.type == 'MESH' and len(o.vertex_groups) > 0:
        body = o

# 导入行走动画
bpy.ops.import_scene.fbx(filepath=WALK_FBX)

walk_arm = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE' and o.name != 'rig' and o.animation_data and o.animation_data.action:
        walk_arm = o

action = walk_arm.animation_data.action
walk_slot = walk_arm.animation_data.action_slot
print(f"行走action: {action.name}")

# 复制action供我们的rig使用(避免污染原动画)
import copy
rig_action = action.copy()
rig_action.name = "Walk_Cycle_rig"
print(f"复制为: {rig_action.name}")

# 去掉Hips的location F曲线(根动作位移)
strip = rig_action.layers[0].strips[0]
slot0 = rig_action.slots[0]
cb = strip.channelbag(slot0)
if cb:
    removed = 0
    for fc in list(cb.fcurves):
        # 只删Hips的location(保留rotation)
        if 'mixamorig:Hips' in fc.data_path and 'location' in fc.data_path:
            cb.fcurves.remove(fc)
            removed += 1
    print(f"删除Hips位移F曲线: {removed}条")

# 绑定到rig
if rig_arm.animation_data is None:
    rig_arm.animation_data_create()
rig_arm.animation_data.action = rig_action
rig_arm.animation_data.action_slot = slot0
print(f"rig action_slot绑定: {rig_arm.animation_data.action_slot}")

# 验证: Hips应该基本不动(原地走路), 但其他骨骼旋转
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()
h1 = rig_arm.pose.bones['mixamorig:Hips'].matrix.copy()
bpy.context.scene.frame_set(20)
bpy.context.view_layer.update()
h20 = rig_arm.pose.bones['mixamorig:Hips'].matrix.copy()
dloc = (h20.translation - h1.translation).length
drot = h20.to_quaternion().rotation_difference(h1.to_quaternion()).angle
print(f"Hips帧1→20: 位移{dloc*1000:.1f}mm(应≈0), 旋转{drot:.3f}rad")

# 检查手臂是否在摆动(验证旋转驱动)
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()
la1 = rig_arm.pose.bones['mixamorig:LeftArm'].matrix.copy()
bpy.context.scene.frame_set(20)
bpy.context.view_layer.update()
la20 = rig_arm.pose.bones['mixamorig:LeftArm'].matrix.copy()
la_rot = la20.to_quaternion().rotation_difference(la1.to_quaternion()).angle
print(f"左臂帧1→20旋转: {la_rot:.3f}rad (应>0, 走路摆臂)")

if dloc < 0.1 and la_rot > 0.05:
    print("\n结论: 原地走路动画驱动成功 ✓")
    # 清理多余骨架
    bpy.data.objects.remove(walk_arm, do_unlink=True)
    # 设置帧范围
    bpy.context.scene.frame_start = int(action.frame_range[0])
    bpy.context.scene.frame_end = int(action.frame_range[1])
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print(f"保存: {OUT}")
else:
    print("\n结论: 仍有问题 ✗")

print("WALK_FIX_DONE")
