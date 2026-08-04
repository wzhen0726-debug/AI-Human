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
mesh = mh_body.data
mesh.update()

# 构建邻接表
adj = [set() for _ in range(len(mesh.vertices))]
for e in mesh.edges:
    adj[e.vertices[0]].add(e.vertices[1])
    adj[e.vertices[1]].add(e.vertices[0])
adj = [list(s) for s in adj]

# ============================================================
# Step 2: 改进的关节检测 - 基于几何特征和位置约束
# ============================================================
print("\n" + "="*60)
print("Step 2: 改进的关节检测")
print("="*60)

# 计算凹陷度
depression_scores = []
for i, v in enumerate(mesh.vertices):
    if not adj[i]:
        depression_scores.append(0)
        continue
    avg_pos = Vector((0,0,0))
    for ni in adj[i]:
        avg_pos += mesh.vertices[ni].co
    avg_pos /= len(adj[i])
    to_center = avg_pos - v.co
    depression = v.normal.dot(to_center)
    depression_scores.append(depression)

depression_scores = np.array(depression_scores)

# 改进的层定义 - 更精确的Z范围
z_min, z_max = bbox['min'].z, bbox['max'].z
z_size = bbox['size'].z

# 定义关节层（更精确的Z范围和X约束）
joint_layers = {
    'ankle': {
        'z_range': (z_min + z_size * 0.02, z_min + z_size * 0.08),
        'x_constraint': 'both',  # 左右都要
        'x_offset': 0.10,  # 预期X偏移
    },
    'knee': {
        'z_range': (z_min + z_size * 0.25, z_min + z_size * 0.32),
        'x_constraint': 'both',
        'x_offset': 0.08,
    },
    'hip': {
        'z_range': (z_min + z_size * 0.48, z_min + z_size * 0.52),
        'x_constraint': 'both',
        'x_offset': 0.12,
    },
    'shoulder': {
        'z_range': (z_min + z_size * 0.78, z_min + z_size * 0.85),
        'x_constraint': 'both',
        'x_offset': 0.20,
    },
    'elbow': {
        'z_range': (z_min + z_size * 0.58, z_min + z_size * 0.68),
        'x_constraint': 'both',
        'x_offset': 0.25,
    },
    'wrist': {
        'z_range': (z_min + z_size * 0.38, z_min + z_size * 0.45),
        'x_constraint': 'both',
        'x_offset': 0.30,
    },
    'pelvis': {
        'z_range': (z_min + z_size * 0.53, z_min + z_size * 0.57),
        'x_constraint': 'center',
    },
    'chest': {
        'z_range': (z_min + z_size * 0.72, z_min + z_size * 0.78),
        'x_constraint': 'center',
    },
    'neck': {
        'z_range': (z_min + z_size * 0.86, z_min + z_size * 0.90),
        'x_constraint': 'center',
    },
}

landmarks = {}

for joint_name, config in joint_layers.items():
    z_start, z_end = config['z_range']
    
    # 收集该层顶点
    layer_verts = []
    for i, v in enumerate(mesh.vertices):
        if z_start <= v.co.z <= z_end:
            layer_verts.append((i, depression_scores[i], v.co.copy()))
    
    if not layer_verts:
        print(f"  {joint_name}: 无顶点")
        continue
    
    # 按凹陷度排序
    layer_verts.sort(key=lambda x: x[1], reverse=True)
    
    if config['x_constraint'] == 'center':
        # 中线关节：找X接近中心的凹陷点
        center_candidates = [c for c in layer_verts if abs(c[2].x - bbox['center'].x) < 0.05]
        if center_candidates:
            best = center_candidates[0]
            landmarks[joint_name] = best[0]
            print(f"  {joint_name}: vertex {best[0]} (depression={best[1]:.4f}, X={best[2].x:.3f})")
        else:
            # 放宽约束
            best = layer_verts[0]
            landmarks[joint_name] = best[0]
            print(f"  {joint_name}: vertex {best[0]} (fallback, X={best[2].x:.3f})")
    
    else:
        # 左右关节：分别找左右侧
        x_off = config.get('x_offset', 0.1)
        
        # 左侧：X < center_x，且凹陷度高
        left_candidates = [c for c in layer_verts if c[2].x < bbox['center'].x]
        if left_candidates:
            # 优先找X接近预期位置的
            left_candidates.sort(key=lambda c: abs(c[2].x - (bbox['center'].x - x_off)))
            best_left = left_candidates[0]
            landmarks[f"{joint_name}_l"] = best_left[0]
            print(f"  {joint_name}_l: vertex {best_left[0]} (X={best_left[2].x:.3f}, dep={best_left[1]:.4f})")
        
        # 右侧：X >= center_x
        right_candidates = [c for c in layer_verts if c[2].x >= bbox['center'].x]
        if right_candidates:
            right_candidates.sort(key=lambda c: abs(c[2].x - (bbox['center'].x + x_off)))
            best_right = right_candidates[0]
            landmarks[f"{joint_name}_r"] = best_right[0]
            print(f"  {joint_name}_r: vertex {best_right[0]} (X={best_right[2].x:.3f}, dep={best_right[1]:.4f})")

# ============================================================
# Step 3: 保存
# ============================================================
print("\n" + "="*60)
print("Step 3: 保存")
print("="*60)

landmarks_path = os.path.join(OUT_DIR, "body_landmarks_topo_v2.json")
with open(landmarks_path, 'w') as f:
    json.dump(landmarks, f, indent=2)

print(f"特征点保存: {landmarks_path}")
print(f"共检测: {len(landmarks)} 个特征点")

blend_path = os.path.join(OUT_DIR, "landmarks_topo_v2.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

print("\nDONE")
