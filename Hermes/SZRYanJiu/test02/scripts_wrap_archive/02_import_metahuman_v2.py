import bpy, os, sys, math
from mathutils import Vector, Matrix
import bmesh

# ============================================================
# 修正版: 导入MetaHuman低模并正确缩放
# 问题: MetaHuman单位是cm，需要转换到m
# ============================================================

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
METAHUMAN_BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\Metahuman_Low_01.blend"
OUT_DIR = os.path.join(ROOT, "output", "renders_mh_v2")
os.makedirs(OUT_DIR, exist_ok=True)

print("="*60)
print("Step 1: 导入MetaHuman低模")
print("="*60)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 导入blend文件
bpy.ops.wm.open_mainfile(filepath=METAHUMAN_BLEND)

# 获取所有网格
meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
print(f"找到 {len(meshes)} 个网格:")
for m in meshes:
    print(f"  - {m.name}: {len(m.data.vertices):,}v {len(m.data.polygons):,}f")

# 获取主网格（身体）
body_mesh = None
head_mesh = None
for m in meshes:
    if 'Body' in m.name:
        body_mesh = m
    elif 'Head' in m.name:
        head_mesh = m

if not body_mesh:
    body_mesh = max(meshes, key=lambda m: len(m.data.vertices))

print(f"\n身体: {body_mesh.name} ({len(body_mesh.data.vertices):,} verts)")
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

bbox = get_bbox(body_mesh)
print(f"\nMetaHuman原始尺寸: X={bbox['size'].x:.1f} Y={bbox['size'].y:.1f} Z={bbox['size'].z:.1f}")
print(f"Z范围: [{bbox['min'].z:.1f}, {bbox['max'].z:.1f}]")

# ============================================================
# Step 2: 缩放MetaHuman到米单位
# ============================================================
print("\n" + "="*60)
print("Step 2: 缩放到米单位")
print("="*60)

# MetaHuman单位是cm，转换到m (除以100)
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
print(f"Z范围: [{bbox['min'].z:.3f}, {bbox['max'].z:.3f}]")

# ============================================================
# Step 3: 渲染MetaHuman
# ============================================================
print("\n" + "="*60)
print("Step 3: 渲染MetaHuman")
print("="*60)

bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.context.scene.render.film_transparent = False
bpy.context.scene.world.color = (0.9, 0.9, 0.9)

# 添加灯光
bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
sun = bpy.context.active_object
sun.data.energy = 5.0
sun.rotation_euler = (math.radians(45), 0, 0)

# 添加相机
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
    
    render_path = os.path.join(OUT_DIR, f"metahuman_{name}.png")
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

blend_path = os.path.join(ROOT, "output", "metahuman_scaled.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

print("\nDONE")
