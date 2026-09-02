import bpy
from mathutils import Vector
# 对比: 参考行走骨架(FBX导入的walk arm) vs 我们骨架 在腾空帧的高度
# 重新打开04, walk_arm已被删, 改为重新导入FBX对比
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\03_骨骼绑定.blend")
arm = bpy.data.objects.get('MixamoSkeleton')
mw = arm.matrix_world

# 导入行走FBX, 不动画我们骨架, 只看参考骨架在腾空帧的脚底位置
bpy.ops.import_scene.fbx(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx")
walk_arm = next(o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm)
wm = walk_arm.matrix_world
print("参考骨架:", walk_arm.name)
print("帧 | 参考L踝z | 参考R踝z | 参考Hips_z")
for f in [1, 4, 8, 12, 18, 24, 28]:
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    for bn in ['mixamorig:LeftFoot','mixamorig:RightFoot','mixamorig:Hips']:
        pb = walk_arm.pose.bones.get(bn)
    lh = (wm @ walk_arm.pose.bones['mixamorig:LeftFoot'].head).z
    rh = (wm @ walk_arm.pose.bones['mixamorig:RightFoot'].head).z
    hp = (wm @ walk_arm.pose.bones['mixamorig:Hips'].head).z
    print(f"{f:3d} | L{lh:.3f} | R{rh:.3f} | Hips{hp:.3f}")
print()
print("参考骨架 Hips 静止位置:", [round(v,3) for v in (wm @ walk_arm.data.bones['mixamorig:Hips'].head_local)])
print("我们骨架 Hips 静止位置:", [round(v,3) for v in (mw @ arm.data.bones['mixamorig:Hips'].head_local)])
print("参考 LeftFoot 静止head:", [round(v,3) for v in (wm @ walk_arm.data.bones['mixamorig:LeftFoot'].head_local)])
print("我们 LeftFoot 静止head:", [round(v,3) for v in (mw @ arm.data.bones['mixamorig:LeftFoot'].head_local)])
