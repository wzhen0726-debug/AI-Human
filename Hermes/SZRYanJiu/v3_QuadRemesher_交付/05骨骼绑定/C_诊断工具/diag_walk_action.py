"""诊断Walk_noroot action内部结构: slots/channelbag归属/数据路径是否对得上骨骼."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\B_骨骼绑定\walk_test_手写版.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

rig = bpy.data.objects.get("MixamoSkeleton")
ad = rig.animation_data
act = ad.action
slot = ad.action_slot
out = []

out.append(f"action: {act.name}")
out.append(f"绑定的slot: id={slot.identifier if slot else None}, handle={slot.handle if slot else None}")
out.append(f"action里的全部slots: {[(s.identifier, s.handle) for s in act.slots]}")
out.append("")

for li, layer in enumerate(act.layers):
    for si, strip in enumerate(layer.strips):
        out.append(f"layer[{li}] strip[{si}] type={strip.type}")
        for bag in strip.channelbags:
            fcs = bag.fcurves
            paths = set()
            for fc in fcs:
                paths.add(fc.data_path.split('"')[1] if '"' in fc.data_path else fc.data_path)
            out.append(f"  channelbag: slot_handle={bag.slot_handle if hasattr(bag,'slot_handle') else '?'}, fcurves={len(fcs)}")
            out.append(f"  数据路径骨骼名(前5): {sorted(paths)[:5]}")
            out.append(f"  路径总数: {len(paths)}")

# 对照: 骨架里实际存在的骨骼名
bone_names = set(rig.data.bones.keys())
out.append("")
# 重新取路径集合
all_paths = set()
for layer in act.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for fc in bag.fcurves:
                if '"' in fc.data_path:
                    all_paths.add(fc.data_path.split('"')[1])
missing = [p for p in all_paths if p not in bone_names]
out.append(f"动画引用的骨骼数: {len(all_paths)}, 其中骨架里不存在的: {len(missing)}")
if missing: out.append(f"  不存在的(前10): {missing[:10]}")

with open(r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\logs\walk_action_struct.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))