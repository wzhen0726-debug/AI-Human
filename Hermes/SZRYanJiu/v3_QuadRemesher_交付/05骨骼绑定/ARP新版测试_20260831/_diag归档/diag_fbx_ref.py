import bpy
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx")
walk_arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
wm = walk_arm.matrix_world
print("参考骨架物体scale:", [round(v,4) for v in walk_arm.scale])
print("参考骨架物体matrix_world对角:", [round(wm[i][i],4) for i in range(3)])

print("\n=== 参考骨架 REST 腿长(世界) ===")
for n in ['mixamorig:Hips','mixamorig:LeftUpLeg','mixamorig:LeftLeg','mixamorig:LeftFoot','mixamorig:LeftToeBase']:
    b = walk_arm.data.bones.get(n)
    if b:
        h = wm @ b.head_local
        print(f"{n}: z={h.z:.3f} x={h.x:.3f}")

print("\n=== 参考骨架 行走各帧脚底(应用动画) ===")
dg = bpy.context.evaluated_depsgraph_get()
for f in [1, 4, 8, 12, 14]:
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    wa_ev = walk_arm.evaluated_get(dg)
    lh = (wm @ wa_ev.pose.bones['mixamorig:LeftFoot'].head).z
    rh = (wm @ wa_ev.pose.bones['mixamorig:RightFoot'].head).z
    lt = (wm @ wa_ev.pose.bones['mixamorig:LeftToeBase'].head).z
    rt = (wm @ wa_ev.pose.bones['mixamorig:RightToeBase'].head).z
    print(f"帧{f}: L踝{lh:.3f} L趾{lt:.3f} | R踝{rh:.3f} R趾{rt:.3f}")
