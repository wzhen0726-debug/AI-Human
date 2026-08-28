"""第4步验证: 骨架关键骨位置 vs 用户17打点 — 手腕/脚踝/手指是否对齐."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
RIG = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "07_arp_rig_v6.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)

arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
print(f"骨架: {arm.name}, {len(arm.data.bones)}骨")

# 用户17打点(AI实测值)
user_pts = {
    "root_loc": (0.0, 0.0002, 0.9007), "chin_loc": (0.0, -0.1138, 1.5875),
    "neck_loc": (0.0, 0.0382, 1.4731), "shoulder_loc": (0.2289, 0.0478, 1.4349),
    "elbow_loc": (0.4579, 0.0953, 1.4349), "hand_loc": (0.7154, 0.0193, 1.4349),
    "hand_tip_loc": (0.9062, 0.0192, 1.4349),
    "thigh_loc": (0.1144, 0.0002, 0.9007), "knee_loc": (0.1144, 0.0002, 0.5191),
    "foot_loc": (0.1144, 0.0762, 0.1376),
}

# 关键骨骼 → 用户点映射 (ARP骨骼名 → 对应用户点)
bone_map = {
    "root": "root_loc", "c_root_master.x": "root_loc",
    "c_neck.x": "neck_loc", "c_head.x": "chin_loc",
    "shoulder.l": "shoulder_loc", "c_shoulder.l": "shoulder_loc",
    "arm_stretch.l": "shoulder_loc", "forearm_stretch.l": "elbow_loc",
    "hand.l": "hand_loc", "hand_ik.l": "hand_loc",
    "thigh_stretch.l": "thigh_loc", "leg_stretch.l": "knee_loc",
    "foot.l": "foot_loc", "foot_ik.l": "foot_loc",
}

import math
def dist(a, b):
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)

print("\n=== 关键骨位置对照 (差>5cm标红) ===")
for bname, pt_name in bone_map.items():
    b = arm.data.bones.get(bname)
    if not b:
        continue
    h = arm.matrix_world @ b.head_local
    u = user_pts[pt_name]
    d = dist((h.x, h.y, h.z), u)
    flag = " !!!" if d > 0.05 else ""
    print(f"{bname}: 骨=({h.x:.3f},{h.y:.3f},{h.z:.3f}) 点=({u[0]:.3f},{u[1]:.3f},{u[2]:.3f}) 差={d*100:.1f}cm{flag}")

# 手指骨骼数量
finger_bones = [b for b in arm.data.bones if any(k in b.name for k in ['thumb', 'index', 'middle', 'ring', 'pinky'])]
print(f"\n手指骨: {len(finger_bones)}根")
print("VERIFY_DONE")
