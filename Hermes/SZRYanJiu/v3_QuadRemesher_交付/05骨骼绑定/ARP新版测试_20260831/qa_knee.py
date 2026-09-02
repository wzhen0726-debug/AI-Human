import bpy
from mathutils import Vector
# 对比参考骨架 vs 我们骨架: 行走中膝盖(小腿head)的x轨迹
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\04_行走测试.blend")
arm = bpy.data.objects.get('MixamoSkeleton')
dg = bpy.context.evaluated_depsgraph_get()
bpy.ops.import_scene.fbx(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx")
walk_arm = next(o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm)

def knee_x(arm_obj, name, dg):
    ae = arm_obj.evaluated_get(dg)
    pb = ae.pose.bones.get(name) or ae.pose.bones.get('mixamorig:'+name)
    return (arm_obj.matrix_world @ pb.head).x

print("帧 | 我们右膝x | 参考右膝x | 差(cm)")
for f in range(1, 34, 4):
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    our = knee_x(arm, 'RightLeg', dg)
    ref = knee_x(walk_arm, 'mixamorig:RightLeg', dg)
    print(f"{f:3d} | {our:.3f} | {ref:.3f} | {(our-ref)*100:+.1f}")
