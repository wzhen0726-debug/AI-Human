"""ARP版去控制器导出: 只保留变形骨骼+mesh, 删除控制器/机制骨, 导出Godot可用GLB.
ARP生成的rig有339根骨骼(含控制器/机制骨), 需要精简到纯变形骨骼.
方法: 保留mixamorig:前缀的骨骼(变形骨), 删除其余, 重新导出."""
import bpy, os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
IN_BLEND = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.blend")
OUT_BLEND = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo_godot.blend")
OUT_GLB = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo_godot.glb")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=IN_BLEND)

# 找骨架和mesh
rig = None
body = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        rig = o
    elif o.type == 'MESH' and 'eye' not in o.name.lower():
        body = o

print(f"骨架: {rig.name}, {len(rig.data.bones)}根")
print(f"身体: {body.name}, {len(body.data.vertices)}顶点")

# 统计要保留的骨骼
keep_bones = [b.name for b in rig.data.bones if b.name.startswith("mixamorig:")]
print(f"保留变形骨骼: {len(keep_bones)}根")

# 进入编辑模式删除非mixamorig骨骼
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
edit_bones = rig.data.edit_bones
to_remove = [eb for eb in edit_bones if not eb.name.startswith("mixamorig:")]
print(f"删除控制器/机制骨: {len(to_remove)}根")
for eb in to_remove:
    edit_bones.remove(eb)
bpy.ops.object.mode_set(mode='OBJECT')

# 检查mesh的顶点组是否都对应保留的骨骼
vg_names = set(vg.name for vg in body.vertex_groups)
bone_names = set(b.name for b in rig.data.bones)
missing = vg_names - bone_names
if missing:
    print(f"警告: {len(missing)}个顶点组无对应骨骼(将被忽略): {sorted(missing)[:5]}")

# 导出
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format='GLB',
    export_yup=True,
    export_apply=True,
    export_skins=True,
    export_animations=False,
    export_image_format='AUTO',
    export_materials='EXPORT',
)

print(f"\n已保存: {OUT_BLEND}")
print(f"已导出: {OUT_GLB}")
print(f"最终骨骼: {len(rig.data.bones)}根(纯变形骨, 无控制器)")
print("ARP_STRIP_DONE")