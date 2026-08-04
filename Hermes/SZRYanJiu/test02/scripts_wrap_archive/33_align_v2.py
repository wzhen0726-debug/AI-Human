import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh
import numpy as np

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
LANDMARK_BLEND = os.path.join(ROOT, "output", "landmark_scene_v6.blend")
MH_BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\Metahuman_Low_01.blend"
OUT_BLEND = os.path.join(ROOT, "output", "wrap", "aligned_v2.blend")
os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)

print("="*60)
print("Step 1: 读取特征点 + 导入MetaHuman + 对齐")
print("="*60)

# 读取特征点
bpy.ops.wm.open_mainfile(filepath=LANDMARK_BLEND)
empties = [o for o in bpy.data.objects if o.type == 'EMPTY']
landmarks = {}
for e in empties:
    landmarks[e.name] = (e.location.x, e.location.y, e.location.z)
    print(f"  {e.name}: ({e.location.x:.3f}, {e.location.y:.3f}, {e.location.z:.3f})")

# 计算Tripo特征点质心
tripo_pts = []
for name, loc in landmarks.items():
    tripo_pts.append(Vector(loc))
tripo_center = sum(tripo_pts, Vector()) / len(tripo_pts)
print(f"\nTripo特征点质心: ({tripo_center.x:.3f}, {tripo_center.y:.3f}, {tripo_center.z:.3f})")

# 导入MetaHuman
print("\n导入MetaHuman...")
bpy.ops.wm.open_mainfile(filepath=MH_BLEND)
mh_body = None
for obj in bpy.data.objects:
    if obj.type == 'MESH' and 'Body' in obj.name:
        mh_body = obj
        break
if not mh_body:
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            mh_body = obj
            break

print(f"MetaHuman: {mh_body.name}, {len(mh_body.data.vertices)} verts")

# cm→m转换
for v in mh_body.data.vertices:
    v.co = v.co * 0.01
bpy.context.view_layer.update()

# MetaHuman bbox
mh_xs = [v.co.x for v in mh_body.data.vertices]
mh_ys = [v.co.y for v in mh_body.data.vertices]
mh_zs = [v.co.z for v in mh_body.data.vertices]
mh_bbox = {
    'min': Vector((min(mh_xs), min(mh_ys), min(mh_zs))),
    'max': Vector((max(mh_xs), max(mh_ys), max(mh_zs))),
}
mh_height = mh_bbox['max'].z - mh_bbox['min'].z
print(f"MetaHuman身高: {mh_height:.3f}m")

# 绕Z轴-90°旋转MetaHuman使坐标系一致
mh_body.matrix_basis = Matrix.Rotation(math.radians(-90), 4, 'Z') @ mh_body.matrix_basis
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 缩放到Tripo身高
mh_xs = [v.co.x for v in mh_body.data.vertices]
mh_ys = [v.co.y for v in mh_body.data.vertices]
mh_zs = [v.co.z for v in mh_body.data.vertices]
mh_height = max(mh_zs) - min(mh_zs)
tripo_height = 1.8
scale = tripo_height / mh_height
mh_body.scale = (scale, scale, scale)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 计算MetaHuman特征点（基于标准人体比例）
mh_xs = [v.co.x for v in mh_body.data.vertices]
mh_ys = [v.co.y for v in mh_body.data.vertices]
mh_zs = [v.co.z for v in mh_body.data.vertices]
mh_center = Vector((
    sum(mh_xs)/len(mh_xs),
    sum(mh_ys)/len(mh_ys),
    (min(mh_zs) + max(mh_zs))/2
))
mh_min_z = min(mh_zs)
mh_max_z = max(mh_zs)

# MetaHuman特征点（标准比例）
mh_landmarks = {
    'head_top': Vector((0, -0.02, mh_max_z * 0.99)),
    'chin': Vector((0, -0.08, mh_max_z * 0.86)),
    'chest': Vector((0, -0.08, mh_max_z * 0.74)),
    'abdomen': Vector((0, -0.06, mh_max_z * 0.60)),
    'back': Vector((0, 0.08, mh_max_z * 0.74)),
    'pelvis': Vector((0, -0.04, mh_max_z * 0.50)),
    'shoulder_L': Vector((-0.20, 0.0, mh_max_z * 0.83)),
    'elbow_L': Vector((-0.45, 0.0, mh_max_z * 0.83)),
    'wrist_L': Vector((-0.70, 0.0, mh_max_z * 0.83)),
    'shoulder_R': Vector((0.20, 0.0, mh_max_z * 0.83)),
    'elbow_R': Vector((0.45, 0.0, mh_max_z * 0.83)),
    'wrist_R': Vector((0.70, 0.0, mh_max_z * 0.83)),
    'knee_L': Vector((-0.12, -0.02, mh_max_z * 0.28)),
    'ankle_L': Vector((-0.12, -0.02, mh_max_z * 0.03)),
    'knee_R': Vector((0.12, -0.02, mh_max_z * 0.28)),
    'ankle_R': Vector((0.12, -0.02, mh_max_z * 0.03)),
}

# 对齐：用特征点质心对齐
mh_center2 = sum(mh_landmarks.values(), Vector()) / len(mh_landmarks)
offset = tripo_center - mh_center2
mh_body.location = offset
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 验证对齐
mh_xs2 = [v.co.x for v in mh_body.data.vertices]
mh_ys2 = [v.co.y for v in mh_body.data.vertices]
mh_zs2 = [v.co.z for v in mh_body.data.vertices]
print(f"\n对齐后MetaHuman bbox: X[{min(mh_xs2):.2f},{max(mh_xs2):.2f}] Y[{min(mh_ys2):.2f},{max(mh_ys2):.2f}] Z[{min(mh_zs2):.2f},{max(mh_zs2):.2f}]")

# 保存
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"\n保存: {OUT_BLEND}")
print("DONE")
