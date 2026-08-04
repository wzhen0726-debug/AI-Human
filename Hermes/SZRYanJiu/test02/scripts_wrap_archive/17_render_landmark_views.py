import bpy, os, sys, math
from mathutils import Vector

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
TRIPO_BLEND = os.path.join(ROOT, "output", "tripo_tpose_prepared_v3.blend")
OUT_DIR = os.path.join(ROOT, "output", "landmark_renders")
os.makedirs(OUT_DIR, exist_ok=True)

print("="*60)
print("生成Tripo特征点标记渲染图")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=TRIPO_BLEND)
tripo = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        tripo = obj
        break

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

bbox = get_bbox(tripo)
print(f"Tripo: {len(tripo.data.vertices):,} verts")
print(f"Size: X={bbox['size'].x:.2f} Y={bbox['size'].y:.2f} Z={bbox['size'].z:.2f}")

# 渲染设置
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
cam_dist = max_dim * 1.5

# 6个方向
directions = {
    'front': (0, -1, 0),
    'back': (0, 1, 0),
    'left': (-1, 0, 0),
    'right': (1, 0, 0),
    'top': (0, 0, 1),
    'bottom': (0, 0, -1),
}

for name, direction in directions.items():
    dir_vec = Vector(direction)
    cam.location = bbox['center'] + dir_vec * cam_dist
    look_dir = bbox['center'] - cam.location
    cam.rotation_euler = look_dir.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    
    render_path = os.path.join(OUT_DIR, f"tripo_{name}.png")
    bpy.context.scene.render.filepath = render_path
    bpy.ops.render.render(write_still=True)
    print(f"  {name}: {render_path}")

# 保存相机参数供反投影使用
cam_data = {
    'location': list(cam.location),
    'rotation_euler': list(cam.rotation_euler),
    'lens': cam.data.lens,
    'sensor_width': cam.data.sensor_width,
    'bbox_center': list(bbox['center']),
    'bbox_size': list(bbox['size']),
    'cam_dist': cam_dist,
}

import json
cam_path = os.path.join(OUT_DIR, "camera_params.json")
with open(cam_path, 'w') as f:
    json.dump(cam_data, f, indent=2)

print(f"\n相机参数: {cam_path}")
print("\nDONE")
