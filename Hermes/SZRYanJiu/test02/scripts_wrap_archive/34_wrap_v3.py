import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh
import numpy as np
from mathutils.bvhtree import BVHTree

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
MH_BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\Metahuman_Low_01.blend"
GLB_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\AI生成高模\02_tripoTpose\raw_model.glb"
OUT_BLEND = os.path.join(ROOT, "output", "wrap", "wrapped_v2.blend")

print("="*60)
print("Shrinkwrap包裹 v2")
print("="*60)

# 清空场景
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 1. 导入Tripo
print("导入Tripo...")
bpy.ops.import_scene.gltf(filepath=GLB_PATH)
tripo = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        tripo = obj
        break
tripo.name = "Tripo_HighPoly"
bpy.context.view_layer.objects.active = tripo
tripo.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 旋转三步
for axis in ['X', 'Z', 'Y']:
    tripo.matrix_basis = Matrix.Rotation(math.radians(-90), 4, axis) @ tripo.matrix_basis
    bpy.context.view_layer.update()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 缩放+接地
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

print(f"Tripo: {len(tripo.data.vertices)} verts")
tripo_zs = [v.co.z for v in tripo.data.vertices]

# 2. 导入MetaHuman Body（追加方式，不清空场景）
print("导入MetaHuman...")
# 保存Tripo到临时文件
tmp_tripo = os.path.join(ROOT, "output", "wrap", "tmp_tripo.blend")
bpy.ops.wm.save_as_mainfile(filepath=tmp_tripo)

# 打开MetaHuman
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

# cm→m
for v in mh_body.data.vertices:
    v.co *= 0.01
bpy.context.view_layer.update()

# 绕Z-90°旋转使坐标系一致
mh_body.matrix_basis = Matrix.Rotation(math.radians(-90), 4, 'Z') @ mh_body.matrix_basis
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 缩放到1.8m
zs = [v.co.z for v in mh_body.data.vertices]
mh_h = max(zs) - min(zs)
mh_body.scale = (1.8/mh_h, 1.8/mh_h, 1.8/mh_h)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 接地
zs = [v.co.z for v in mh_body.data.vertices]
mh_body.location.z = -min(zs)
# 居中
xs = [v.co.x for v in mh_body.data.vertices]
ys = [v.co.y for v in mh_body.data.vertices]
mh_body.location.x = -(min(xs)+max(xs))/2
mh_body.location.y = -(min(ys)+max(ys))/2
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

print(f"MetaHuman: {len(mh_body.data.vertices)} verts")

# 追加Tripo
bpy.ops.wm.append(filepath=os.path.join(tmp_tripo, "Object", "Tripo_HighPoly"), directory=os.path.join(tmp_tripo, "Object"), filename="Tripo_HighPoly")
tripo = bpy.data.objects.get("Tripo_HighPoly")
print(f"Tripo追加: {len(tripo.data.vertices)} verts")

# 验证bbox
zs_t = [v.co.z for v in tripo.data.vertices]
zs_m = [v.co.z for v in mh_body.data.vertices]
print(f"Tripo Z: [{min(zs_t):.2f}, {max(zs_t):.2f}]")
print(f"MH Z:    [{min(zs_m):.2f}, {max(zs_m):.2f}]")

# 3. Shrinkwrap
print("\nShrinkwrap...")
bpy.context.view_layer.objects.active = mh_body
mh_body.select_set(True)

sw = mh_body.modifiers.new(name="SW", type='SHRINKWRAP')
sw.target = tripo
sw.wrap_method = 'NEAREST_SURFACEPOINT'
sw.wrap_mode = 'ON_SURFACE'
try:
    sw.use_keep_above_surface = True
except AttributeError:
    pass

bpy.ops.object.modifier_apply(modifier="SW")

# 4. 统计精度
print("\n计算精度...")
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
print(f"平均: {np.mean(distances)*1000:.2f}mm")
print(f"中位: {np.median(distances)*1000:.2f}mm")
print(f"<1mm: {np.mean(distances<0.001)*100:.1f}%")
print(f"<2mm: {np.mean(distances<0.002)*100:.1f}%")
print(f"<5mm: {np.mean(distances<0.005)*100:.1f}%")
print(f"最大: {np.max(distances)*1000:.2f}mm")

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"\n保存: {OUT_BLEND}")
print("DONE")
