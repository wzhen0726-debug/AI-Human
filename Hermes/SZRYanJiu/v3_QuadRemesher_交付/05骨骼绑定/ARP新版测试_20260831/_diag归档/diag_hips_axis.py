import bpy
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\04_行走测试.blend")
arm = bpy.data.objects.get('MixamoSkeleton')
hips = arm.pose.bones['mixamorig:Hips']
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()
mw = arm.matrix_world
h0 = (mw @ hips.head).z
print("Hips 帧1 世界z(未动):", round(h0,4))
# 测: 局部y加0.1, 看世界z变化
for axis_name, idx in [('x',0),('y',1),('z',2)]:
    hips.location = Vector((0,0,0)); hips.location[idx] = 0.1
    bpy.context.view_layer.update()
    hz = (mw @ hips.head).z
    print(f"局部{axis_name}+0.1 → 世界z变化: {hz-h0:+.4f}")
hips.location = Vector((0,0,0))
bpy.context.view_layer.update()
