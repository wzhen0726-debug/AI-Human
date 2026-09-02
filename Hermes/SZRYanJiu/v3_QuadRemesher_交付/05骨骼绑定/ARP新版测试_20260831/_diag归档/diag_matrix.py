import bpy
from mathutils import Vector
# 思路: walk FBX骨架(参考)腿长0.893, 我们0.783。把参考骨架动画的"Hips位移"按正确坐标系转换+缩放。
# 关键认知: 参考骨架物体scale=0.01(cm→m), Hips局部y=前进, z=垂直。
# 我们骨架scale=1, Hips局部y=?(需查), 由align_roll对齐了Mixamo的z轴, 但head/tail位置是ARP的。
#
# 最稳的重定向: 不搬fcurve, 而是逐帧读取参考骨架每根骨的世界旋转矩阵,
# 转成我们骨架对应骨的局部旋转并keyframe。Hips额外加世界位移(缩放+坐标转换)。
bpy.ops.wm.read_factory_settings(use_empty=True)

# 打开我们的绑定
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\03_骨骼绑定.blend")
arm = bpy.data.objects.get('MixamoSkeleton')
body = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))

# 导入参考行走FBX
bpy.ops.import_scene.fbx(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx")
walk_arm = next(o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm)

# 打印两边Hips的matrix_local(含朝向)用于坐标转换
def bone(arm_obj, name):
    return arm_obj.data.bones.get(name) or arm_obj.data.bones.get('mixamorig:'+name)
def pbone(arm_obj, name):
    return arm_obj.pose.bones.get(name) or arm_obj.pose.bones.get('mixamorig:'+name)
print("我们Hips matrix_local:\n", bone(arm,'Hips').matrix_local)
print("参考Hips matrix_local:\n", bone(walk_arm,'Hips').matrix_local)
print("参考骨架scale:", walk_arm.scale[:])
print("我们骨架scale:", arm.scale[:])
# 测: 参考骨架帧8 Hips世界位置
dg = bpy.context.evaluated_depsgraph_get()
bpy.context.scene.frame_set(8); bpy.context.view_layer.update()
ae = walk_arm.evaluated_get(dg)
print("参考帧8 Hips世界:", [round(v,3) for v in (walk_arm.matrix_world @ pbone(walk_arm,'Hips').head)])
print("参考帧8 RightFoot世界z:", round((walk_arm.matrix_world @ pbone(walk_arm,'RightFoot').head).z,3))
