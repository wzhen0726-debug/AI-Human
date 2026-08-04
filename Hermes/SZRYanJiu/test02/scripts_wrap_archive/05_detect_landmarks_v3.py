import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
ALIGNED_BLEND = os.path.join(ROOT, "output", "wrap", "aligned_scene.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")

print("="*60)
print("Step 1: 导入对齐场景")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=ALIGNED_BLEND)

mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")
tripo = bpy.data.objects.get("Tripo_Tripo_HighPoly")

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
# Step 2: 基于拓扑结构的特征点检测
# ============================================================
print("\n" + "="*60)
print("Step 2: 基于拓扑结构的特征点检测")
print("="*60)

bbox = get_bbox(mh_body)
height = bbox['size'].z
center_x = bbox['center'].x

# 使用Mesh的顶点组或基于几何特征检测
# MetaHuman有标准的拓扑结构，我们可以基于顶点索引范围来定位

# MetaHuman Body的顶点分布（基于标准MetaHuman拓扑）
# 这些是基于MetaHuman标准拓扑的估算
MH_TOPO_REGIONS = {
    'head': (0, 2000),
    'neck': (2000, 4000),
    'chest': (4000, 8000),
    'spine': (8000, 12000),
    'pelvis': (12000, 16000),
    'left_arm': (16000, 22000),
    'right_arm': (22000, 28000),
    'left_leg': (28000, 32000),
    'right_leg': (32000, 32334),
}

def find_landmark_in_region(mesh, region_name, z_ratio, x_offset=0):
    """在指定区域内找特定高度和X偏移的顶点"""
    if region_name not in MH_TOPO_REGIONS:
        return -1, float('inf')
    
    start_idx, end_idx = MH_TOPO_REGIONS[region_name]
    target_z = bbox['min'].z + bbox['size'].z * z_ratio
    target_x = center_x + x_offset
    
    best_idx = -1
    best_dist = float('inf')
    
    for i in range(start_idx, min(end_idx, len(mesh.data.vertices))):
        v = mesh.data.vertices[i]
        world_pos = mesh.matrix_world @ v.co
        dist = (world_pos - Vector((target_x, 0, target_z))).length
        if dist < best_dist:
            best_dist = dist
            best_idx = i
    
    return best_idx, best_dist

# 检测特征点
landmarks = {}

# 中线
for name, region, z_ratio in [
    ('pelvis', 'pelvis', 0.55),
    ('chest', 'chest', 0.75),
    ('neck', 'neck', 0.88),
]:
    idx, dist = find_landmark_in_region(mh_body, region, z_ratio)
    if idx >= 0:
        landmarks[name] = idx
        print(f"  {name}: vertex {idx} (dist={dist*1000:.1f}mm)")

# 左侧
left_width = bbox['size'].x * 0.2
for name, region, z_ratio, x_off in [
    ('shoulder_l', 'chest', 0.82, -left_width),
    ('elbow_l', 'left_arm', 0.62, -left_width * 1.5),
    ('wrist_l', 'left_arm', 0.42, -left_width * 1.8),
    ('hip_l', 'pelvis', 0.48, -left_width * 0.8),
    ('knee_l', 'left_leg', 0.28, -left_width),
    ('ankle_l', 'left_leg', 0.05, -left_width * 1.2),
]:
    idx, dist = find_landmark_in_region(mh_body, region, z_ratio, x_off)
    if idx >= 0:
        landmarks[name] = idx
        print(f"  {name}: vertex {idx} (dist={dist*1000:.1f}mm)")

# 右侧（基于左侧镜像）
print("\n右侧特征点:")
for name in ['shoulder', 'elbow', 'wrist', 'hip', 'knee', 'ankle']:
    left_name = f"{name}_l"
    right_name = f"{name}_r"
    if left_name in landmarks:
        left_idx = landmarks[left_name]
        left_pos = mh_body.matrix_world @ mh_body.data.vertices[left_idx].co
        # 镜像X坐标
        right_x = 2 * center_x - left_pos.x
        # 在右侧区域找最近顶点
        region = 'right_arm' if 'arm' in left_name or name in ['shoulder', 'elbow', 'wrist'] else 'right_leg' if name in ['hip', 'knee', 'ankle'] else 'chest'
        idx, dist = find_landmark_in_region(mh_body, region, (left_pos.z - bbox['min'].z) / bbox['size'].z, right_x - center_x)
        if idx >= 0:
            landmarks[right_name] = idx
            print(f"  {right_name}: vertex {idx} (dist={dist*1000:.1f}mm)")

# 保存特征点
landmarks_path = os.path.join(OUT_DIR, "body_landmarks_v3.json")
with open(landmarks_path, 'w') as f:
    json.dump(landmarks, f, indent=2)

print(f"\n特征点保存: {landmarks_path}")
print(f"共检测: {len(landmarks)} 个特征点")

# ============================================================
# Step 3: 保存
# ============================================================
print("\n" + "="*60)
print("Step 3: 保存")
print("="*60)

blend_path = os.path.join(OUT_DIR, "landmarks_detected_v3.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

print("\nDONE")
