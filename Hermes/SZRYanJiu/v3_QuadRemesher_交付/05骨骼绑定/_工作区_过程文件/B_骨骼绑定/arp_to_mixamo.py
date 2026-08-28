"""ARP骨架 → Mixamo命名对齐
将ARP变形骨骼重命名为Mixamo标准名, 合并twist/stretch骨骼权重, 删除多余骨骼.
输出: 06_rig_arp_mixamo.blend + .glb
"""
import bpy, os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
IN_BLEND = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp.blend")
OUT_BLEND = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.blend")
OUT_GLB = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.glb")

bpy.ops.wm.open_mainfile(filepath=IN_BLEND)

# 找骨架和身体
arm = None
body = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        arm = o
    elif o.type == 'MESH' and len(o.vertex_groups) > 0:
        body = o

print(f"骨架: {arm.name}, 身体: {body.name}, 顶点组: {len(body.vertex_groups)}")

# ARP变形骨骼 → Mixamo名 映射
# 格式: ARP名 → Mixamo名 (None=删除,权重合并到指定目标)
RENAME_MAP = {
    # 主干
    'root.x': 'Hips',
    'spine_01.x': 'Spine1',
    'spine_02.x': 'Spine2',
    'neck.x': 'Neck',
    'head.x': 'Head',
    # 肩
    'shoulder.l': 'LeftShoulder',
    'shoulder.r': 'RightShoulder',
    # 手臂
    'arm_stretch.l': 'LeftArm',
    'arm_stretch.r': 'RightArm',
    'forearm_stretch.l': 'LeftForeArm',
    'forearm_stretch.r': 'RightForeArm',
    'hand.l': 'LeftHand',
    'hand.r': 'RightHand',
    # 腿
    'thigh_stretch.l': 'LeftUpLeg',
    'thigh_stretch.r': 'RightUpLeg',
    'leg_stretch.l': 'LeftLeg',
    'leg_stretch.r': 'RightLeg',
    'foot.l': 'LeftFoot',
    'foot.r': 'RightFoot',
    'toes_01.l': 'LeftToeBase',
    'toes_01.r': 'RightToeBase',
    # 手指 L
    'c_index1_base.l': 'LeftHandIndex1',
    'index1.l': 'LeftHandIndex2',
    'c_index2.l': 'LeftHandIndex3',
    'c_index3.l': 'LeftHandIndex4',
    'c_middle1_base.l': 'LeftHandMiddle1',
    'middle1.l': 'LeftHandMiddle2',
    'c_middle2.l': 'LeftHandMiddle3',
    'c_middle3.l': 'LeftHandMiddle4',
    'c_ring1_base.l': 'LeftHandRing1',
    'ring1.l': 'LeftHandRing2',
    'c_ring2.l': 'LeftHandRing3',
    'c_ring3.l': 'LeftHandRing4',
    'c_pinky1_base.l': 'LeftHandPinky1',
    'pinky1.l': 'LeftHandPinky2',
    'c_pinky2.l': 'LeftHandPinky3',
    'c_pinky3.l': 'LeftHandPinky4',
    'thumb1.l': 'LeftHandThumb1',
    'c_thumb2.l': 'LeftHandThumb2',
    'c_thumb3.l': 'LeftHandThumb3',
    # 手指 R
    'c_index1_base.r': 'RightHandIndex1',
    'index1.r': 'RightHandIndex2',
    'c_index2.r': 'RightHandIndex3',
    'c_index3.r': 'RightHandIndex4',
    'c_middle1_base.r': 'RightHandMiddle1',
    'middle1.r': 'RightHandMiddle2',
    'c_middle2.r': 'RightHandMiddle3',
    'c_middle3.r': 'RightHandMiddle4',
    'c_ring1_base.r': 'RightHandRing1',
    'ring1.r': 'RightHandRing2',
    'c_ring2.r': 'RightHandRing3',
    'c_ring3.r': 'RightHandRing4',
    'c_pinky1_base.r': 'RightHandPinky1',
    'pinky1.r': 'RightHandPinky2',
    'c_pinky2.r': 'RightHandPinky3',
    'c_pinky3.r': 'RightHandPinky4',
    'thumb1.r': 'RightHandThumb1',
    'c_thumb2.r': 'RightHandThumb2',
    'c_thumb3.r': 'RightHandThumb3',
}

# Twist/stretch骨骼 → 权重合并目标 (这些骨骼Mixamo没有,权重并入主骨骼)
MERGE_MAP = {
    'forearm_twist.l': 'LeftForeArm',
    'forearm_twist.r': 'RightForeArm',
    'leg_twist.l': 'LeftLeg',
    'leg_twist.r': 'RightLeg',
    'thigh_twist.l': 'LeftUpLeg',
    'thigh_twist.r': 'RightUpLeg',
    'c_arm_twist_offset.l': 'LeftArm',
    'c_arm_twist_offset.r': 'RightArm',
}

# Step 1: 合并twist骨骼权重到主骨骼
print("\n=== Step 1: 合并twist权重 ===")
for src_name, dst_name in MERGE_MAP.items():
    src_vg = body.vertex_groups.get(src_name)
    if not src_vg:
        continue
    # 确保目标顶点组存在
    dst_vg = body.vertex_groups.get(dst_name)
    if not dst_vg:
        dst_vg = body.vertex_groups.new(name=dst_name)
    # 把src的权重加到dst
    for v in body.data.vertices:
        for g in v.groups:
            if g.group == src_vg.index and g.weight > 0:
                dst_vg.add([v.index], g.weight, 'ADD')
    body.vertex_groups.remove(src_vg)
    print(f"  合并 {src_name} → {dst_name}")

# Step 2: 重命名骨骼
print("\n=== Step 2: 重命名骨骼 ===")
renamed = 0
for arp_name, mix_name in RENAME_MAP.items():
    bone = arm.data.bones.get(arp_name)
    if bone:
        bone.name = mix_name
        renamed += 1
print(f"  重命名 {renamed} 根骨骼")

# Step 3: 重命名顶点组
print("\n=== Step 3: 重命名顶点组 ===")
vg_renamed = 0
for arp_name, mix_name in RENAME_MAP.items():
    vg = body.vertex_groups.get(arp_name)
    if vg:
        vg.name = mix_name
        vg_renamed += 1
print(f"  重命名 {vg_renamed} 个顶点组")

# Step 4: 删除未映射的骨骼(控制器、IK极等)
print("\n=== Step 4: 清理非变形骨骼 ===")
# 保留的骨骼名(已重命名的)
keep_names = set(RENAME_MAP.values())
# 进入编辑模式删除多余骨骼
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
removed = 0
for eb in list(arm.data.edit_bones):
    if eb.name not in keep_names:
        # 先确保子骨骼不会丢失(重新连接到父骨骼)
        for child in eb.children:
            if child.name in keep_names:
                child.parent = eb.parent
        arm.data.edit_bones.remove(eb)
        removed += 1
bpy.ops.object.mode_set(mode='OBJECT')
print(f"  删除 {removed} 根非变形骨骼, 保留 {len(arm.data.bones)} 根")

# Step 5: 保存
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"\n保存: {OUT_BLEND}")

# Step 6: 导出GLB
try:
    bpy.ops.export_scene.gltf(
        filepath=OUT_GLB,
        export_format='GLB',
        use_selection=False,
    )
    print(f"GLB: {OUT_GLB}")
except Exception as e:
    print(f"GLB导出失败: {e}")

print(f"\n最终: {len(arm.data.bones)} 根骨骼, {len(body.vertex_groups)} 个顶点组")
print("ARP_MIXAMO_DONE")
