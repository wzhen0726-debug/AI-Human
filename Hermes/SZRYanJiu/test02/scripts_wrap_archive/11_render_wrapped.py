import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh
import numpy as np

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
WRAPPED_BLEND = os.path.join(ROOT, "output", "wrap", "wrapped_body.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")

print("="*60)
print("Step 1: 导入包裹结果并渲染")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=WRAPPED_BLEND)
mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")
tripo = bpy.data.objects.get("Tripo_Tripo_HighPoly")

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

bbox = get_bbox(mh_body)
max_dim = max(bbox['size'].x, bbox['size'].y, bbox['size'].z)
cam_dist = max_dim * 2.0

# 渲染多个视角
directions = {
    'front': (0, -1, 0),
    'back': (0, 1, 0),
    'left': (-1, 0, 0),
    'right': (1, 0, 0),
}

for name, direction in directions.items():
    dir_vec = Vector(direction)
    cam.location = bbox['center'] + dir_vec * cam_dist
    look_dir = bbox['center'] - cam.location
    cam.rotation_euler = look_dir.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    
    render_path = os.path.join(OUT_DIR, f"wrapped_{name}.png")
    bpy.context.scene.render.filepath = render_path
    bpy.ops.render.render(write_still=True)
    print(f"  {name}: {render_path}")

# ============================================================
# Step 2: 保存
# ============================================================
blend_path = os.path.join(OUT_DIR, "wrapped_body_rendered.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"\n保存: {blend_path}")
print("DONE")
