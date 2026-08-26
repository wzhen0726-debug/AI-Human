"""检查walk_test_ARP版.blend的slot绑定状态."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\B_骨骼绑定\walk_test_ARP版.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

rig = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        rig = o
        break

if not rig:
    print("无骨架")
    raise SystemExit(1)

ad = rig.animation_data
if not ad or not ad.action:
    print("无动画数据")
    raise SystemExit(1)

act = ad.action
slot = ad.action_slot

print(f"ACTION_NAME={act.name}")
print(f"SLOT_TYPE={type(slot).__name__ if slot else 'NONE'}")
print(f"SLOT_NAME={slot.name if slot else 'NONE'}")
print(f"SLOT_ID={slot.identifier if slot else 'NONE'}")

# 检查这个slot属于哪个action
for s in act.slots:
    print(f"SLOT_IN_ACTION: name={s.name} id={s.identifier}")

# 检查Hips骨骼是否真的动
if 'mixamorig:Hips' in rig.pose.bones:
    pb = rig.pose.bones['mixamorig:Hips']
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    m1 = pb.matrix.copy()
    bpy.context.scene.frame_set(20)
    bpy.context.view_layer.update()
    m2 = pb.matrix.copy()
    diff = (m1.to_translation() - m2.to_translation()).length
    print(f"HIPS_FRAME1={tuple(round(v,3) for v in m1.to_translation())}")
    print(f"HIPS_FRAME20={tuple(round(v,3) for v in m2.to_translation())}")
    print(f"HIPS_DIFF={diff:.6f}m")

print("SLOT_CHECK_DONE")
