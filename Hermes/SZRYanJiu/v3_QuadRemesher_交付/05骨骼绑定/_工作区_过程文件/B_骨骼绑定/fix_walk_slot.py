"""修复walk_test_手写版.blend: slot绑定指错(绑到空slot, 数据在另一个slot).
根因: animation_data.action_slot指向handle=929201143(OBwalk_rig_slot,空),
      而全部517条fcurves在handle=929201142(OBSlot)的channelbag里 → 动画不生效.
修复: action_slot指到有数据的slot + 删除Mixamo参考模型(用户要求动作在模型上不在参考上)."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\B_骨骼绑定\walk_test_手写版.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

out = []
rig = bpy.data.objects.get("MixamoSkeleton")
ad = rig.animation_data
act = ad.action

# 1) 找到装着fcurves的slot
data_slot = None
for slot in act.slots:
    n = 0
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                if bag.slot_handle == slot.handle:
                    n += len(bag.fcurves)
    if n > 0:
        data_slot = slot
        out.append(f"有数据的slot: {slot.identifier} (handle={slot.handle}, fcurves={n})")

# 2) 绑定到有数据的slot
ad.action_slot = data_slot
out.append(f"已改绑: action_slot → {data_slot.identifier}")

# 3) 播放验证: 帧1 vs 帧18 mesh变形
scn = bpy.context.scene
body = bpy.data.objects.get("tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR")

scn.frame_set(1)
bpy.context.view_layer.update()
base = [v.co.copy() for v in body.data.vertices[:3000]]

scn.frame_set(18)
bpy.context.view_layer.update()
moved = 0; maxd = 0.0
for i, v in enumerate(body.data.vertices[:3000]):
    d = (v.co - base[i]).length
    if d > 0.01: moved += 1
    if d > maxd: maxd = d
out.append(f"改绑后mesh变形: {moved}/3000 顶点>1cm, 最大 {maxd*100:.1f}cm")

# 4) 删除Mixamo参考模型(Alpha_Joints/Alpha_Surface/Armature)
del_names = [o.name for o in bpy.data.objects if o.name in ("Alpha_Joints", "Alpha_Surface", "Armature")]
for name in del_names:
    o = bpy.data.objects.get(name)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)
out.append(f"已删除参考模型: {del_names}")

# 5) 保存
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
out.append("已保存")

with open(r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\logs\walk_fix_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))