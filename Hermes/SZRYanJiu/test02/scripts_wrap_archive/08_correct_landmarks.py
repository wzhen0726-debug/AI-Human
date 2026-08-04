import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
LANDMARKS_BLEND = os.path.join(ROOT, "output", "wrap", "landmarks_topo_v2.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")

print("="*60)
print("Step 1: 导入并手动修正特征点")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=LANDMARKS_BLEND)
mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")

with open(os.path.join(OUT_DIR, "body_landmarks_topo_v2.json")) as f:
    landmarks = json.load(f)

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

# ============================================================
# Step 2: 基于对称性修正特征点
# ============================================================
print("\n" + "="*60)
print("Step 2: 基于对称性修正特征点")
print("="*60)

# 构建邻接表
adj = [set() for _ in range(len(mesh.vertices))]
for e in mesh.edges:
    adj[e.vertices[0]].add(e.vertices[1])
    adj[e.vertices[1]].add(e.vertices[0])
adj = [list(s) for s in adj]

def find_mirror_vertex(mesh, left_idx, center_x, search_radius=0.05):
    """基于左侧顶点找右侧镜像顶点"""
    left_pos = mesh.vertices[left_idx].co
    target_x = 2 * center_x - left_pos.x
    target_pos = Vector((target_x, left_pos.y, left_pos.z))
    
    best_idx = -1
    best_dist = float('inf')
    
    # 在目标位置附近搜索
    for i, v in enumerate(mesh.vertices):
        dist = (v.co - target_pos).length
        if dist < search_radius and dist < best_dist:
            best_dist = dist
            best_idx = i
    
    return best_idx, best_dist

# 修正缺失的右侧特征点
missing_right = ['knee_r']
for name in missing_right:
    left_name = name.replace('_r', '_l')
    if left_name in landmarks:
        left_idx = landmarks[left_name]
        right_idx, dist = find_mirror_vertex(mesh, left_idx, bbox['center'].x, 0.1)
        if right_idx >= 0:
            landmarks[name] = right_idx
            pos = mesh.vertices[right_idx].co
            print(f"  {name}: vertex {right_idx} (mirror of {left_name}, dist={dist*1000:.1f}mm)")

# 修正不对称的特征点（基于Z坐标一致性）
asymmetric_pairs = [
    ('ankle_l', 'ankle_r'),
    ('hip_l', 'hip_r'),
    ('shoulder_l', 'shoulder_r'),
    ('wrist_l', 'wrist_r'),
]

for left_name, right_name in asymmetric_pairs:
    if left_name in landmarks and right_name in landmarks:
        left_pos = mesh.vertices[landmarks[left_name]].co
        right_pos = mesh.vertices[landmarks[right_name]].co
        
        # 如果Z坐标差异太大，修正右侧
        if abs(left_pos.z - right_pos.z) > 0.05:
            print(f"  修正 {right_name}: Z {right_pos.z:.3f} → {left_pos.z:.3f}")
            # 在左侧Z高度找右侧顶点
            target_z = left_pos.z
            target_x = 2 * bbox['center'].x - left_pos.x
            
            best_idx = -1
            best_dist = float('inf')
            for i, v in enumerate(mesh.vertices):
                # 在右侧，Z接近目标，X接近镜像
                if v.co.x > bbox['center'].x:
                    dist = (v.co - Vector((target_x, v.co.y, target_z))).length
                    if dist < best_dist:
                        best_dist = dist
                        best_idx = i
            
            if best_idx >= 0 and best_dist < 0.1:
                landmarks[right_name] = best_idx
                print(f"    修正后: vertex {best_idx} (dist={best_dist*1000:.1f}mm)")

# ============================================================
# Step 3: 验证修正结果
# ============================================================
print("\n" + "="*60)
print("Step 3: 验证修正结果")
print("="*60)

pairs = [
    ('ankle_l', 'ankle_r'),
    ('knee_l', 'knee_r'),
    ('hip_l', 'hip_r'),
    ('shoulder_l', 'shoulder_r'),
    ('elbow_l', 'elbow_r'),
    ('wrist_l', 'wrist_r'),
]

print(f"{'左名称':<12} {'左X':>8} {'左Z':>8} | {'右名称':<12} {'右X':>8} {'右Z':>8} | {'dX':>6} {'dZ':>6} {'状态':>6}")
print('-' * 80)

for left_name, right_name in pairs:
    if left_name in landmarks and right_name in landmarks:
        lp = mesh.vertices[landmarks[left_name]].co
        rp = mesh.vertices[landmarks[right_name]].co
        dx = abs(abs(lp.x) - abs(rp.x))
        dz = abs(lp.z - rp.z)
        status = 'OK' if dx < 0.05 and dz < 0.05 else 'BAD'
        print(f'{left_name:<12} {lp.x:>8.3f} {lp.z:>8.3f} | {right_name:<12} {rp.x:>8.3f} {rp.z:>8.3f} | {dx:>6.3f} {dz:>6.3f} {status:>6}')
    elif left_name in landmarks:
        lp = mesh.vertices[landmarks[left_name]].co
        print(f'{left_name:<12} {lp.x:>8.3f} {lp.z:>8.3f} | {"MISSING":<12}')

# 保存修正后的特征点
landmarks_path = os.path.join(OUT_DIR, "body_landmarks_corrected.json")
with open(landmarks_path, 'w') as f:
    json.dump(landmarks, f, indent=2)

print(f"\n修正后特征点保存: {landmarks_path}")
print(f"共 {len(landmarks)} 个特征点")

# ============================================================
# Step 4: 保存
# ============================================================
blend_path = os.path.join(OUT_DIR, "landmarks_corrected.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

print("\nDONE")
