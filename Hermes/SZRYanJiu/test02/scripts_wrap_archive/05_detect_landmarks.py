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
mh_head = bpy.data.objects.get("MH_NewMetaHumanCharacter_Head")
tripo = bpy.data.objects.get("Tripo_Tripo_HighPoly")

print(f"MH Body: {mh_body.name} ({len(mh_body.data.vertices):,} verts)")
print(f"MH Head: {mh_head.name} ({len(mh_head.data.vertices):,} verts)")
print(f"Tripo: {tripo.name} ({len(tripo.data.vertices):,} verts)")

# ============================================================
# Step 2: 定义身体特征点（关节点）
# ============================================================
print("\n" + "="*60)
print("Step 2: 定义身体特征点")
print("="*60)

# MetaHuman身体特征点（基于骨骼位置和拓扑结构）
# 这些索引需要根据实际MetaHuman拓扑验证
BODY_LANDMARKS = {
    # 躯干
    'pelvis_center': 0,  # 骨盆中心
    'spine_01': 1000,    # 腰椎
    'spine_03': 2000,    # 胸椎
    'spine_05': 3000,    # 颈椎
    'neck_base': 4000,   # 颈部底部
    
    # 左臂
    'shoulder_l': 5000,      # 左肩
    'upperarm_mid_l': 6000,  # 左大臂中点
    'elbow_l': 7000,         # 左肘
    'lowerarm_mid_l': 8000,  # 左小臂中点
    'wrist_l': 9000,         # 左腕
    
    # 右臂
    'shoulder_r': 10000,     # 右肩
    'upperarm_mid_r': 11000, # 右大臂中点
    'elbow_r': 12000,        # 右肘
    'lowerarm_mid_r': 13000, # 右小臂中点
    'wrist_r': 14000,        # 右腕
    
    # 左腿
    'hip_l': 15000,          # 左髋
    'thigh_mid_l': 16000,    # 左大腿中点
    'knee_l': 17000,         # 左膝
    'calf_mid_l': 18000,     # 左小腿中点
    'ankle_l': 19000,        # 左踝
    
    # 右腿
    'hip_r': 20000,          # 右髋
    'thigh_mid_r': 21000,    # 右大腿中点
    'knee_r': 22000,         # 右膝
    'calf_mid_r': 23000,     # 右小腿中点
    'ankle_r': 24000,        # 右踝
}

# 注意：这些索引是估算的，需要根据实际MetaHuman拓扑验证
# 更好的方法是基于几何位置自动检测

print("身体特征点定义（估算索引）:")
for name, idx in list(BODY_LANDMARKS.items())[:10]:
    print(f"  {name}: vertex {idx}")

# ============================================================
# Step 3: 基于几何位置自动检测特征点
# ============================================================
print("\n" + "="*60)
print("Step 3: 基于几何位置自动检测特征点")
print("="*60)

# 使用MetaHuman的几何特征自动检测关节点
# 方法：基于顶点位置和法线方向

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

def find_landmark_by_position(mesh, target_pos, search_radius=0.05):
    """在目标位置附近搜索顶点"""
    best_idx = -1
    best_dist = float('inf')
    
    for i, v in enumerate(mesh.data.vertices):
        world_pos = mesh.matrix_world @ v.co
        dist = (world_pos - target_pos).length
        if dist < search_radius and dist < best_dist:
            best_dist = dist
            best_idx = i
    
    return best_idx, best_dist

# 基于MetaHuman的典型比例定义目标位置
# 假设MetaHuman是标准人体比例
bbox = get_bbox(mh_body)
height = bbox['size'].z

# 定义关键关节的目标位置（基于人体比例）
landmark_targets = {
    'pelvis': Vector((0, 0, bbox['min'].z + height * 0.55)),
    'chest': Vector((0, 0, bbox['min'].z + height * 0.75)),
    'neck': Vector((0, 0, bbox['min'].z + height * 0.88)),
    
    'shoulder_l': Vector((-bbox['size'].x * 0.25, 0, bbox['min'].z + height * 0.82)),
    'elbow_l': Vector((-bbox['size'].x * 0.35, 0, bbox['min'].z + height * 0.62)),
    'wrist_l': Vector((-bbox['size'].x * 0.40, 0, bbox['min'].z + height * 0.42)),
    
    'shoulder_r': Vector((bbox['size'].x * 0.25, 0, bbox['min'].z + height * 0.82)),
    'elbow_r': Vector((bbox['size'].x * 0.35, 0, bbox['min'].z + height * 0.62)),
    'wrist_r': Vector((bbox['size'].x * 0.40, 0, bbox['min'].z + height * 0.42)),
    
    'hip_l': Vector((-bbox['size'].x * 0.15, 0, bbox['min'].z + height * 0.48)),
    'knee_l': Vector((-bbox['size'].x * 0.18, 0, bbox['min'].z + height * 0.28)),
    'ankle_l': Vector((-bbox['size'].x * 0.20, 0, bbox['min'].z + height * 0.05)),
    
    'hip_r': Vector((bbox['size'].x * 0.15, 0, bbox['min'].z + height * 0.48)),
    'knee_r': Vector((bbox['size'].x * 0.18, 0, bbox['min'].z + height * 0.28)),
    'ankle_r': Vector((bbox['size'].x * 0.20, 0, bbox['min'].z + height * 0.05)),
}

# 检测特征点
detected_landmarks = {}
for name, target in landmark_targets.items():
    idx, dist = find_landmark_by_position(mh_body, target, search_radius=0.1)
    if idx >= 0:
        detected_landmarks[name] = idx
        print(f"  {name}: vertex {idx} (dist={dist*1000:.1f}mm)")
    else:
        print(f"  {name}: NOT FOUND")

# 保存特征点
landmarks_path = os.path.join(OUT_DIR, "body_landmarks.json")
with open(landmarks_path, 'w') as f:
    json.dump(detected_landmarks, f, indent=2)
print(f"\n特征点保存: {landmarks_path}")

# ============================================================
# Step 4: 保存
# ============================================================
print("\n" + "="*60)
print("Step 4: 保存")
print("="*60)

blend_path = os.path.join(OUT_DIR, "landmarks_detected.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

print("\nDONE")
