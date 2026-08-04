import bpy, os, sys, math, json
from mathutils import Vector

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
BLEND_PATH = os.path.join(ROOT, "output", "landmark_scene_v4.blend")
OUT_DIR = os.path.join(ROOT, "output", "verification")
os.makedirs(OUT_DIR, exist_ok=True)

print("="*60)
print("验证v4场景并渲染截图")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)

mesh_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        mesh_obj = obj
        break

# 检查顶点坐标
print("\n顶点坐标检查:")
for i in range(min(5, len(mesh_obj.data.vertices))):
    v = mesh_obj.data.vertices[i]
    print(f"  v{i}: ({v.co.x:.4f}, {v.co.y:.4f}, {v.co.z:.4f})")

# 检查bbox
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
print(f"\nbbox: X[{bbox['min'].x:.3f}, {bbox['max'].x:.3f}] Y[{bbox['min'].y:.3f}, {bbox['max'].y:.3f}] Z[{bbox['min'].z:.3f}, {bbox['max'].z:.3f}]")
print(f"size: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")

# 渲染前/左/顶三视图
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
    'left': (-1, 0, 0),
    'top': (0, 0, 1),
}

for name, direction in directions.items():
    dir_vec = Vector(direction)
    cam.location = bbox['center'] + dir_vec * cam_dist
    look_dir = bbox['center'] - cam.location
    cam.rotation_euler = look_dir.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    
    render_path = os.path.join(OUT_DIR, f"v4_{name}.png")
    bpy.context.scene.render.filepath = render_path
    bpy.ops.render.render(write_still=True)
    print(f"  {name}: {render_path}")

print("\nDONE")
