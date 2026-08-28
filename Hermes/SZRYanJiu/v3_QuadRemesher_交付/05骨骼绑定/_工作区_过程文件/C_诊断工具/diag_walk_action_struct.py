"""诊断2: Blender 5.1 Action动画数据结构, 找到fcurves真实位置."""
import bpy, os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
BLEND = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "07_走动画测试.blend")
bpy.ops.wm.open_mainfile(filepath=BLEND)

rig_arm = None
walk_arm = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        if o.name == 'rig': rig_arm = o
        else: walk_arm = o

# 用原始行走骨架的action(确保有动画数据)
src = walk_arm if (walk_arm and walk_arm.animation_data) else rig_arm
print(f"源骨架: {src.name}")
action = src.animation_data.action
print(f"Action: {action.name}")

# 枚举action的所有属性
print("\n=== Action属性 ===")
for attr in dir(action):
    if attr.startswith('_'): continue
    try:
        val = getattr(action, attr)
        if callable(val): continue
        tname = type(val).__name__
        print(f"  {attr}: {tname}")
    except: pass

# 试各种读fcurve的方式
print("\n=== 读fcurves尝试 ===")
def try_read(desc, fn):
    try:
        r = fn()
        print(f"  {desc}: {r}")
        return r
    except Exception as e:
        print(f"  {desc}: 失败 {type(e).__name__}")
        return None

try_read("action.fcurves", lambda: len(action.fcurves))
try_read("action.layers", lambda: len(action.layers))
try_read("action.slots", lambda: len(action.slots) if hasattr(action,'slots') else 'N/A')

# 如果有layers, 深入
if hasattr(action, 'layers'):
    for li, layer in enumerate(action.layers):
        print(f"\n  Layer {li}: {layer.name}")
        for si, strip in enumerate(layer.strips):
            print(f"    Strip {si}: type={strip.type}")
            try:
                for ci, cb in enumerate(strip.channelbags()):
                    if cb:
                        print(f"      ChannelBag {ci}: {len(cb.fcurves)} fcurves")
                        # 打前3条data_path
                        for fc in cb.fcurves[:3]:
                            print(f"        {fc.data_path}")
            except Exception as e:
                print(f"      channelbags失败: {e}")

print("DIAG2_DONE")
