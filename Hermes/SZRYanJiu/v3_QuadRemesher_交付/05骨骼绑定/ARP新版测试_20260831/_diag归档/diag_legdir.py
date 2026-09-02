import bpy
from mathutils import Vector
# 对比: 同一帧, 参考骨架腿骨世界方向 vs 我们骨架腿骨世界方向
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\03_骨骼绑定.blend")
arm = bpy.data.objects.get('MixamoSkeleton')
# 套用之前保存的行走action(04里已有), 重新跑步骤7的动作绑定太绕, 直接打开04
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\04_行走测试.blend")
arm = bpy.data.objects.get('MixamoSkeleton')
dg = bpy.context.evaluated_depsgraph_get()

# 参考骨架
bpy.ops.import_scene.fbx(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx")
walk_arm = next(o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm)

def wdir(arm_obj, name, dg):
    ae = arm_obj.evaluated_get(dg)
    pb = ae.pose.bones.get(name) or ae.pose.bones.get('mixamorig:'+name)
    mw = arm_obj.matrix_world
    d = (mw @ pb.tail) - (mw @ pb.head)
    return d.normalized(), (mw @ pb.head)

f = 8
bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
print(f"=== 帧{f} 腿骨世界方向对比 ===")
for n in ['RightUpLeg','RightLeg','RightFoot']:
    d_our, h_our = wdir(arm, n, dg)
    d_ref, h_ref = wdir(walk_arm, n, dg)
    dot = d_our.dot(d_ref)
    print(f"{n}:")
    print(f"  我们 head=({h_our.x:.3f},{h_our.y:.3f},{h_our.z:.3f}) dir=({d_our.x:.3f},{d_our.y:.3f},{d_our.z:.3f})")
    print(f"  参考 head=({h_ref.x:.3f},{h_ref.y:.3f},{h_ref.z:.3f}) dir=({d_ref.x:.3f},{d_ref.y:.3f},{d_ref.z:.3f})")
    print(f"  方向点积={dot:.3f} (1=完全一致)")

# 静止rest方向对比
print("\n=== REST方向对比 ===")
for n in ['RightUpLeg','RightLeg','RightFoot']:
    b_our = arm.data.bones.get(n) or arm.data.bones.get('mixamorig:'+n)
    b_ref = walk_arm.data.bones.get(n) or walk_arm.data.bones.get('mixamorig:'+n)
    d_our = (arm.matrix_world @ b_our.tail_local) - (arm.matrix_world @ b_our.head_local)
    d_ref = (walk_arm.matrix_world @ b_ref.tail_local) - (walk_arm.matrix_world @ b_ref.head_local)
    print(f"{n}: 我们rest_dir=({d_our.normalized().x:.3f},{d_our.normalized().y:.3f},{d_our.normalized().z:.3f}) 参考rest_dir=({d_ref.normalized().x:.3f},{d_ref.normalized().y:.3f},{d_ref.normalized().z:.3f})")
