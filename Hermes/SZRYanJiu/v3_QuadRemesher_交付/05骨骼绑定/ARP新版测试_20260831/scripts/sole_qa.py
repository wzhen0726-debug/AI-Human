"""多动画贴地质量精查: 区分"该腾空的离地期"和"不该腾空的支撑期"
跳跃/跑步的离地期双脚腾空是正常的; 支撑期(至少一脚该落地)没落地才是问题。
判定: 参考骨架该帧的脚底高度——若参考该帧也离地, 则是离地期(正常); 若参考贴地而我们腾空, 才是错误。
"""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831"
ANIM_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件"
OUT = os.path.join(BASE, "多动画测试")

ANIMS = [
    ("anim_StandardWalk.blend", "Standard Walk.fbx"),
    ("anim_Running.blend", "Running.fbx"),
    ("anim_Jump.blend", "Jump.fbx"),
]

for blend_name, fbx_name in ANIMS:
    print(f"\n=== {blend_name} ===")
    bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, blend_name))
    arm = bpy.data.objects.get('MixamoSkeleton')
    body = max((o for o in bpy.data.objects if o.type=='MESH' and o.name!='MixamoSkeleton'), key=lambda o: len(o.data.vertices))
    # 参考骨架
    bpy.ops.import_scene.fbx(filepath=os.path.join(ANIM_DIR, fbx_name))
    walk_arm = next((o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm and o.animation_data), None)
    wm_ref = walk_arm.matrix_world
    lf_i = {g.index for g in body.vertex_groups if 'LeftFoot' in g.name or 'LeftToe' in g.name}
    rf_i = {g.index for g in body.vertex_groups if 'RightFoot' in g.name or 'RightToe' in g.name}
    dg = bpy.context.evaluated_depsgraph_get()
    scn = bpy.context.scene
    wrong = 0  # 支撑期没贴地的错误帧
    airborne = 0  # 离地期(正常腾空)
    for f in range(scn.frame_start, scn.frame_end+1):
        scn.frame_set(f); bpy.context.view_layer.update()
        # 参考脚底高度
        ref_l = (wm_ref @ walk_arm.evaluated_get(dg).pose.bones['mixamorig:LeftFoot'].head).z
        ref_r = (wm_ref @ walk_arm.evaluated_get(dg).pose.bones['mixamorig:RightFoot'].head).z
        ref_sole = min(ref_l, ref_r)  # 参考最低脚
        vs = body.evaluated_get(dg).data.vertices
        lmin = min((v.co.z for v in vs if any(g.group in lf_i and g.weight>0.1 for g in v.groups)), default=9)
        rmin = min((v.co.z for v in vs if any(g.group in rf_i and g.weight>0.1 for g in v.groups)), default=9)
        our_sole = min(lmin, rmin)
        # 参考贴地(踝<0.15)但我们腾空(脚>0.05) → 错误
        if ref_sole < 0.15 and our_sole > 0.05:
            wrong += 1
        elif ref_sole >= 0.15:
            airborne += 1
    print(f"  支撑期腾空错误: {wrong}帧 | 离地期(正常): {airborne}帧")

print("\n========== SOLE_QA_DONE ==========")
