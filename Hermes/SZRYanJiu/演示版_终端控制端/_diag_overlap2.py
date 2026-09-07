"""对比: Mixamo官方T-Pose骨架 vs 我们骨架的关节连接情况
关键: use_connect=False不代表位置断开(可以是位置重叠但可分离移动)
真正的标准: head位置是否=父骨tail位置(位置重叠/相接)"""
import bpy
from mathutils import Vector

def joint_info(arm, label):
    print(f"\n===== {label} =====")
    mw = arm.matrix_world
    joints = [
        ('mixamorig:Hips', 'mixamorig:LeftUpLeg', '骨盆→大腿根'),
        ('mixamorig:Hips', 'mixamorig:Spine', '骨盆→脊柱'),
        ('mixamorig:Spine2', 'mixamorig:LeftShoulder', '胸椎→左肩'),
        ('mixamorig:LeftUpLeg', 'mixamorig:LeftLeg', '大腿→小腿(膝)'),
        ('mixamorig:LeftLeg', 'mixamorig:LeftFoot', '小腿→脚(踝)'),
        ('mixamorig:LeftShoulder', 'mixamorig:LeftArm', '肩→大臂'),
        ('mixamorig:LeftArm', 'mixamorig:LeftForeArm', '大臂→小臂(肘)'),
        ('mixamorig:LeftHand', 'mixamorig:LeftHandIndex1', '手掌→食指'),
    ]
    for pn, cn, desc in joints:
        p, c = arm.data.bones.get(pn), arm.data.bones.get(cn)
        if not p or not c:
            print(f"  {desc}: 骨名不存在(p={pn in arm.data.bones}, c={cn in arm.data.bones})")
            continue
        ptail = mw @ p.tail_local
        chead = mw @ c.head_local
        d = (ptail - chead).length * 1000
        status = "相接" if d < 2 else ("间隙" if d < 20 else "断开")
        print(f"  {desc:18s} {status:4s} {d:7.2f}mm  connect={c.use_connect}")

# Mixamo官方参考
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\T-Pose.fbx")
ref = next(o for o in bpy.data.objects if o.type=='ARMATURE')
joint_info(ref, "Mixamo官方T-Pose参考骨架")

# 我们的骨架
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付\05骨骼绑定\ARP新版测试_20260831\03_骨骼绑定.blend")
our = next(o for o in bpy.data.objects if o.type=='ARMATURE')
joint_info(our, "我们的03_骨骼绑定")
print("\nDONE")
