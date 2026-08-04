import bpy, os, sys, math
from mathutils import Vector, Matrix
import bmesh

# ============================================================
# Step 1: 导入MetaHuman并旋转到Tripo坐标系
# 方案: 旋转MetaHuman使X=厚度(与Tripo一致)
# ============================================================

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
METAHUMAN_BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\Metahuman_Low_01.blend"
OUT_DIR = os.path.join(ROOT, "output", "renders_mh_rotated")
os.makedirs(OUT_DIR, exist_ok=True)

print("="*60)
print("Step 1: 导入MetaHuman低模")
print("="*60)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

bpy.ops.wm.open_mainfile(filepath=METAHUMAN_BLEND)

# 获取所有网格
meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
print(f"找到 {len(meshes)} 个网格")

# 获取身体和头部
body_mesh = None
head_mesh = None
face_mesh = None
for m in meshes:
    if 'Body' in m.name:
        body_mesh = m
    elif 'Head' in m.name:
        head_mesh = m
    elif 'Face' in m.name:
        face_mesh = m

if not body_mesh:
    body_mesh = max(meshes, key=lambda m: len(m.data.vertices))

print(f"身体: {body_mesh.name} ({len(body_mesh.data.vertices):,} verts)")
if head_mesh:
    print(f"头部: {head_mesh.name} ({len(head_mesh.data.vertices):,} verts)")

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

# ============================================================
# Step 2: 缩放到米单位并旋转
# ============================================================
print("\n" + "="*60)
print("Step 2: 缩放到米单位并旋转")
print("="*60)

# 先缩放到米
scale_factor = 0.01
for m in meshes:
    m.scale = (scale_factor, scale_factor, scale_factor)

bpy.context.view_layer.update()

# 应用缩放
for m in meshes:
    bpy.context.view_layer.objects.active = m
    m.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    m.select_set(False)

bbox = get_bbox(body_mesh)
print(f"缩放后: X={bbox['size'].x:.3f}m Y={bbox['size'].y:.3f}m Z={bbox['size'].z:.3f}m")

# 旋转MetaHuman: X=肩宽→X=厚度, Y=深度→Y=肩宽
# 绕Z轴旋转-90°: x→-y, y→x
print("\n绕Z轴旋转-90° (X=肩宽→X=厚度)")

for m in meshes:
    bm = bmesh.new()
    bm.from_mesh(m.data)
    
    # 绕Z轴-90°: x→-y, y→x
    for v in bm.verts:
        old_x, old_y = v.co.x, v.co.y
        v.co.x = -old_y  # 新X = -旧Y (深度→厚度)
        v.co.y = old_x   # 新Y = 旧X (肩宽→深度)
    
    bm.to_mesh(m.data)
    bm.free()
    m.data.update()

bbox = get_bbox(body_mesh)
print(f"旋转后: X={bbox['size'].x:.3f}m Y={bbox['size'].y:.3f}m Z={bbox['size'].z:.3f}m")

# ============================================================
# Step 3: 渲染验证
# ============================================================
print("\n" + "="*60)
print("Step 3: 渲染验证")
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
cam_dist = max_dim * 2.0

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
    
    render_path = os.path.join(OUT_DIR, f"metahuman_rotated_{name}.png")
    bpy.context.scene.render.filepath = render_path
    bpy.ops.render.render(write_still=True)
    render_paths[name] = render_path
    print(f"  {name}: {render_path}")

# ============================================================
# Step 4: 保存
# ============================================================
print("\n" + "="*60)
print("Step 4: 保存")
print("="*60)

blend_path = os.path.join(ROOT, "output", "metahuman_rotated.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

print("\n" + "="*60)
print("模型信息摘要")
print("="*60)
print(f"最终尺寸: {bbox['size'].x:.3f} x {bbox['size'].y:.3f} x {bbox['size'].z:.3f} m")
print(f"身体顶点: {len(body_mesh.data.vertices):,}")

print("\nDONE")
