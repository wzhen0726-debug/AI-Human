"""修复ARP版: 顶点组名改为mixamorig:前缀, 与骨骼名匹配."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\B_骨骼绑定\06_rig_arp_mixamo.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

body = None
for o in bpy.data.objects:
    if o.type == 'MESH' and 'eye' not in o.name.lower():
        if body is None or len(o.data.vertices) > len(body.data.vertices):
            body = o

rig = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        rig = o
        break

# 建立映射: ARP骨骼名 → Mixamo名
# ARP的骨骼名是 thigh_ik.l, arm_fk.l 这种, 需要映射到 mixamorig:LeftUpLeg 等
# 但更简单的是: 直接给所有顶点组加 mixamorig: 前缀(因为骨骼已经叫这个名了)
print("重命名顶点组...")
renamed = 0
for vg in body.vertex_groups:
    if not vg.name.startswith("mixamorig:"):
        old = vg.name
        vg.name = "mixamorig:" + old
        renamed += 1
        if renamed <= 5:
            print(f"  {old} → {vg.name}")

print(f"重命名顶点组: {renamed}")

# 保存
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print(f"已保存: {BLEND}")
print("ARP_VG_FIX_DONE")
