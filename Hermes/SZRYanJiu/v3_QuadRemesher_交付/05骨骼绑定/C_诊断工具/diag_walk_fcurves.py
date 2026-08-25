"""诊断: 行走动画F曲线data_path与rig骨骼名匹配问题."""
import bpy, os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
BLEND = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "07_走动画测试.blend")

bpy.ops.wm.open_mainfile(filepath=BLEND)

rig_arm = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE' and o.name == 'rig':
        rig_arm = o

if not rig_arm.animation_data:
    print("ERROR: rig无animation_data")
    raise SystemExit(0)

action = rig_arm.animation_data.action
# Blender 5.1新动画层系统: fcurves在action.layers[].strips[].channelbag().fcurves
all_fcurves = []
try:
    for layer in action.layers:
        for strip in layer.strips:
            for cb in strip.channelbags():
                if cb:
                    all_fcurves.extend(cb.fcurves)
    print(f"(新动画层API) F曲线数: {len(all_fcurves)}")
except Exception as e:
    print(f"新API失败({e}), 试旧API")
    all_fcurves = list(action.fcurves) if hasattr(action, 'fcurves') else []

print(f"F曲线数: {len(all_fcurves)}")

# 看data_path格式
paths = set()
for fc in all_fcurves:
    paths.add(fc.data_path)
print(f"唯一data_path数: {len(paths)}")
for p in sorted(paths)[:15]:
    print(f"  {p}")

# pose bone名
pose_names = set(pb.name for pb in rig_arm.pose.bones)
print(f"\npose骨骼数: {len(pose_names)}")

# 检查data_path引用的骨骼是否存在
found = 0
notfound = 0
for p in paths:
    # data_path格式: pose.bones["BoneName"].location
    if 'pose.bones["' in p:
        bname = p.split('pose.bones["')[1].split('"]')[0]
        if bname in pose_names:
            found += 1
        else:
            notfound += 1
            if notfound <= 5:
                print(f"  找不到: {bname}")

print(f"\ndata_path匹配: {found}存在, {notfound}缺失")

# 试手动设帧看Hips有没有动
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()
if 'Hips' in rig_arm.pose.bones:
    h1 = rig_arm.pose.bones['Hips'].matrix.copy()
    bpy.context.scene.frame_set(20)
    bpy.context.view_layer.update()
    h20 = rig_arm.pose.bones['Hips'].matrix.copy()
    print(f"\nHips 帧1位置: {h1.translation}")
    print(f"Hips 帧20位置: {h20.translation}")
    print(f"Hips 帧1旋转: {h1.to_euler()}")
    print(f"Hips 帧20旋转: {h20.to_euler()}")
    if abs(h20.translation.z - h1.translation.z) > 0.001 or (h20.to_euler().x != h1.to_euler().x):
        print("结论: 动画驱动了骨骼")
    else:
        print("结论: 动画未驱动骨骼")
print("DIAG_DONE")
