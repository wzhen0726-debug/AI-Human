"""诊断3: 找到KEYFRAME strip里fcurves的真实位置并验证动画数据."""
import bpy, os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
BLEND = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "07_走动画测试.blend")
bpy.ops.wm.open_mainfile(filepath=BLEND)

walk_arm = None
rig_arm = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        if o.name == 'rig': rig_arm = o
        else: walk_arm = o

action = (walk_arm or rig_arm).animation_data.action
print(f"Action: {action.name}, layers={len(action.layers)}, slots={len(action.slots)}")

layer = action.layers[0]
strip = layer.strips[0]
print(f"Strip type: {strip.type}")

# 枚举strip的属性
print("\n=== Strip属性 ===")
for attr in dir(strip):
    if attr.startswith('_'): continue
    try:
        val = getattr(strip, attr)
        if callable(val): continue
        print(f"  {attr}: {type(val).__name__}")
    except Exception as e:
        print(f"  {attr}: <err {e}>")

# KEYFRAME strip通常有channelbags(slot)
print("\n=== channelbags尝试 ===")
slot = action.slots[0]
print(f"Slot: {slot.target_path if hasattr(slot,'target_path') else slot}")
try:
    cb = strip.channelbag(slot)
    print(f"channelbag(slot): {cb}")
    if cb:
        print(f"  fcurves数: {len(cb.fcurves)}")
        for fc in cb.fcurves[:5]:
            print(f"    {fc.data_path} [{fc.array_index}]")
except Exception as e:
    print(f"channelbag(slot)失败: {e}")
print("DIAG3_DONE")
