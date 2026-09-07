"""对比: Mixamo官方T-Pose骨架 vs 我们骨架, 关节点 head/tail 是否重合
用户质疑: Mixamo的关节点是重叠且完整连接的. 验证真相."""
import bpy
from mathutils import Vector

def check(arm, label):
    print(f"\n=== {label} ===")
    mw = arm.matrix_world
    joints = [
        ('mixamorig:Hips', 'mixamorig:LeftUpLeg'),      # 骨盆→左腿
        ('mixamorig:Hips', 'mixamorig:RightUpLeg'),     # 骨盆→右腿
        ('mixamorig:Spine2', 'mixamorig:LeftShoulder'), # 胸椎→左肩
        ('mixamorig:Spine2', 'mixamorig:RightShoulder'),# 胸椎→右肩
        ('mixamorig:LeftUpLeg', 'mixamorig:LeftLeg'),   # 大腿→小腿
        ('mixamorig:LeftHand', 'mixamorig:LeftHandIndex1'), # 手掌→食指根
    ]
    for pn, cn in joints:
        p, c = arm.data.bones.get(pn), arm.data.bones.get(cn)
        if not p or not c: continue
        ptail = mw @ p.tail_local
        chead = mw @ c.head_local
        d = (ptail - chead).length * 1000
        print(f"  {pn}.tail → {cn}.head: 间距 {d:.2f}mm  connect={c.use_connect}")

# Mixamo官方
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\T-Pose.fbx")
ref = next(o for o in bpy.data.objects if o.type=='ARMATURE')
check(ref, "Mixamo官方T-Pose参考骨架")

# 我们骨架(03骨骼绑定)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付\05骨骼绑定\ARP新版测试_20260831\03_骨骼绑定.blend")
our = next(o for o in bpy.data.objects if o.type=='ARMATURE')
check(our, "我们的03_骨骼绑定")
print("\nDONE")
