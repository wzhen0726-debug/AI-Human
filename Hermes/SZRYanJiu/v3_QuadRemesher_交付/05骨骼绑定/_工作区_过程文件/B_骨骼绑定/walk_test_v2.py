"""手写版行走动画测试 v2 (2026-08-27根因重写).
根因: 旧walk_test_fix.py打开的是ARP版rig(06_rig_arp_mixamo.blend)不是手写版!
      且slot绑定取slots[0]不一定是装fcurves的那个 → 交付文件里动画没驱动.
本脚本: 从修好的06_rig_final.blend出发 → 导入行走FBX → 复制action删Hips位移
        → slot绑到装数据的channelbag → 删参考模型 → 保存+验证."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
WALK_FBX = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx"
RIG = os.path.join(BASE, "B_骨骼绑定", "06_rig_final.blend")
OUT = os.path.join(BASE, "B_骨骼绑定", "walk_test_手写版.blend")
OUT2 = os.path.join(BASE, "B_骨骼绑定", "07_走动画测试.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)

rig_arm = bpy.data.objects.get("MixamoSkeleton")
assert rig_arm, "找不到MixamoSkeleton"

# 导入行走动画
bpy.ops.import_scene.fbx(filepath=WALK_FBX)
walk_arm = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE' and o.name != 'MixamoSkeleton' and o.animation_data and o.animation_data.action:
        walk_arm = o
assert walk_arm, "行走FBX没导入出骨架"

action = walk_arm.animation_data.action
print(f"行走action: {action.name}")

# 复制action
rig_action = action.copy()
rig_action.name = "Walk_noroot"

# 找装fcurves的slot + 删Hips位移曲线
data_slot = None
removed = 0
for layer in rig_action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            if len(bag.fcurves) > 0:
                data_slot = next((s for s in rig_action.slots if s.handle == bag.slot_handle), None)
                for fc in list(bag.fcurves):
                    if 'mixamorig:Hips' in fc.data_path and 'location' in fc.data_path:
                        bag.fcurves.remove(fc)
                        removed += 1
                break
assert data_slot, "action里没有装fcurves的slot"
print(f"数据slot: {data_slot.identifier}, 删除Hips位移曲线: {removed}条")

# 绑定到我们的骨架 — slot必须指到装数据的那个
if rig_arm.animation_data is None:
    rig_arm.animation_data_create()
rig_arm.animation_data.action = rig_action
rig_arm.animation_data.action_slot = data_slot
print(f"绑定: action={rig_action.name}, slot={data_slot.identifier}")

# 删除Mixamo参考对象(导入FBX带进来的)
del_names = [o.name for o in bpy.data.objects if o.name != 'MixamoSkeleton'
             and o.name not in ('tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR',)
             and not ('Eye' in o.name)]
for nm in del_names:
    o = bpy.data.objects.get(nm)
    if o and o.type in ('ARMATURE', 'MESH'):
        bpy.data.objects.remove(o, do_unlink=True)
print(f"删除参考对象: {del_names}")

# 帧范围
bpy.context.scene.frame_start = int(action.frame_range[0])
bpy.context.scene.frame_end = int(action.frame_range[1])

# ===== 验证(depsgraph求值, 不读原始mesh) =====
scn = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
body = bpy.data.objects.get("tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR")
body_ev = body.evaluated_get(dg)

scn.frame_set(1); bpy.context.view_layer.update()
base = [v.co.copy() for v in body_ev.data.vertices[:3000]]
lh1 = (rig_arm.matrix_world @ rig_arm.pose.bones['mixamorig:LeftHand'].matrix).translation.copy()

scn.frame_set(18); bpy.context.view_layer.update()
moved = sum(1 for i, v in enumerate(body_ev.data.vertices[:3000]) if (v.co - base[i]).length > 0.01)
lh18 = (rig_arm.matrix_world @ rig_arm.pose.bones['mixamorig:LeftHand'].matrix).translation.copy()
rf18 = (rig_arm.matrix_world @ rig_arm.pose.bones['mixamorig:RightFoot'].matrix).translation.copy()

print(f"mesh变形: {moved}/3000 顶点>1cm")
print(f"帧18左手: z={lh18.z:.3f} (T-pose手z≈1.44; 走路摆臂应≈1.2-1.6, 不应举头顶>1.8)")
print(f"帧18左手位移: {(lh18-lh1).length*100:.1f}cm (应>2cm摆臂)")
print(f"帧18右脚: z={rf18.z:.3f} (应贴地0.0-0.3)")

ok = moved > 500 and lh18.z < 1.8 and (lh18-lh1).length > 0.02 and rf18.z < 0.4
print(f"\n结论: {'✓ 通过' if ok else '✗ 仍有问题'}")

if ok:
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    bpy.ops.wm.save_as_mainfile(filepath=OUT2)
    print(f"保存: {OUT}")
    print(f"保存: {OUT2}")
print("WALK_V2_DONE")