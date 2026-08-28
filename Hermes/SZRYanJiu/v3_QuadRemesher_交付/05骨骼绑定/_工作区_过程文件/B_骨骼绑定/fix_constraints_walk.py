"""清理ARP变形骨的控制器约束 + 重做行走测试.
根因: ARP生成的骨架含FK/IK控制器约束, 变形骨(改名后)仍被COPY_LOCATION/STRETCH_TO锁死,
导致行走动画四元数在变但最终姿态不动."""
import bpy, os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
WALK_FBX = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx"
RIG = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.blend")
OUT = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "07_走动画测试.blend")

bpy.ops.wm.open_mainfile(filepath=RIG)

rig_arm = None
body = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE' and o.name == 'rig':
        rig_arm = o
    elif o.type == 'MESH' and len(o.vertex_groups) > 0:
        body = o

# Step 1: 删除所有pose bone约束(它们是ARP控制器的, 改名后必须清掉)
removed_constraints = 0
for pb in rig_arm.pose.bones:
    for c in list(pb.constraints):
        pb.constraints.remove(c)
        removed_constraints += 1
print(f"删除约束: {removed_constraints}个")

# 保存清理后的rig
bpy.ops.wm.save_as_mainfile(filepath=RIG)
print(f"已保存清理后的rig: {RIG}")

# Step 2: 重新导出GLB(无约束)
try:
    bpy.ops.export_scene.gltf(
        filepath=os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.glb"),
        export_format='GLB',
        use_selection=False,
    )
    print("GLB重导出完成")
except Exception as e:
    print(f"GLB导出失败: {e}")

# Step 3: 导入行走动画测试
bpy.ops.import_scene.fbx(filepath=WALK_FBX)
walk_arm = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE' and o.name != 'rig' and o.animation_data and o.animation_data.action:
        walk_arm = o

action = walk_arm.animation_data.action
walk_slot = walk_arm.animation_data.action_slot

# 复制action, 去掉Hips位移(原地走路)
rig_action = action.copy()
rig_action.name = "Walk_Cycle_rig"
strip = rig_action.layers[0].strips[0]
slot0 = rig_action.slots[0]
cb = strip.channelbag(slot0)
if cb:
    removed = 0
    for fc in list(cb.fcurves):
        if 'mixamorig:Hips' in fc.data_path and 'location' in fc.data_path:
            cb.fcurves.remove(fc)
            removed += 1
    print(f"删除Hips位移F曲线: {removed}条")

# 绑定到rig
if rig_arm.animation_data is None:
    rig_arm.animation_data_create()
rig_arm.animation_data.action = rig_action
rig_arm.animation_data.action_slot = slot0

# Step 4: 全面验证
print("\n=== 验证 ===")
bones = ['mixamorig:Hips', 'mixamorig:Spine', 'mixamorig:LeftArm',
         'mixamorig:LeftUpLeg', 'mixamorig:LeftLeg', 'mixamorig:RightUpLeg']
import math
bpy.context.scene.frame_set(1); bpy.context.view_layer.update()
m1 = {n: rig_arm.pose.bones[n].matrix.copy() for n in bones}
bpy.context.scene.frame_set(18); bpy.context.view_layer.update()
m2 = {n: rig_arm.pose.bones[n].matrix.copy() for n in bones}
any_move = False
for n in bones:
    ang = math.degrees(m2[n].to_quaternion().rotation_difference(m1[n].to_quaternion()).angle)
    print(f"  {n}: 帧1→18旋转 {ang:.1f}°")
    if ang > 1:
        any_move = True

# 网格变形验证
dg = bpy.context.evaluated_depsgraph_get()
bpy.context.scene.frame_set(1); bpy.context.view_layer.update()
be1 = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
import numpy as np
p1 = np.array([v.co for v in be1.data.vertices])[::10]
bpy.context.scene.frame_set(18); bpy.context.view_layer.update()
be2 = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
p2 = np.array([v.co for v in be2.data.vertices])[::10]
diff = np.linalg.norm(p2-p1, axis=1)
print(f"  网格变形顶点(>1cm): {(diff>0.01).sum()}/{len(diff)}, 最大位移{diff.max()*100:.1f}cm")

if any_move and diff.max() < 1.0:
    print("\n结论: 行走动画驱动成功, 无飞走 ✓")
    bpy.data.objects.remove(walk_arm, do_unlink=True)
    bpy.context.scene.frame_start = int(action.frame_range[0])
    bpy.context.scene.frame_end = int(action.frame_range[1])
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print(f"保存: {OUT}")
else:
    print("\n结论: 仍有问题 ✗")
print("CONSTRAINT_FIX_DONE")
