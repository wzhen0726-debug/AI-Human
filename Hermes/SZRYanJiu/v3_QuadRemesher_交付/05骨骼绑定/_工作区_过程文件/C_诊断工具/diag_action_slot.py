"""诊断4: Blender 5.x action slot结构, 找出动画不驱动的原因."""
import bpy, os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
BLEND = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "07_走动画测试.blend")
bpy.ops.wm.open_mainfile(filepath=BLEND)

rig_arm = None
walk_arm = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        if o.name == 'rig': rig_arm = o
        else: walk_arm = o

print(f"walk_arm.animation_data.action_slot: {walk_arm.animation_data.action_slot}")
print(f"rig_arm.animation_data.action_slot: {rig_arm.animation_data.action_slot}")

action = rig_arm.animation_data.action
for i, slot in enumerate(action.slots):
    print(f"Slot {i}: name={slot.name}, target_id={slot.target_id}, id_type={slot.target_id.id_type if hasattr(slot.target_id,'id_type') else '?'}")
print("DIAG4_DONE")
