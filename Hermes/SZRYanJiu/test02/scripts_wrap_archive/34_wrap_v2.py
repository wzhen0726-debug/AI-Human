import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh
import numpy as np

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
ALIGNED_BLEND = os.path.join(ROOT, "output", "wrap", "aligned_v2.blend")
LANDMARK_BLEND = os.path.join(ROOT, "output", "landmark_scene_v6.blend")
OUT_BLEND = os.path.join(ROOT, "output", "wrap", "wrapped_v2.blend")

print("="*60)
print("Step 2: Shrinkwrap包裹（先用特征点对齐，再包裹躯干）")
print("="*60)

# 打开对齐后的场景
bpy.ops.wm.open_mainfile(filepath=ALIGNED_BLEND)

# 找到MetaHuman和Tripo
mh_body = None
tripo = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        if 'Body' in obj.name or 'MetaHuman' in obj.name:
            mh_body = obj
        elif 'Tripo' in obj.name or 'HighPoly' in obj.name:
            tripo = obj

if not mh_body:
    # 如果只有MetaHuman（aligned_v2只有MetaHuman）
    mh_body = bpy.data.objects[0] if bpy.data.objects else None

print(f"MetaHuman: {mh_body.name if mh_body else 'NOT FOUND'}")
print(f"Tripo: {tripo.name if tripo else 'NOT FOUND (需要导入)'}")

# 导入Tripo
if not tripo:
    print("导入Tripo...")
    # 读取特征点场景
    bpy.ops.wm.open_mainfile(filepath=LANDMARK_BLEND)
    tripo = None
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            tripo = obj
            break
    # 复制Tripo到新场景
    tripo_data = tripo.data.copy()
    tripo_name = tripo.name

    # 打开MetaHuman场景
    bpy.ops.wm.open_mainfile(filepath=ALIGNED_BLEND)
    mh_body = None
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            mh_body = obj
            break

    # 追加Tripo
    new_tripo = bpy.data.objects.new(tripo_name, tripo_data)
    bpy.context.collection.objects.link(new_tripo)
    tripo = new_tripo

print(f"\nMetaHuman: {mh_body.name}, {len(mh_body.data.vertices)} verts")
print(f"Tripo: {tripo.name}, {len(tripo.data.vertices)} verts")

# 读取特征点
# 从landmark_scene_v6读取
bpy.ops.wm.open_mainfile(filepath=LANDMARK_BLEND)
empties = [o for o in bpy.data.objects if o.type == 'EMPTY']
landmarks = {}
for e in empties:
    landmarks[e.name] = Vector((e.location.x, e.location.y, e.location.z))

# 重新打开对齐后的场景
bpy.ops.wm.open_mainfile(filepath=ALIGNED_BLEND)
mh_body = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        mh_body = obj
        break

# 导入Tripo
bpy.ops.import_scene.gltf(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\AI生成高模\02_tripoTpose\raw_model.glb")
tripo = None
for obj in bpy.data.objects:
    if obj.type == 'MESH' and obj != mh_body:
        tripo = obj
        break

# 旋转Tripo（三步）
for axis in ['X', 'Z', 'Y']:
    tripo.matrix_basis = Matrix.Rotation(math.radians(-90), 4, axis) @ tripo.matrix_basis
    bpy.context.view_layer.update()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 缩放Tripo到1.8m
tripo_zs = [v.co.z for v in tripo.data.vertices]
tripo_height = max(tripo_zs) - min(tripo_zs)
scale = 1.8 / tripo_height
tripo.scale = (scale, scale, scale)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 居中+接地
tripo_xs = [v.co.x for v in tripo.data.vertices]
tripo_ys = [v.co.y for v in tripo.data.vertices]
tripo_zs = [v.co.z for v in tripo.data.vertices]
cx = (min(tripo_xs) + max(tripo_xs)) / 2
cy = (min(tripo_ys) + max(tripo_ys)) / 2
cz_min = min(tripo_zs)
tripo.location = (-cx, -cy, -cz_min)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

print(f"\nTripo bbox: X[{min(v.co.x for v in tripo.data.vertices):.2f},{max(v.co.x for v in tripo.data.vertices):.2f}] Y[{min(v.co.y for v in tripo.data.vertices):.2f},{max(v.co.y for v in tripo.data.vertices):.2f}] Z[{min(v.co.z for v in tripo.data.vertices):.2f},{max(v.co.z for v in tripo.data.vertices):.2f}]")

# 用特征点对齐MetaHuman到Tripo
# Tripo特征点（从用户打点）
tripo_lm = {
    'head_top': Vector((0, -0.02, 1.796)),
    'chin': Vector((0, -0.104, 1.547)),
    'chest': Vector((0, -0.112, 1.330)),
    'pelvis': Vector((0, -0.108, 0.895)),
    'shoulder_L': Vector((-0.210, 0.043, 1.504)),
    'shoulder_R': Vector((0.204, 0.043, 1.505)),
    'knee_L': Vector((-0.137, -0.026, 0.496)),
    'ankle_L': Vector((-0.142, 0.022, 0.107)),
}

# MetaHuman特征点（通过bbox比例估算）
mh_zs = [v.co.z for v in mh_body.data.vertices]
mh_max_z = max(mh_zs)
mh_min_z = min(mh_zs)
mh_height = mh_max_z - mh_min_z

mh_lm = {
    'head_top': Vector((0, -0.02, mh_max_z)),
    'chin': Vector((0, -0.08, mh_min_z + mh_height * 0.86)),
    'chest': Vector((0, -0.08, mh_min_z + mh_height * 0.74)),
    'pelvis': Vector((0, -0.04, mh_min_z + mh_height * 0.50)),
    'shoulder_L': Vector((-0.20, 0.0, mh_min_z + mh_height * 0.83)),
    'shoulder_R': Vector((0.20, 0.0, mh_min_z + mh_height * 0.83)),
    'knee_L': Vector((-0.12, -0.02, mh_min_z + mh_height * 0.28)),
    'ankle_L': Vector((-0.12, -0.02, mh_min_z + mh_height * 0.03)),
}

# 对齐：用头部和脚部缩放
tripo_head_z = tripo_lm['head_top'].z
tripo_foot_z = tripo_lm['ankle_L'].z
tripo_body_h = tripo_head_z - tripo_foot_z

mh_head_z = mh_lm['head_top'].z
mh_foot_z = mh_lm['ankle_L'].z
mh_body_h = mh_head_z - mh_foot_z

scale_z = tripo_body_h / mh_body_h
print(f"\n缩放: {scale_z:.3f} (Tripo {tripo_body_h:.3f}m / MH {mh_body_h:.3f}m)")
mh_body.scale = (scale_z, scale_z, scale_z)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 平移：脚部对齐
mh_zs = [v.co.z for v in mh_body.data.vertices]
mh_foot_z_new = min(mh_zs)
mh_body.location.z = tripo_foot_z - mh_foot_z_new
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# X/Y居中
mh_body.location.x = -sum(v.co.x for v in mh_body.data.vertices) / len(mh_body.data.vertices)
mh_body.location.y = -sum(v.co.y for v in mh_body.data.vertices) / len(mh_body.data.vertices)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 验证对齐
mh_zs = [v.co.z for v in mh_body.data.vertices]
print(f"\n对齐后MetaHuman: Z[{min(mh_zs):.2f}, {max(mh_zs):.2f}]")
print(f"Tripo: Z[0.00, 1.80]")

# ============================================================
# Shrinkwrap包裹
# ============================================================
print("\n" + "="*60)
print("Shrinkwrap包裹")
print("="*60)

bpy.context.view_layer.objects.active = mh_body
mh_body.select_set(True)

sw = mh_body.modifiers.new(name="Shrinkwrap", type='SHRINKWRAP')
sw.target = tripo
sw.wrap_method = 'NEAREST_SURFACEPOINT'
sw.wrap_mode = 'ON_SURFACE'
sw.use_keep_above_surface = True

bpy.ops.object.modifier_apply(modifier="Shrinkwrap")

# 统计包裹精度
mh_verts = np.array([[v.co.x, v.co.y, v.co.z] for v in mh_body.data.vertices])
tripo_bvh = None
from mathutils.bvhtree import BVHTree

# 构建Tripo BVH
tripo_mesh = tripo.data
tripo_matrix = tripo.matrix_world
tripo_verts = [tripo_matrix @ v.co for v in tripo_mesh.vertices]
tripo_faces = [list(p.vertices) for p in tripo_mesh.polygons]
tripo_bvh = BVHTree.FromPolygons(tripo_verts, tripo_faces)

# 计算每个MetaHuman顶点到Tripo的距离
distances = []
for v in mh_body.data.vertices:
    wp = mh_body.matrix_world @ v.co
    nearest, _, _, _ = tripo_bvh.find_nearest(wp)
    if nearest:
        d = (wp - nearest).length
        distances.append(d)

distances = np.array(distances)
print(f"\n包裹精度:")
print(f"  平均: {np.mean(distances)*1000:.2f}mm")
print(f"  中位数: {np.median(distances)*1000:.2f}mm")
print(f"  <1mm: {np.mean(distances < 0.001)*100:.1f}%")
print(f"  <2mm: {np.mean(distances < 0.002)*100:.1f}%")
print(f"  <5mm: {np.mean(distances < 0.005)*100:.1f}%")
print(f"  最大: {np.max(distances)*1000:.2f}mm")

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"\n保存: {OUT_BLEND}")
print("DONE")
