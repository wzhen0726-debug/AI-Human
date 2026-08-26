"""验证: walk_test_手写版.blend 播放动画时我们的mesh是否变形 + 骨骼位置对比交付版."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\B_骨骼绑定\walk_test_手写版.blend"
REF = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\B_骨骼绑定\06_rig_final.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

scn = bpy.context.scene
out = []

# 我们的mesh
body = bpy.data.objects.get("tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR")
rig = bpy.data.objects.get("MixamoSkeleton")

# 1) 第1帧基准顶点位置
scn.frame_set(1)
bpy.context.view_layer.update()
base = [v.co.copy() for v in body.data.vertices[:2000]]

# 2) 第18帧(走路中段)顶点位置
scn.frame_set(18)
bpy.context.view_layer.update()
moved = 0
maxd = 0.0
for i, v in enumerate(body.data.vertices[:2000]):
    d = (v.co - base[i]).length
    if d > 0.01: moved += 1
    if d > maxd: maxd = d

out.append(f"mesh变形: {moved}/2000 顶点移动>1cm, 最大 {maxd*100:.1f}cm")

# 3) 骨骼姿态: 第18帧时几个关键骨骼的旋转
for bn in ["mixamorig:LeftUpLeg", "mixamorig:RightArm", "mixamorig:Spine"]:
    try:
        pb = rig.pose.bones[bn]
        out.append(f"帧18 {bn}: 旋转 {tuple(round(r,1) for r in pb.rotation_euler)}")
    except KeyError:
        out.append(f"帧18 {bn}: 不存在")

# 4) rest位骨骼位置对比交付版(检查"骨骼都有问题")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=REF)
ref_rig = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE': ref_rig = o
ref_pos = {b.name: tuple(round(c,3) for c in b.head_local) for b in ref_rig.data.bones}

bpy.ops.wm.open_mainfile(filepath=BLEND)
rig = bpy.data.objects.get("MixamoSkeleton")  # 重开后重新获取引用
diffs = []
for b in rig.data.bones:
    if b.name in ref_pos:
        rp = ref_pos[b.name]
        d = max(abs(b.head_local[i]-rp[i]) for i in range(3))
        if d > 0.005:
            diffs.append(f"{b.name}: 偏移{d*100:.1f}cm ({tuple(round(c,3) for c in b.head_local)} vs {rp})")
out.append(f"骨骼位置与交付版偏差>5mm: {len(diffs)}根")
out.extend(diffs[:10])

out.append("VERIFY_DONE")
with open(r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\logs\walk_verify_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))