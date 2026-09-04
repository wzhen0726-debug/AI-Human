"""03_mixamo_rest.blend 生成: 骨架rest朝向归一化为Mixamo标准 (2026-09-04 用户方案第一步)

目的: 把我们骨架的rest姿态改成与Mixamo相同, 之后动画绑定可直接复制局部旋转。
方法: 编辑模式只改骨骼朝向(头位置不动, 保持用户打点位置与角色形状):
  目标世界朝向 = 我们Hips朝向 @ (参考Hips朝向^-1 @ 参考骨朝向)  [锚Hips, 纯旋转]
  所有量全部实测(锚用户提供的T-Pose.fbx), 无写死参数——下个模型若rest本就标准,
  差异≈0, 自动等于不改。
已实证(2026-09-04): 编辑模式改朝向 头位置0位移/网格0位移/子骨头0位移。
注意: 改朝向前必须断开连接骨(use_connect), 否则旋转父骨拖动子骨头位置。
朝向对齐后不恢复连接(恢复会把子骨头拖回父骨tail, 破坏打点位置)。

用法: blender -b --python scripts/normalize_rest.py
"""
import bpy, os, math
from mathutils import Matrix, Quaternion

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831"
RIG = os.path.join(BASE, "03_骨骼绑定.blend")
ANIM_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件"
OUT = os.path.join(BASE, "03_mixamo_rest.blend")
THRESH = math.radians(0.5)  # 朝向差>0.5°才改(测量阈值, 差异≈0的模型自动跳过)

def qdiff(a, b):
    b2 = b.copy()
    if a.dot(b2) < 0: b2.negate()
    return a.rotation_difference(b2).angle

bpy.ops.wm.open_mainfile(filepath=RIG)
arm = bpy.data.objects.get('MixamoSkeleton')
body = next(o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('tripo'))
for b in arm.data.bones:
    if not b.name.startswith("mixamorig:"): b.name = "mixamorig:" + b.name
for vg in body.vertex_groups:
    if not vg.name.startswith("mixamorig:"): vg.name = "mixamorig:" + vg.name

dg = bpy.context.evaluated_depsgraph_get()
bpy.context.view_layer.update()
heads_before = {b.name: (arm.matrix_world @ b.matrix_local).translation.copy() for b in arm.data.bones}
vs_before = [v.co.copy() for v in body.evaluated_get(dg).data.vertices]

# ===== 导入参考, 算每骨目标世界朝向 =====
bpy.ops.import_scene.fbx(filepath=os.path.join(ANIM_DIR, "T-Pose.fbx"))
ref = next(o for o in bpy.data.objects if o.type=='ARMATURE' and o != arm)
assert ref, "T-Pose.fbx导入失败"
wm_ref = ref.matrix_world
ref_w = {b.name: wm_ref @ b.matrix_local for b in ref.data.bones}
H_r_rot = ref_w['mixamorig:Hips'].to_quaternion()
H_o_rot = (arm.matrix_world @ arm.data.bones['mixamorig:Hips'].matrix_local).to_quaternion()
target_rot = {}
for b in arm.data.bones:
    if b.name not in ref_w: continue
    target_rot[b.name] = H_o_rot @ (H_r_rot.inverted() @ ref_w[b.name].to_quaternion())

diffs = []
for b in arm.data.bones:
    if b.name not in target_rot: continue
    cur = (arm.matrix_world @ b.matrix_local).to_quaternion()
    diffs.append((qdiff(cur, target_rot[b.name]), b.name))
diffs.sort(reverse=True)
n_fix = sum(1 for d, _ in diffs if d > THRESH)
print(f"逐骨rest朝向差实测: 最大{math.degrees(diffs[0][0]):.2f}°({diffs[0][1]}) "
      f"平均{math.degrees(sum(d for d,_ in diffs)/len(diffs)):.2f}° 需校正(>0.5°): {n_fix}/{len(diffs)}骨")
for d, n in diffs[:6]:
    print(f"  {n}: {math.degrees(d):.2f}°")

# ===== 编辑模式: 断开连接 → 旋转朝向(头不动) =====
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
n_conn = sum(1 for eb in arm.data.edit_bones if eb.use_connect)
for eb in arm.data.edit_bones:
    eb.use_connect = False
n_done = 0
for eb in arm.data.edit_bones:
    if eb.name not in target_rot: continue
    cur_q = eb.matrix.to_quaternion()  # armature空间当前朝向
    tgt_q = arm.matrix_world.to_quaternion().inverted() @ target_rot[eb.name]  # 世界→armature空间
    if qdiff(cur_q, tgt_q) <= THRESH:
        continue
    head = eb.head.copy()
    eb.matrix = Matrix.Translation(head) @ tgt_q.to_matrix().to_4x4()
    n_done += 1
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()
print(f"断开连接骨: {n_conn}根, 旋转校正: {n_done}骨 (头位置保持)")

# ===== 验证 =====
max_d, worst = 0.0, ''
for b in arm.data.bones:
    if b.name not in target_rot: continue
    cur = (arm.matrix_world @ b.matrix_local).to_quaternion()
    d = qdiff(cur, target_rot[b.name])
    if d > max_d: max_d, worst = d, b.name
print(f"应用后朝向残余差最大: {math.degrees(max_d):.3f}°({worst}) {'OK' if max_d < 0.01 else 'FAIL'}")
max_h = max(((arm.matrix_world @ arm.data.bones[n].matrix_local).translation - heads_before[n]).length for n in heads_before)
print(f"头位置最大位移: {max_h*1000:.3f}mm {'OK' if max_h < 0.001 else 'FAIL'}")
vs_after = [v.co.copy() for v in body.evaluated_get(dg).data.vertices]
vmax = max((a-b).length for a, b in zip(vs_before, vs_after))
print(f"rest网格最大位移: {vmax*1000:.3f}mm {'OK' if vmax < 0.001 else 'FAIL'}")
assert max_d < 0.01 and max_h < 0.001 and vmax < 0.001, "rest归一化失败!"

# 清参考残留
keep = {arm.name, body.name, 'Eye002_L', 'Eye002_R'}
for o in list(bpy.data.objects):
    if o.name not in keep:
        bpy.data.objects.remove(o, do_unlink=True)

bpy.ops.wm.save_mainfile(filepath=OUT)
print(f"已保存: {OUT}")
print("========== NORMALIZE_DONE ==========")
