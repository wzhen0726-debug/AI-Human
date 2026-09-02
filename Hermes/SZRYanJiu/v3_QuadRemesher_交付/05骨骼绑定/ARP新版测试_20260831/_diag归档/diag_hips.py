import bpy
arm = bpy.data.objects.get('MixamoSkeleton')
mw = arm.matrix_world
dg = bpy.context.evaluated_depsgraph_get()
print("=== 重映射后 04_行走测试.blend ===")
print("Hips骨 静止roll检查: 局部y轴世界方向")
b = arm.data.bones['mixamorig:Hips']
yl = (mw @ b.matrix_local).to_3x3() @ __import__('mathutils').Vector((0,1,0))
print(f"  Hips局部Y世界方向: ({yl.x:.3f},{yl.y:.3f},{yl.z:.3f})")
print("帧 | Hips世界z | L踝z | R踝z")
for f in [1, 4, 8, 12, 14]:
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    ae = arm.evaluated_get(dg)
    hp = (mw @ ae.pose.bones['mixamorig:Hips'].head).z
    lh = (mw @ ae.pose.bones['mixamorig:LeftFoot'].head).z
    rh = (mw @ ae.pose.bones['mixamorig:RightFoot'].head).z
    print(f"{f:3d} | Hips{hp:.3f} | L{lh:.3f} | R{rh:.3f}")
# 查Hips location fcurve 实际值
act = arm.animation_data.action
print("\nHips location fcurves:")
for layer in act.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for fc in bag.fcurves:
                if 'mixamorig:Hips' in fc.data_path and 'location' in fc.data_path:
                    vals = [round(kp.co[1],3) for kp in fc.keyframe_points[:5]]
                    print(f"  轴{fc.array_index}: 前5帧值={vals}")
