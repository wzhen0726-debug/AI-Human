import bpy, os, sys, math
from mathutils import Vector, Matrix
import bmesh

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
GLB_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\AI生成高模\02_tripoTpose\raw_model.glb"
OUT_BLEND = os.path.join(ROOT, "output", "tripo_tpose_corrected_v2.blend")

print("="*60)
print("修正Tripo坐标系 v2")
print("="*60)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

bpy.ops.import_scene.gltf(filepath=GLB_PATH)

mesh_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        mesh_obj = obj
        break

mesh_obj.name = "Tripo_HighPoly"
bpy.context.view_layer.objects.active = mesh_obj
mesh_obj.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

def get_bbox(obj):
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    return {
        'min': Vector((min(xs), min(ys), min(zs))),
        'max': Vector((max(xs), max(ys), max(zs))),
        'size': Vector((max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))),
        'center': Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    }

bbox = get_bbox(mesh_obj)
print(f"原始: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")

# ============================================================
# Step 1: 绕Z轴-90° (身高从Y转到Z)
# ============================================================
print("\n" + "="*60)
print("Step 1: 绕Z轴-90°")
print("="*60)

bm = bmesh.new()
bm.from_mesh(mesh_obj.data)

# 绕Z轴-90°: x→-y, y→x, z→z
for v in bm.verts:
    old_x, old_y = v.co.x, v.co.y
    v.co.x = -old_y  # 新X = -旧Y
    v.co.y = old_x   # 新Y = 旧X

bm.to_mesh(mesh_obj.data)
bm.free()
mesh_obj.data.update()

bbox = get_bbox(mesh_obj)
print(f"绕Z轴-90°后: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")

# ============================================================
# Step 2: 绕Y轴+90° (宽度从Z转到X)
# ============================================================
print("\n" + "="*60)
print("Step 2: 绕Y轴+90°")
print("="*60)

bm = bmesh.new()
bm.from_mesh(mesh_obj.data)

# 绕Y轴+90°: x→z, z→-x, y→y
for v in bm.verts:
    old_x, old_z = v.co.x, v.co.z
    v.co.x = old_z   # 新X = 旧Z
    v.co.z = -old_x  # 新Z = -旧X

bm.to_mesh(mesh_obj.data)
bm.free()
mesh_obj.data.update()

bbox = get_bbox(mesh_obj)
print(f"绕Y轴+90°后: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")

# ============================================================
# Step 3: 绕Z轴180° (正面朝-Y)
# ============================================================
print("\n" + "="*60)
print("Step 3: 绕Z轴180° (正面朝-Y)")
print("="*60)

bm = bmesh.new()
bm.from_mesh(mesh_obj.data)

# 绕Z轴180°: x→-x, y→-y, z→z
for v in bm.verts:
    old_x, old_y = v.co.x, v.co.y
    v.co.x = -old_x  # 新X = -旧X
    v.co.y = -old_y  # 新Y = -旧Y

bm.to_mesh(mesh_obj.data)
bm.free()
mesh_obj.data.update()

bbox = get_bbox(mesh_obj)
print(f"绕Z轴180°后: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")

# ============================================================
# Step 4: 居中、缩放、接地
# ============================================================
print("\n" + "="*60)
print("Step 4: 居中、缩放、接地")
print("="*60)

# 居中
mesh_obj.location = -bbox['center']
bpy.context.view_layer.update()
bbox = get_bbox(mesh_obj)

# 缩放到1.8m
scale_factor = 1.8 / bbox['size'].z
mesh_obj.scale = (scale_factor, scale_factor, scale_factor)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 重新居中并接地
bbox = get_bbox(mesh_obj)
mesh_obj.location.x = -bbox['center'].x
mesh_obj.location.y = -bbox['center'].y
mesh_obj.location.z = -bbox['min'].z
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bbox = get_bbox(mesh_obj)
print(f"最终: 高={bbox['size'].z:.2f}m, 宽={bbox['size'].x:.2f}m, 深={bbox['size'].y:.2f}m")
print(f"Z范围: [{bbox['min'].z:.2f}, {bbox['max'].z:.2f}]")
print(f"Y范围: [{bbox['min'].y:.2f}, {bbox['max'].y:.2f}]")
print(f"X范围: [{bbox['min'].x:.2f}, {bbox['max'].x:.2f}]")

# ============================================================
# Step 5: 保存
# ============================================================
print("\n" + "="*60)
print("Step 5: 保存")
print("="*60)

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"保存: {OUT_BLEND}")

print("\nDONE")
