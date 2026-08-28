"""修复行走动画驱动 v3: Blender 5.x Slotted Action.
根因: F曲线在walk原始slot的channelbag里. 让rig直接复用该slot即可驱动(骨骼名一致)."""
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
print(f"walk原始slot: {walk_slot.name_display if walk_slot else None}")
print(f"slots总数: {len(action.slots)}")

# 核心: 把action绑到rig, 并复用walk的原始slot(F曲线所在)
if rig_arm.animation_data is None:
    rig_arm.animation_data_create()
rig_arm.animation_data.action = action
rig_arm.animation_data.action_slot = walk_slot
print(f"rig action_slot已绑定: {rig_arm.animation_data.action_slot}")

# 验证驱动
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()
hb1 = rig_arm.pose.bones['mixamorig:Hips'].matrix.copy()
bpy.context.scene.frame_set(20)
bpy.context.view_layer.update()
hb20 = rig_arm.pose.bones['mixamorig:Hips'].matrix.copy()
dloc = (hb20.translation - hb1.translation).length
drot = hb20.to_quaternion().rotation_difference(hb1.to_quaternion()).angle
print(f"Hips帧1→20: 位移{dloc*1000:.1f}mm, 旋转{drot:.3f}rad")

if dloc > 0.001 or drot > 0.01:
    print("结论: 行走动画驱动成功 ✓")
    # 删除多余行走骨架
    bpy.data.objects.remove(walk_arm, do_unlink=True)
    action_fr = action.frame_range
    bpy.context.scene.frame_start = int(action_fr[0])
    bpy.context.scene.frame_end = int(action_fr[1])
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print(f"保存: {OUT}")
else:
    print("结论: 动画仍未驱动 ✗")

print("SLOT_FIX3_DONE")
