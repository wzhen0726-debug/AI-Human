"""诊断: 确认rest pose臂角 + 列出可摆姿势的臂控制器骨."""
import bpy, os, math
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
RIG = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "07_arp_rig_v6.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')

# 1) rest pose臂角: shoulder→hand 方向 vs 水平
def bone_head(name):
    b = arm.data.bones.get(name)
    return (arm.matrix_world @ b.head_local) if b else None

sh = bone_head("shoulder.l")
ha = bone_head("hand.l")
if sh and ha:
    arm_vec = ha - sh
    # 与水平面的夹角 (水平=xy平面)
    horiz = Vector((arm_vec.x, arm_vec.y, 0))
    ang = math.degrees(arm_vec.angle(horiz)) if horiz.length > 0 else 0
    print(f"rest pose 左臂: shoulder=({sh.x:.3f},{sh.z:.3f}) hand=({ha.x:.3f},{ha.z:.3f})")
    print(f"  臂与水平夹角: {ang:.1f}° (0=水平T-pose, >0=下垂A-pose)")

# 2) 模型臂角对照 (标记点)
print("\n标记点: shoulder z=1.435, hand z=1.435 → 水平(T-pose)")

# 3) 列出臂相关骨 (找控制器)
print("\n=== 含arm/shoulder/hand/fk/ik的骨骼 ===")
for b in arm.data.bones:
    if any(k in b.name.lower() for k in ['arm', 'shoulder', 'hand_fk', 'hand_ik', 'c_arm', 'c_hand']):
        if 'stretch' not in b.name and 'twist' not in b.name:
            print(f"  {b.name}")
print("DIAG3_DONE")
