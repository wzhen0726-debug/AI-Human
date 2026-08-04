import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh

# ============================================================
# Step 1: 导入MetaHuman低模并渲染
# 目的: 检查MetaHuman的朝向、比例、骨骼位置
# ============================================================

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
METAHUMAN_BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\Metahuman_Low_01.blend"
OUT_DIR = os.path.join(ROOT, "output", "renders_mh")
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

# 获取骨骼
armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
print(f"\n找到 {len(armatures)} 个骨骼:")
for a in armatures:
    print(f"  - {a.name}: {len(a.data.bones)} bones")

# 获取主网格（最大的）
main_mesh = max(meshes, key=lambda m: len(m.data.vertices))
print(f"\n主网格: {main_mesh.name} ({len(main_mesh.data.vertices):,} verts)")

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

bbox = get_bbox(main_mesh)
print(f"\nMetaHuman尺寸: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")
print(f"Z范围: [{bbox['min'].z:.3f}, {bbox['max'].z:.3f}]")

# ============================================================
# Step 2: 渲染MetaHuman
# ============================================================
print("\n" + "="*60)
print("Step 2: 渲染MetaHuman")
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
    
    render_path = os.path.join(OUT_DIR, f"metahuman_{name}.png")
    bpy.context.scene.render.filepath = render_path
    bpy.ops.render.render(write_still=True)
    render_paths[name] = render_path
    print(f"  {name}: {render_path}")

# ============================================================
# Step 3: 分析骨骼位置
# ============================================================
print("\n" + "="*60)
print("Step 3: 骨骼位置分析")
print("="*60)

if armatures:
    arm = armatures[0]
    print(f"骨骼: {arm.name}")
    print(f"骨骼数量: {len(arm.data.bones)}")
    
    # 打印关键骨骼位置
    key_bones = ['root', 'pelvis', 'spine_01', 'spine_05', 'neck_01', 'head',
                 'clavicle_l', 'clavicle_r', 'upperarm_l', 'upperarm_r',
                 'lowerarm_l', 'lowerarm_r', 'hand_l', 'hand_r',
                 'thigh_l', 'thigh_r', 'calf_l', 'calf_r', 'foot_l', 'foot_r']
    
    print("\n关键骨骼位置 (世界坐标):")
    for bone_name in key_bones:
        bone = arm.data.bones.get(bone_name)
        if bone:
            # 骨骼头位置
            head_local = bone.head_local
            # 转换到世界坐标
            head_world = arm.matrix_world @ Vector(head_local)
            print(f"  {bone_name}: ({head_world.x:.3f}, {head_world.y:.3f}, {head_world.z:.3f})")

# ============================================================
# Step 4: 保存
# ============================================================
print("\n" + "="*60)
print("Step 4: 保存")
print("="*60)

blend_path = os.path.join(ROOT, "output", "metahuman_imported.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

print("\nDONE")
