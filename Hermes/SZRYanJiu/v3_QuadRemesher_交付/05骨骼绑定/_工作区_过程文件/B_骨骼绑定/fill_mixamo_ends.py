"""补齐ARP版缺失的6根Mixamo骨骼: Spine + 4个End末端骨(HeadTop/Thumb4/Toe).
补齐后与Mixamo 65骨骼完全对齐."""
import bpy, os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
IN_BLEND = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.blend")
OUT_BLEND = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.blend")
OUT_GLB = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.glb")

bpy.ops.wm.open_mainfile(filepath=IN_BLEND)

arm = None
body = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        arm = o
    elif o.type == 'MESH' and len(o.vertex_groups) > 0:
        body = o

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones

# 1. Spine: Mixamo标准中 Hips 和 Spine1 之间有一根 Spine
# ARP版没有中间脊柱, 在Hips和Spine1之间插入
hips = eb.get('Hips')
spine1 = eb.get('Spine1')
if hips and spine1:
    spine = eb.new('Spine')
    spine.head = hips.head + (spine1.head - hips.head) * 0.33
    spine.tail = spine1.head
    spine.parent = hips
    spine1.parent = spine
    print("插入 Spine")

# 2. End末端骨: 各加一根短骨延伸
def add_end(parent_name, end_name, length=0.05, dir_vec=None):
    p = eb.get(parent_name)
    if not p:
        print(f"  跳过 {end_name}: 找不到父骨 {parent_name}")
        return
    e = eb.new(end_name)
    e.head = p.tail
    if dir_vec:
        e.tail = p.tail + dir_vec * length
    else:
        e.tail = p.tail + (p.tail - p.head).normalized() * length
    e.parent = p
    print(f"插入 {end_name} (父: {parent_name})")

# HeadTop_End: Head顶端向上
add_end('Head', 'HeadTop_End', 0.10, None)
# Thumb4: 拇指末节延伸
add_end('LeftHandThumb3', 'LeftHandThumb4', 0.03, None)
add_end('RightHandThumb3', 'RightHandThumb4', 0.03, None)
# Toe_End: 脚趾延伸
add_end('LeftToeBase', 'LeftToe_End', 0.05, None)
add_end('RightToeBase', 'RightToe_End', 0.05, None)

bpy.ops.object.mode_set(mode='OBJECT')
print(f"\n最终骨骼数: {len(arm.data.bones)} (目标65)")

# 保存
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"保存: {OUT_BLEND}")

# 导出GLB
try:
    bpy.ops.export_scene.gltf(
        filepath=OUT_GLB,
        export_format='GLB',
        use_selection=False,
    )
    print(f"GLB: {OUT_GLB}")
except Exception as e:
    print(f"GLB导出失败: {e}")

print("FILL_DONE")
