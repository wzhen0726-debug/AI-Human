import bpy
from mathutils import Vector
# 1) 参考骨架(原始FBX) 的 Hips location fcurve 原始值
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx")
walk_arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
print("=== 参考骨架 Hips location fcurve (局部空间) ===")
act = walk_arm.animation_data.action
for layer in act.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for fc in bag.fcurves:
                if 'Hips' in fc.data_path and 'location' in fc.data_path:
                    vals = [(int(kp.co[0]), round(kp.co[1],3)) for kp in fc.keyframe_points[:6]]
                    print(f"  轴{fc.array_index}: {vals}")
# 参考骨架Hips局部Y世界方向
b = walk_arm.data.bones['mixamorig:Hips']
wm = walk_arm.matrix_world
yl = (wm @ b.matrix_local).to_3x3() @ Vector((0,1,0))
print(f"参考Hips局部Y世界方向: ({yl.x:.3f},{yl.y:.3f},{yl.z:.3f})")
print(f"参考Hips 静止世界head: {[round(v,3) for v in (wm@b.head_local)]}")

# 各帧参考Hips世界z
dg = bpy.context.evaluated_depsgraph_get()
print("\n帧 | 参考Hips世界z")
for f in [1,3,5,8]:
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    ae = walk_arm.evaluated_get(dg)
    print(f"{f} | {(wm@ae.pose.bones['mixamorig:Hips'].head).z:.3f}")
