"""方案1抢救: 从ARP正确的参考骨架提取最终骨架 (Mixamo命名).
依据: 参考骨66根位置全对(=用户17标记点), 手指层级完整;
      错的只是go_detect生成的A-pose变形骨. 弃变形骨, 用参考骨重建.
映射: ARP参考骨 → Mixamo标准名 (含手指15根/手, 脚趾)."""
import bpy, os
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
RIG = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "07_arp_rig_v6.blend")
OUT = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "17_arp_fingers_fixed.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)

src_arm = bpy.data.objects.get("rig")
body = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices))
mw = src_arm.matrix_world

def ref(name):
    return src_arm.data.bones.get(name)
def whead(name):
    return mw @ ref(name).head_local
def wtail(name):
    return mw @ ref(name).tail_local

# (Mixamo名, 父名, head来源ref, tail来源ref)
# tail来源=None时用head来源的tail; 合并骨用(head骨, tail骨)两个来源
MAP = [("Hips", None, "root_ref.x", "root_ref.x"),
       ("Spine", "Hips", "spine_01_ref.x", "spine_01_ref.x"),
       ("Spine1", "Spine", "spine_02_ref.x", "spine_02_ref.x"),
       ("Spine2", "Spine1", "spine_03_ref.x", "spine_03_ref.x"),
       ("Neck", "Spine2", "neck_ref.x", "neck_ref.x"),
       ("Head", "Neck", "head_ref.x", "head_ref.x"),
       ("HeadTop_End", "Head", "SPECIAL_HEADTOP", None)]

for side, pre in [("l", "Left"), ("r", "Right")]:
    s = "." + side
    MAP += [
        # Mixamo约定: Shoulder head在脊柱侧, tail到肩关节 — 原样即可(不反转)
        (f"{pre}Shoulder", "Spine2", f"shoulder_ref{s}", f"shoulder_ref{s}"),
        (f"{pre}Arm", f"{pre}Shoulder", f"arm_ref{s}", f"arm_ref{s}"),
        (f"{pre}ForeArm", f"{pre}Arm", f"forearm_ref{s}", f"forearm_ref{s}"),
        # Hand尾伸到中指指根(Mixamo约定: 掌骨区归Hand骨), 不再只到掌中
        # HEAD_前缀=取该参考骨的head(指根), 而非tail(第二关节)
        (f"{pre}Hand", f"{pre}ForeArm", f"hand_ref{s}", f"HEAD_middle1_ref{s}"),
        # 拇指 (ARP无base, 直接1/2/3)
        (f"{pre}HandThumb1", f"{pre}Hand", f"thumb1_ref{s}", f"thumb1_ref{s}"),
        (f"{pre}HandThumb2", f"{pre}HandThumb1", f"thumb2_ref{s}", f"thumb2_ref{s}"),
        (f"{pre}HandThumb3", f"{pre}HandThumb2", f"thumb3_ref{s}", f"thumb3_ref{s}"),
    ]
    # 四指: Mixamo约定 — 掌骨区归Hand骨, 指骨从指根开始.
    # Finger1只覆盖近节指骨(index1: 指根→第2关节), 不并入掌段base
    for f in ["index", "middle", "ring", "pinky"]:
        F = f.capitalize()
        MAP += [
            (f"{pre}Hand{F}1", f"{pre}Hand", f"{f}1_ref{s}", f"{f}1_ref{s}"),
            (f"{pre}Hand{F}2", f"{pre}Hand{F}1", f"{f}2_ref{s}", f"{f}2_ref{s}"),
            (f"{pre}Hand{F}3", f"{pre}Hand{F}2", f"{f}3_ref{s}", f"{f}3_ref{s}"),
        ]
    MAP += [
        (f"{pre}UpLeg", "Hips", f"thigh_ref{s}", f"thigh_ref{s}"),
        (f"{pre}Leg", f"{pre}UpLeg", f"leg_ref{s}", f"leg_ref{s}"),
        (f"{pre}Foot", f"{pre}Leg", f"foot_ref{s}", f"foot_ref{s}"),
        (f"{pre}ToeBase", f"{pre}Foot", f"toes_ref{s}", f"toes_ref{s}"),
        (f"{pre}Toe_End", f"{pre}ToeBase", "SPECIAL_TOE", s),
    ]

# ===== 清理body的旧绑定 =====
body.modifiers.clear()
body.vertex_groups.clear()
print("body旧权重/修改器已清")

# ===== 建新骨架 =====
arm_data = bpy.data.armatures.new("MixamoSkeleton")
arm = bpy.data.objects.new("MixamoSkeleton", arm_data)
bpy.context.scene.collection.objects.link(arm)
arm.matrix_world.identity()

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm_data.edit_bones

created = {}
for name, parent, hsrc, tsrc in MAP:
    b = eb.new(name)
    if tsrc and tsrc.startswith("HEAD_"):
        # 尾部取该参考骨的head(如中指指根)而非tail
        b.head = whead(hsrc)
        b.tail = whead(tsrc[5:])
    elif hsrc == "SPECIAL_HEADTOP":
        h = wtail("head_ref.x")
        b.head = h
        b.tail = h + Vector((0, 0, 0.10))
    elif hsrc == "SPECIAL_TOE":
        h = wtail(f"toes_ref{tsrc}")
        d = (wtail(f"toes_ref{tsrc}") - whead(f"toes_ref{tsrc}")).normalized()
        b.head = h
        b.tail = h + d * 0.05
    else:
        b.head = whead(hsrc)
        b.tail = wtail(tsrc if tsrc else hsrc)
    if (b.tail - b.head).length < 0.005:
        b.tail = b.head + Vector((0, 0, 0.02))
    created[name] = b

for name, parent, _, _ in MAP:
    if parent:
        created[name].parent = created[parent]

print(f"新骨架骨骼数: {len(created)}")
bpy.ops.object.mode_set(mode='OBJECT')

# ===== 删旧rig, 自动权重 =====
bpy.data.objects.remove(src_arm, do_unlink=True)
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
print(f"自动权重完成, 顶点组: {len(body.vertex_groups)}")

# ===== 验证: 新骨位置 vs 用户标记 =====
marks = {"Hips": (0.0, 0.0002, 0.9007), "Neck": (0.0, 0.0382, 1.4731),
         "LeftShoulder": (0.057, 0.068, 1.435),  # Mixamo约定: Shoulder head在脊柱侧
         "LeftArm": (0.2289, 0.0478, 1.4349),
         "LeftForeArm": (0.4579, 0.0953, 1.4349), "LeftHand": (0.7154, 0.0193, 1.4349),
         "LeftUpLeg": (0.1144, 0.0002, 0.9007), "LeftLeg": (0.1144, 0.0002, 0.5191),
         "LeftFoot": (0.1144, 0.0762, 0.1376)}
print("\n=== 验证: 新骨head vs 用户标记 ===")
import math
bad = 0
for bn, mk in marks.items():
    b = arm_data.bones.get(bn)
    if not b: continue
    h = b.head_local
    d = math.sqrt((h.x-mk[0])**2 + (h.y-mk[1])**2 + (h.z-mk[2])**2)
    flag = " !!!" if d > 0.03 else ""
    if d > 0.03: bad += 1
    print(f"{bn}: ({h.x:.3f},{h.y:.3f},{h.z:.3f}) 差{d*100:.1f}cm{flag}")
# 手指抽查
for bn in ["LeftHandMiddle1", "LeftHandThumb1", "LeftHandPinky3"]:
    b = arm_data.bones.get(bn)
    if b:
        h = b.head_local
        print(f"{bn}: ({h.x:.3f},{h.y:.3f},{h.z:.3f})")
print(f"\n超标骨骼: {bad}")

bpy.ops.wm.save_mainfile(filepath=OUT)
print(f"保存: {OUT}")
print("EXTRACT_DONE")
