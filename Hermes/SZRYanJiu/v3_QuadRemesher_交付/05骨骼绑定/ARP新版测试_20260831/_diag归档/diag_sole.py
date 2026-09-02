import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\04_行走测试.blend")
arm = bpy.data.objects.get('MixamoSkeleton')
dg = bpy.context.evaluated_depsgraph_get()
bpy.ops.import_scene.fbx(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx")
walk_arm = next(o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm)

# 参考骨架mesh(行走FBX自带mesh)脚底z
ref_mesh = next((o for o in bpy.data.objects if o.type=='MESH'), None)
print("参考骨架自带mesh:", ref_mesh.name if ref_mesh else "无")

def foot_sole_z(arm_obj, dg):
    ae = arm_obj.evaluated_get(dg)
    mw = arm_obj.matrix_world
    out = {}
    for n in ['LeftFoot','LeftToeBase','LeftToe_End','RightFoot','RightToeBase','RightToe_End']:
        pb = ae.pose.bones.get(n) or ae.pose.bones.get('mixamorig:'+n)
        if pb: out[n] = (mw @ pb.tail).z  # tail=骨末端更贴脚底
    return out

for f in [1, 8, 14]:
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    our = foot_sole_z(arm, dg)
    ref = foot_sole_z(walk_arm, dg)
    print(f"\n帧{f}:")
    print(f"  我们脚底tail_z: R_Foot={our.get('RightFoot',0):.3f} R_Toe={our.get('RightToe_End',0):.3f} L_Foot={our.get('LeftFoot',0):.3f} L_Toe={our.get('LeftToe_End',0):.3f}")
    print(f"  参考脚底tail_z: R_Foot={ref.get('RightFoot',0):.3f} R_Toe={ref.get('RightToe_End',0):.3f} L_Foot={ref.get('LeftFoot',0):.3f} L_Toe={ref.get('LeftToe_End',0):.3f}")
