import bpy, os, sys, math
from mathutils import Vector, Matrix
import numpy as np
from mathutils.bvhtree import BVHTree

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
MH_BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\Metahuman_Low_01.blend"
GLB_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\AI生成高模\02_tripoTpose\raw_model.glb"
OUT_BLEND = os.path.join(ROOT, "output", "wrap", "wrapped_v3.blend")
TMP_MH = os.path.join(ROOT, "output", "wrap", "tmp_mh_body.blend")

print("="*60)
print("Shrinkwrap包裹 v3（修复版）")
print("="*60)

# ============================================================
# Step 1: 在干净场景中导入Tripo并旋转
# ============================================================
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

print("导入Tripo...")
bpy.ops.import_scene.gltf(filepath=GLB_PATH)
tripo = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        tripo = obj
        break
tripo.name = "Tripo"
bpy.context.view_layer.objects.active = tripo
tripo.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

for axis in ['X', 'Z', 'Y']:
    tripo.matrix_basis = Matrix.Rotation(math.radians(-90), 4, axis) @ tripo.matrix_basis
    bpy.context.view_layer.update()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

zs = [v.co.z for v in tripo.data.vertices]
scale = 1.8 / (max(zs) - min(zs))
tripo.scale = (scale, scale, scale)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

xs = [v.co.x for v in tripo.data.vertices]
ys = [v.co.y for v in tripo.data.vertices]
zs = [v.co.z for v in tripo.data.vertices]
tripo.location = (-(min(xs)+max(xs))/2, -(min(ys)+max(ys))/2, -min(zs))
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

print(f"Tripo: {len(tripo.data.vertices)} verts, Z[0, 1.8]")

# ============================================================
# Step 2: 从MetaHuman blend文件中只提取Body网格
# ============================================================
print("\n提取MetaHuman Body...")

# 打开MetaHuman文件，提取Body
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

# 确保只有Body，删除其他
for obj in list(bpy.data.objects):
    if obj != mh_body:
        bpy.data.objects.remove(obj, do_unlink=True)

# cm→m
for v in mh_body.data.vertices:
    v.co *= 0.01
bpy.context.view_layer.update()

# 绕Z-90°旋转使坐标系与Tripo一致
mh_body.matrix_basis = Matrix.Rotation(math.radians(-90), 4, 'Z') @ mh_body.matrix_basis
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 缩放到1.8m
zs = [v.co.z for v in mh_body.data.vertices]
mh_h = max(zs) - min(zs)
mh_body.scale = (1.8/mh_h, 1.8/mh_h, 1.8/mh_h)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 接地+居中
zs = [v.co.z for v in mh_body.data.vertices]
xs = [v.co.x for v in mh_body.data.vertices]
ys = [v.co.y for v in mh_body.data.vertices]
mh_body.location = (-(min(xs)+max(xs))/2, -(min(ys)+max(ys))/2, -min(zs))
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 验证
xs = [v.co.x for v in mh_body.data.vertices]
ys = [v.co.y for v in mh_body.data.vertices]
zs = [v.co.z for v in mh_body.data.vertices]
print(f"MetaHuman Body: {len(mh_body.data.vertices)} verts")
print(f"  X[{min(xs):.2f},{max(xs):.2f}] Y[{min(ys):.2f},{max(ys):.2f}] Z[{min(zs):.2f},{max(zs):.2f}]")

# 保存MetaHuman Body
bpy.ops.wm.save_as_mainfile(filepath=TMP_MH)
print(f"  保存: {TMP_MH}")

# ============================================================
# Step 3: 在Tripo场景中追加MetaHuman Body
# ============================================================
print("\n在Tripo场景中追加MetaHuman Body...")

# 重新打开Tripo场景
tmp_tripo = os.path.join(ROOT, "output", "wrap", "tmp_tripo.blend")
# 先保存当前Tripo到tmp_tripo（重新导入）
print("重新导入Tripo到tmp_tripo...")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)
tripo = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        tripo = obj
        break
tripo.name = "Tripo"
bpy.context.view_layer.objects.active = tripo
tripo.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for axis in ['X', 'Z', 'Y']:
    tripo.matrix_basis = Matrix.Rotation(math.radians(-90), 4, axis) @ tripo.matrix_basis
    bpy.context.view_layer.update()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
zs = [v.co.z for v in tripo.data.vertices]
scale = 1.8 / (max(zs) - min(zs))
tripo.scale = (scale, scale, scale)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
xs = [v.co.x for v in tripo.data.vertices]
ys = [v.co.y for v in tripo.data.vertices]
zs = [v.co.z for v in tripo.data.vertices]
tripo.location = (-(min(xs)+max(xs))/2, -(min(ys)+max(ys))/2, -min(zs))
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.wm.save_as_mainfile(filepath=tmp_tripo)
print(f"Tripo保存: {tmp_tripo}")
tripo = bpy.data.objects.get("Tripo")
print(f"Tripo: {len(tripo.data.vertices)} verts")

# 追加MetaHuman Body
MH_BODY_NAME = "NewMetaHumanCharacter_Body"
bpy.ops.wm.append(
    filepath=os.path.join(TMP_MH, "Object", MH_BODY_NAME),
    directory=os.path.join(TMP_MH, "Object"),
    filename=MH_BODY_NAME
)
mh_body = bpy.data.objects.get(MH_BODY_NAME)
if not mh_body:
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and 'Body' in obj.name:
            mh_body = obj
            break

print(f"MetaHuman Body追加: {len(mh_body.data.vertices)} verts")

# 验证
xs = [v.co.x for v in mh_body.data.vertices]
ys = [v.co.y for v in mh_body.data.vertices]
zs = [v.co.z for v in mh_body.data.vertices]
print(f"  X[{min(xs):.2f},{max(xs):.2f}] Y[{min(ys):.2f},{max(ys):.2f}] Z[{min(zs):.2f},{max(zs):.2f}]")

# ============================================================
# Step 4: Shrinkwrap
# ============================================================
print("\nShrinkwrap...")
bpy.context.view_layer.objects.active = mh_body
mh_body.select_set(True)
tripo.select_set(False)

sw = mh_body.modifiers.new(name="SW", type='SHRINKWRAP')
sw.target = tripo
sw.wrap_method = 'NEAREST_SURFACEPOINT'
sw.wrap_mode = 'ON_SURFACE'
try:
    sw.use_keep_above_surface = True
except AttributeError:
    pass

bpy.ops.object.modifier_apply(modifier="SW")

# 验证Shrinkwrap结果
xs = [v.co.x for v in mh_body.data.vertices]
ys = [v.co.y for v in mh_body.data.vertices]
zs = [v.co.z for v in mh_body.data.vertices]
print(f"\n包裹后MetaHuman Body:")
print(f"  X[{min(xs):.2f},{max(xs):.2f}] Y[{min(ys):.2f},{max(ys):.2f}] Z[{min(zs):.2f},{max(zs):.2f}]")

# ============================================================
# Step 5: 精度统计
# ============================================================
print("\n精度统计...")
tripo_verts = [tripo.matrix_world @ v.co for v in tripo.data.vertices]
tripo_faces = [list(p.vertices) for p in tripo.data.polygons]
tripo_bvh = BVHTree.FromPolygons(tripo_verts, tripo_faces)

distances = []
for v in mh_body.data.vertices:
    wp = mh_body.matrix_world @ v.co
    nearest, _, _, _ = tripo_bvh.find_nearest(wp)
    if nearest:
        d = (wp - nearest).length
        distances.append(d)

distances = np.array(distances)
print(f"  平均: {np.mean(distances)*1000:.2f}mm")
print(f"  中位: {np.median(distances)*1000:.2f}mm")
print(f"  <1mm: {np.mean(distances<0.001)*100:.1f}%")
print(f"  <2mm: {np.mean(distances<0.002)*100:.1f}%")
print(f"  <5mm: {np.mean(distances<0.005)*100:.1f}%")
print(f"  最大: {np.max(distances)*1000:.2f}mm")

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"\n保存: {OUT_BLEND}")
print("DONE")
