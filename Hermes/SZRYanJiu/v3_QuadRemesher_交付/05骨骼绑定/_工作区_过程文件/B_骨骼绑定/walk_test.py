"""行走动画测试: 导入Mixamo行走动画到ARP版骨骼, 验证能否播放."""
import bpy, os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
RIG = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.blend")
WALK = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx"
OUT = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "07_走动画测试.blend")

bpy.ops.wm.open_mainfile(filepath=RIG)

# 导入行走动画(作为新骨架+动作)
bpy.ops.import_scene.fbx(filepath=WALK)

# 找两个骨架
arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
print(f"骨架数: {len(arms)}")
for a in arms:
    print(f"  {a.name}: {len(a.data.bones)} 骨骼")

# 找行走动画的骨架(带animation_data)
walk_arm = None
rig_arm = None
for a in arms:
    if a.animation_data and a.animation_data.action:
        walk_arm = a
        print(f"行走骨架: {a.name}, 动作: {a.animation_data.action.name}")
    else:
        rig_arm = a

if not walk_arm:
    print("WARNING: 未找到带行走动画的骨架")
    raise SystemExit(0)

# 检查骨骼名对齐 (两边都去掉mixamorig:前缀后比较)
strip = lambda n: n.replace("mixamorig:", "")
walk_bones = set(strip(b.name) for b in walk_arm.data.bones)
rig_bones = set(strip(b.name) for b in rig_arm.data.bones)
matched = walk_bones & rig_bones
missing = walk_bones - rig_bones

print(f"\n行走骨架骨骼: {len(walk_bones)}")
print(f"rig骨架骨骼: {len(rig_bones)}")
print(f"名称匹配: {len(matched)}")
print(f"缺失: {len(missing)}")
if missing:
    print(f"  缺失列表: {sorted(missing)[:10]}")

# 如果完全匹配, 可以把动画动作绑定到rig骨架
if len(matched) >= 20:  # 至少20根匹配
    # 复制动画数据
    if rig_arm.animation_data is None:
        rig_arm.animation_data_create()
    rig_arm.animation_data.action = walk_arm.animation_data.action
    print(f"\n动画已绑定到rig骨架")

    # 播放测试: 设置帧范围
    action = walk_arm.animation_data.action
    rig_arm.animation_data.action = action
    bpy.context.scene.frame_start = int(action.frame_range[0])
    bpy.context.scene.frame_end = int(action.frame_range[1])
    print(f"帧范围: {int(action.frame_range[0])} - {int(action.frame_range[1])}")

    # 直接验证驱动: Hips在两帧的位置/旋转是否变化
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    hb1 = rig_arm.pose.bones['mixamorig:Hips'].matrix.copy()
    bpy.context.scene.frame_set(20)
    bpy.context.view_layer.update()
    hb20 = rig_arm.pose.bones['mixamorig:Hips'].matrix.copy()
    dloc = (hb20.translation - hb1.translation).length
    drot = (hb20.to_quaternion().rotation_difference(hb1.to_quaternion()).angle)
    print(f"Hips帧1→20: 位移{dloc*1000:.1f}mm, 旋转{drot:.3f}rad")
    if dloc > 0.001 or drot > 0.01:
        print("结论: 行走动画驱动成功 ✓")
    else:
        print("结论: 动画未驱动 ✗")

# 保存
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"\n保存: {OUT}")
print("WALK_TEST_DONE")
