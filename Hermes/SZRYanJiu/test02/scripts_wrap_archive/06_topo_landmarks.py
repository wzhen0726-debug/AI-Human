import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh
import numpy as np

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
ALIGNED_BLEND = os.path.join(ROOT, "output", "wrap", "aligned_scene.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")

print("="*60)
print("Step 1: 导入对齐场景")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=ALIGNED_BLEND)
mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")

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
print(f"MH Body: {len(mh_body.data.vertices):,} verts")
print(f"Size: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")

# ============================================================
# Step 2: 计算每个顶点的曲率特征
# ============================================================
print("\n" + "="*60)
print("Step 2: 计算曲率特征")
print("="*60)

mesh = mh_body.data
mesh.update()

# 构建邻接表
adj = [set() for _ in range(len(mesh.vertices))]
for e in mesh.edges:
    adj[e.vertices[0]].add(e.vertices[1])
    adj[e.vertices[1]].add(e.vertices[0])
adj = [list(s) for s in adj]

# 计算每个顶点的"凹陷度"（基于邻居高度差）
# 关节处（肘窝/膝盖窝/腋下）通常是局部凹陷
print("计算顶点凹陷度...")

depression_scores = []
for i, v in enumerate(mesh.vertices):
    if not adj[i]:
        depression_scores.append(0)
        continue
    
    # 邻居平均位置
    avg_pos = Vector((0,0,0))
    for ni in adj[i]:
        avg_pos += mesh.vertices[ni].co
    avg_pos /= len(adj[i])
    
    # 凹陷度 = 顶点法线方向与(顶点-邻居平均)的点积
    # 凹陷处：顶点低于邻居平均，法线向外
    to_center = avg_pos - v.co
    depression = v.normal.dot(to_center)
    depression_scores.append(depression)

depression_scores = np.array(depression_scores)
print(f"凹陷度范围: {depression_scores.min():.4f} to {depression_scores.max():.4f}")

# ============================================================
# Step 3: 按Z轴分层，找局部凹陷点
# ============================================================
print("\n" + "="*60)
print("Step 3: 按Z轴分层检测关节")
print("="*60)

# 将身体按Z轴分为多个层
z_min, z_max = bbox['min'].z, bbox['max'].z
z_layers = {
    'ankle': (z_min + bbox['size'].z * 0.00, z_min + bbox['size'].z * 0.10),
    'knee': (z_min + bbox['size'].z * 0.20, z_min + bbox['size'].z * 0.35),
    'hip': (z_min + bbox['size'].z * 0.45, z_min + bbox['size'].z * 0.52),
    'pelvis': (z_min + bbox['size'].z * 0.52, z_min + bbox['size'].z * 0.58),
    'chest': (z_min + bbox['size'].z * 0.70, z_min + bbox['size'].z * 0.80),
    'shoulder': (z_min + bbox['size'].z * 0.78, z_min + bbox['size'].z * 0.85),
    'elbow': (z_min + bbox['size'].z * 0.55, z_min + bbox['size'].z * 0.68),
    'wrist': (z_min + bbox['size'].z * 0.35, z_min + bbox['size'].z * 0.48),
    'neck': (z_min + bbox['size'].z * 0.85, z_min + bbox['size'].z * 0.92),
}

# 在每层中找凹陷度最高的点（可能是关节窝）
landmarks = {}

for joint_name, (z_start, z_end) in z_layers.items():
    # 收集该层顶点
    layer_verts = []
    for i, v in enumerate(mesh.vertices):
        if z_start <= v.co.z <= z_end:
            layer_verts.append((i, depression_scores[i], v.co.copy()))
    
    if not layer_verts:
        print(f"  {joint_name}: 无顶点")
        continue
    
    # 按凹陷度排序，取前5个候选
    layer_verts.sort(key=lambda x: x[1], reverse=True)
    candidates = layer_verts[:5]
    
    print(f"\n  {joint_name}层 (Z {z_start:.2f}-{z_end:.2f}):")
    print(f"    顶点数: {len(layer_verts)}")
    
    # 对于左右对称关节，需要分左右
    if joint_name in ['ankle', 'knee', 'hip', 'shoulder', 'elbow', 'wrist']:
        # 找左侧（X < center_x）
        left_candidates = [c for c in candidates if c[2].x < bbox['center'].x]
        right_candidates = [c for c in candidates if c[2].x >= bbox['center'].x]
        
        if left_candidates:
            best = left_candidates[0]
            landmarks[f"{joint_name}_l"] = best[0]
            print(f"    左: vertex {best[0]} (depression={best[1]:.4f}, X={best[2].x:.3f})")
        
        if right_candidates:
            best = right_candidates[0]
            landmarks[f"{joint_name}_r"] = best[0]
            print(f"    右: vertex {best[0]} (depression={best[1]:.4f}, X={best[2].x:.3f})")
    else:
        # 中线关节
        best = candidates[0]
        landmarks[joint_name] = best[0]
        print(f"    中: vertex {best[0]} (depression={best[1]:.4f}, X={best[2].x:.3f})")

# ============================================================
# Step 4: 保存
# ============================================================
print("\n" + "="*60)
print("Step 4: 保存")
print("="*60)

landmarks_path = os.path.join(OUT_DIR, "body_landmarks_topo.json")
with open(landmarks_path, 'w') as f:
    json.dump(landmarks, f, indent=2)

print(f"特征点保存: {landmarks_path}")
print(f"共检测: {len(landmarks)} 个特征点")

blend_path = os.path.join(OUT_DIR, "landmarks_topo.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

print("\nDONE")
