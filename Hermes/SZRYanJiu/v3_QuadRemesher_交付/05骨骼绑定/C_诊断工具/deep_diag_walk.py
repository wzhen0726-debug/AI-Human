"""深入诊断: slot已改对但动画仍不驱动. 检查depsgraph求值/骨骼矩阵/驱动器干扰."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\B_骨骼绑定\walk_test_手写版.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

rig = bpy.data.objects.get("MixamoSkeleton")
ad = rig.animation_data
out = []

# 1) slot现状
out.append(f"action: {ad.action.name}, slot: {ad.action_slot.identifier}")

# 2) 帧设到18, 直接读pose bone矩阵(不经depsgraph)
scn = bpy.context.scene
scn.frame_set(18)
out.append(f"帧={scn.frame_current}")

h = rig.pose.bones.get("mixamorig:Hips")
if h:
    out.append(f"Hips rotation_euler(原始): {tuple(round(r,3) for r in h.rotation_euler)}")
    out.append(f"Hips rotation_quaternion: {tuple(round(r,3) for r in h.rotation_quaternion)}")
    out.append(f"Hips matrix_translation: {tuple(round(c,3) for c in h.matrix.translation)}")
    # 关键: 手动从fcurve取帧18的值
    act = ad.action
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                if bag.slot_handle == ad.action_slot.handle:
                    for fc in bag.fcurves:
                        if 'Hips' in fc.data_path and 'rotation_euler' in fc.data_path:
                            out.append(f"FCurve帧18值: {fc.data_path}[{fc.array_index}] = {fc.evaluate(18):.4f}")
                            break
                    break

# 3) mesh求值再试一次(用evaluated对象)
body = bpy.data.objects.get("tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR")
dg = bpy.context.evaluated_depsgraph_get()
scn.frame_set(1)
bpy.context.view_layer.update()
base = [v.co.copy() for v in body.data.vertices[:2000]]
scn.frame_set(18)
bpy.context.view_layer.update()
moved = sum(1 for i, v in enumerate(body.data.vertices[:2000]) if (v.co - base[i]).length > 0.01)
out.append(f"mesh变形(直接): {moved}/2000")

body_ev = body.evaluated_get(dg)
scn.frame_set(18)
bpy.context.view_layer.update()
moved2 = sum(1 for i, v in enumerate(body_ev.data.vertices[:2000]) if (v.co - base[i]).length > 0.01)
out.append(f"mesh变形(evaluated): {moved2}/2000")

# 4) NLA轨道是否mute了action
out.append(f"NLA轨道数: {len(ad.nla_tracks)}")
for tr in ad.nla_tracks:
    out.append(f"  轨道'{tr.name}': mute={tr.mute}, strips={len(tr.strips)}")

with open(r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\logs\deep_diag.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))