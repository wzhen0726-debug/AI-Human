import bpy, os, sys, math
from mathutils import Vector, Matrix
import bmesh

# ============================================================
# 修正版v3: 正确旋转Tripo模型
# 问题: Tripo是躺姿(Y=身高,Z=身宽), 需要绕X轴+90°站立
# ============================================================

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
GLB_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\AI生成高模\02_tripoTpose\raw_model.glb"
OUT_DIR = os.path.join(ROOT, "output", "renders_v3")
os.makedirs(OUT_DIR, exist_ok=True)

print("="*60)
print("Step 1: 导入Tripo T-pose高模")
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
# Step 2: 旋转到标准朝向
# Tripo原始: Y=身高(躺), Z=身宽, X=厚度
# 目标: Z=身高(站), Y=深度, X=宽度
# 绕X轴+90°: y→-z, z→y
# ============================================================
print("\n" + "="*60)
print("Step 2: 旋转到标准朝向")
print("="*60)

print("绕X轴+90° (躺→站)")

bm = bmesh.new()
bm.from_mesh(mesh_obj.data)

# 绕X轴+90°: y→-z, z→y
for v in bm.verts:
    old_y, old_z = v.co.y, v.co.z
    v.co.y = -old_z  # 新Y = -旧Z (身宽→深度)
    v.co.z = old_y   # 新Z = 旧Y (身高→站立)

bm.to_mesh(mesh_obj.data)
bm.free()
mesh_obj.data.update()

bbox = get_bbox(mesh_obj)
print(f"旋转后: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")

# ============================================================
# Step 3: 居中、缩放、接地
# ============================================================
print("\n" + "="*60)
print("Step 3: 居中、缩放、接地")
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

# ============================================================
# Step 4: 渲染6方向截图
# ============================================================
print("\n" + "="*60)
print("Step 4: 渲染6方向截图")
print("="*60)

bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.context.scene.render.film_transparent = False
bpy.context.scene.world.color = (0.9, 0.9, 0.9)

bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
sun = bpy.context.active_object
sun.data.energy = 5.0
sun.rotation_euler = (math.radians(45), 0, 0)

bpy.ops.object.camera_add()
cam = bpy.context.active_object
bpy.context.scene.camera = cam

max_dim = max(bbox['size'].x, bbox['size'].y, bbox['size'].z)
cam_dist = max_dim * 1.8

directions = {
    'front': (0, -1, 0),
    'back': (0, 1, 0),
    'left': (-1, 0, 0),
    'right': (1, 0, 0),
    'top': (0, 0, 1),
    'bottom': (0, 0, -1),
}

render_paths = {}
for name, direction in directions.items():
    dir_vec = Vector(direction)
    cam.location = bbox['center'] + dir_vec * cam_dist
    
    look_dir = bbox['center'] - cam.location
    cam.rotation_euler = look_dir.to_track_quat('-Z', 'Y').to_euler()
    
    bpy.context.view_layer.update()
    
    render_path = os.path.join(OUT_DIR, f"tripo_tpose_{name}.png")
    bpy.context.scene.render.filepath = render_path
    bpy.ops.render.render(write_still=True)
    render_paths[name] = render_path
    print(f"  {name}: {render_path}")

# ============================================================
# Step 5: 保存
# ============================================================
print("\n" + "="*60)
print("Step 5: 保存")
print("="*60)

blend_path = os.path.join(ROOT, "output", "tripo_tpose_prepared_v3.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

print("\n" + "="*60)
print("模型信息摘要")
print("="*60)
print(f"最终尺寸: {bbox['size'].x:.2f} x {bbox['size'].y:.2f} x {bbox['size'].z:.2f} m")
print(f"顶点数: {len(mesh_obj.data.vertices):,}")
print(f"面数: {len(mesh_obj.data.polygons):,}")

print("\nDONE")
