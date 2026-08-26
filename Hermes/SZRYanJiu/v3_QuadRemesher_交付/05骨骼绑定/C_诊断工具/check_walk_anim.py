"""检查walk_test_手写版.blend: 动画在哪个骨架上(Blender 5.x Slotted Action API)."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\B_骨骼绑定\walk_test_手写版.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

def count_fcurves(act):
    """5.x: fcurves在 layers[].strips[].channelbags (带s的属性, 不可调用)"""
    n = 0
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                n += len(bag.fcurves)
    return n

out = []
out.append("=== 有动画的骨架 ===")
for o in bpy.data.objects:
    if o.type == 'ARMATURE' and o.animation_data and o.animation_data.action:
        act = o.animation_data.action
        fc = count_fcurves(act)
        slot = o.animation_data.action_slot
        out.append(f"{o.name}: action={act.name}, fcurves={fc}, slot_id={slot.identifier if slot else None}")

out.append("")
out.append("=== 所有骨架 ===")
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        ad = o.animation_data
        has_anim = ad is not None and ad.action is not None
        out.append(f"{o.name}: bones={len(o.data.bones)}, 有动画={has_anim}")

out.append("")
out.append("=== 有armature修改器的mesh ===")
for o in bpy.data.objects:
    if o.type == 'MESH':
        for m in o.modifiers:
            if m.type == 'ARMATURE':
                out.append(f"{o.name}: armature={m.object.name if m.object else 'NONE'}, 顶点组={len(o.vertex_groups)}")

out.append("CHECK_WALK_ANIM_DONE")

with open(r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\logs\walk_anim_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))