import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
ALIGNED_BLEND = os.path.join(ROOT, "output", "wrap", "aligned_scene.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")
os.makedirs(OUT_DIR, exist_ok=True)

print("="*60)
print("Step 1: 导入对齐场景")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=ALIGNED_BLEND)

mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")
tripo = bpy.data.objects.get("Tripo_Tripo_HighPoly")

print(f"MH Body: {mh_body.name} ({len(mh_body.data.vertices):,} verts)")
print(f"Tripo: {tripo.name} ({len(tripo.data.vertices):,} verts)")

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
# Step 2: 对称特征点检测
# ============================================================
print("\n" + "="*60)
print("Step 2: 对称特征点检测")
print("="*60)

# 利用MetaHuman的对称性：左特征点找到后，镜像找右特征点
bbox = get_bbox(mh_body)
height = bbox['size'].z
center_x = bbox['center'].x

def find_landmark(mesh, target_pos, search_radius=0.1):
    best_idx = -1
    best_dist = float('inf')
    for i, v in enumerate(mesh.data.vertices):
        world_pos = mesh.matrix_world @ v.co
        dist = (world_pos - target_pos).length
        if dist < search_radius and dist < best_dist:
            best_dist = dist
            best_idx = i
    return best_idx, best_dist

def mirror_x(pos, center_x):
    """以X=center_x为对称轴镜像"""
    return Vector((2 * center_x - pos.x, pos.y, pos.z))

# 先找左侧特征点
left_targets = {
    'shoulder_l': Vector((center_x - bbox['size'].x * 0.25, 0, bbox['min'].z + height * 0.82)),
    'elbow_l': Vector((center_x - bbox['size'].x * 0.35, 0, bbox['min'].z + height * 0.62)),
    'wrist_l': Vector((center_x - bbox['size'].x * 0.40, 0, bbox['min'].z + height * 0.42)),
    'hip_l': Vector((center_x - bbox['size'].x * 0.15, 0, bbox['min'].z + height * 0.48)),
    'knee_l': Vector((center_x - bbox['size'].x * 0.18, 0, bbox['min'].z + height * 0.28)),
    'ankle_l': Vector((center_x - bbox['size'].x * 0.20, 0, bbox['min'].z + height * 0.05)),
}

# 找中线特征点
mid_targets = {
    'pelvis': Vector((center_x, 0, bbox['min'].z + height * 0.55)),
    'chest': Vector((center_x, 0, bbox['min'].z + height * 0.75)),
    'neck': Vector((center_x, 0, bbox['min'].z + height * 0.88)),
}

detected = {}

# 检测中线
print("中线特征点:")
for name, target in mid_targets.items():
    idx, dist = find_landmark(mh_body, target, 0.15)
    if idx >= 0:
        detected[name] = idx
        print(f"  {name}: vertex {idx} (dist={dist*1000:.1f}mm)")

# 检测左侧
print("\n左侧特征点:")
for name, target in left_targets.items():
    idx, dist = find_landmark(mh_body, target, 0.15)
    if idx >= 0:
        detected[name] = idx
        print(f"  {name}: vertex {idx} (dist={dist*1000:.1f}mm)")

# 镜像检测右侧
print("\n右侧特征点 (镜像检测):")
for name, target in left_targets.items():
    right_name = name.replace('_l', '_r')
    # 先找到左侧的实际位置
    if name in detected:
        left_idx = detected[name]
        left_pos = mh_body.matrix_world @ mh_body.data.vertices[left_idx].co
        # 镜像到右侧
        right_target = mirror_x(left_pos, center_x)
        idx, dist = find_landmark(mh_body, right_target, 0.15)
        if idx >= 0:
            detected[right_name] = idx
            print(f"  {right_name}: vertex {idx} (dist={dist*1000:.1f}mm)")
        else:
            print(f"  {right_name}: NOT FOUND (mirror of {name})")

# 保存特征点
landmarks_path = os.path.join(OUT_DIR, "body_landmarks_v2.json")
with open(landmarks_path, 'w') as f:
    json.dump(detected, f, indent=2)

print(f"\n特征点保存: {landmarks_path}")
print(f"共检测: {len(detected)} 个特征点")

# ============================================================
# Step 3: 保存
# ============================================================
print("\n" + "="*60)
print("Step 3: 保存")
print("="*60)

blend_path = os.path.join(OUT_DIR, "landmarks_detected_v2.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

print("\nDONE")
