"""验证: 手写版骨骼前缀后, 顶点组是否与骨骼名匹配(否则不变形)."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\B_骨骼绑定\06_rig_final.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
body = next((o for o in bpy.data.objects if o.type == 'MESH' and len(o.vertex_groups) > 0), None)

bone_names = set(b.name for b in arm.data.bones)
vg_names = set(vg.name for vg in body.vertex_groups)

matched = bone_names & vg_names
print(f"骨骼数: {len(bone_names)}, 顶点组数: {len(vg_names)}")
print(f"匹配(骨骼名=顶点组名): {len(matched)}")
print(f"骨骼无对应顶点组: {len(bone_names - vg_names)}")
print(f"顶点组无对应骨骼: {len(vg_names - bone_names)}")
if bone_names - vg_names:
    print(f"  无顶点组的骨骼示例: {sorted(bone_names - vg_names)[:5]}")
if vg_names - bone_names:
    print(f"  无骨骼的顶点组示例: {sorted(vg_names - bone_names)[:5]}")

# armature修改器检查
mods = [m for m in body.modifiers if m.type == 'ARMATURE']
print(f"armature修改器: {len(mods)}, 目标正确: {mods[0].object == arm if mods else 'N/A'}")
print("VG_MATCH_DONE")
