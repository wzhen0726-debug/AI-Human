import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
LANDMARKS_BLEND = os.path.join(ROOT, "output", "wrap", "landmarks_topo_v2.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")

print("="*60)
print("Step 1: 导入并可视化特征点")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=LANDMARKS_BLEND)
mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")

with open(os.path.join(OUT_DIR, "body_landmarks_topo_v2.json")) as f:
    landmarks = json.load(f)

print(f"加载 {len(landmarks)} 个特征点")

# 创建空物体标记特征点
bpy.ops.object.empty_add(type='SPHERE', radius=0.01)
marker_template = bpy.context.active_object
marker_template.name = "Landmark_Template"

# 为每个特征点创建标记
markers = []
for name, idx in landmarks.items():
    if idx < len(mh_body.data.vertices):
        v = mh_body.data.vertices[idx]
        world_pos = mh_body.matrix_world @ v.co
        
        # 创建新空物体
        marker = marker_template.copy()
        marker.name = f"LM_{name}"
        marker.location = world_pos
        bpy.context.collection.objects.link(marker)
        markers.append(marker)
        
        print(f"  {name}: vertex {idx} at ({world_pos.x:.3f}, {world_pos.y:.3f}, {world_pos.z:.3f})")

# 删除模板
bpy.data.objects.remove(marker_template, do_unlink=True)

# ============================================================
# Step 2: 渲染验证
# ============================================================
print("\n" + "="*60)
print("Step 2: 渲染验证")
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

directions = {
    'front': (0, -1, 0),
    'left': (-1, 0, 0),
    'right': (1, 0, 0),
}

for name, direction in directions.items():
    dir_vec = Vector(direction)
    cam.location = bbox['center'] + dir_vec * cam_dist
    look_dir = bbox['center'] - cam.location
    cam.rotation_euler = look_dir.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    
    render_path = os.path.join(OUT_DIR, f"landmarks_viz_{name}.png")
    bpy.context.scene.render.filepath = render_path
    bpy.ops.render.render(write_still=True)
    print(f"  {name}: {render_path}")

# ============================================================
# Step 3: 保存
# ============================================================
blend_path = os.path.join(OUT_DIR, "landmarks_visualized.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"\n保存: {blend_path}")
print("DONE")
