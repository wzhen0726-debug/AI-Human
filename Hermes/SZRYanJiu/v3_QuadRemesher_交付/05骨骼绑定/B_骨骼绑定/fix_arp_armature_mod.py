"""修复ARP版: 给mesh加armature修改器(ARP用父级绑定, 不是修改器绑定)."""
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

# 检查是否已有armature修改器
has_arm_mod = any(m.type == 'ARMATURE' for m in body.modifiers)
print(f"已有armature修改器: {has_arm_mod}")

if not has_arm_mod:
    # 添加armature修改器
    mod = body.modifiers.new(name="Armature", type='ARMATURE')
    mod.object = rig
    mod.use_deform = True
    print(f"已添加armature修改器, 目标={rig.name}")
else:
    print("已有armature修改器")

# 保存
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print(f"已保存: {BLEND}")
print("ARP_FIX_DONE")
