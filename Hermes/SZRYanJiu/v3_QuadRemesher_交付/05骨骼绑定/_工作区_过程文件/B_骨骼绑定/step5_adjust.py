"""第5步: 修正骨架骨骼位置 — 把手臂从A-pose拉回T-pose, 腿对齐标记点.
根因: go_detect按A-pose建手臂(下垂), 但模型是T-pose(平举), 导致手腕差33cm.
方法: 编辑模式下直接设置关键骨的head/tail到标记点位置."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
RIG = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "07_arp_rig_v6.blend")
OUT = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "08_arp_rig_v6_adjusted.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)

arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
print(f"骨架: {arm.name}, {len(arm.data.bones)}骨")

# 用户标记点 (AI实测)
M = {
    "root":     (0.0,    0.0002, 0.9007),
    "neck":     (0.0,    0.0382, 1.4731),
    "shoulder": (0.2289, 0.0478, 1.4349),
    "elbow":    (0.4579, 0.0953, 1.4349),
    "hand":     (0.7154, 0.0193, 1.4349),
    "hand_tip": (0.9062, 0.0192, 1.4349),
    "thigh":    (0.1144, 0.0002, 0.9007),
    "knee":     (0.1144, 0.0002, 0.5191),
    "foot":     (0.1144, 0.0762, 0.1376),
}

def mir(v):
    return (-v[0], v[1], v[2])

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones

def set_bone(name, head, tail):
    b = eb.get(name)
    if b:
        b.head = head
        b.tail = tail
        return True
    return False

adjusted = 0
# === 左臂 (T-pose: 水平) ===
for side, sgn in [("l", 1), ("r", -1)]:
    sh = (sgn*M["shoulder"][0], M["shoulder"][1], M["shoulder"][2])
    el = (sgn*M["elbow"][0],    M["elbow"][1],    M["elbow"][2])
    ha = (sgn*M["hand"][0],     M["hand"][1],     M["hand"][2])
    ht = (sgn*M["hand_tip"][0], M["hand_tip"][1], M["hand_tip"][2])
    th = (sgn*M["thigh"][0],    M["thigh"][1],    M["thigh"][2])
    kn = (sgn*M["knee"][0],     M["knee"][1],     M["knee"][2])
    ft = (sgn*M["foot"][0],     M["foot"][1],     M["foot"][2])

    # 手臂链: shoulder→arm→forearm→hand (T-pose水平)
    if set_bone(f"shoulder.{side}", sh, (sh[0]+sgn*0.06, sh[1], sh[2])): adjusted+=1
    if set_bone(f"arm_stretch.{side}", sh, el): adjusted+=1
    if set_bone(f"forearm_stretch.{side}", el, ha): adjusted+=1
    if set_bone(f"hand.{side}", ha, ht): adjusted+=1

    # 腿链: thigh→leg→foot
    if set_bone(f"thigh_stretch.{side}", th, kn): adjusted+=1
    if set_bone(f"leg_stretch.{side}", kn, ft): adjusted+=1
    if set_bone(f"foot.{side}", ft, (ft[0], ft[1]-0.15, ft[2])): adjusted+=1

# 脊柱
if set_bone("c_root_master.x", M["root"], (M["root"][0], M["root"][1], M["root"][2]+0.12)): adjusted+=1
if set_bone("c_neck.x", M["neck"], (M["neck"][0], M["neck"][1], M["neck"][2]+0.06)): adjusted+=1

print(f"调整骨骼: {adjusted}根")
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"保存: {OUT}")
print("ADJUST_DONE")
