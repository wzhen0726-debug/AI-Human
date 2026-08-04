import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
LANDMARKS_BLEND = os.path.join(ROOT, "output", "wrap", "landmarks_corrected.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")

print("="*60)
print("Step 1: 导入并验证特征点")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=LANDMARKS_BLEND)
mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")

with open(os.path.join(OUT_DIR, "body_landmarks_corrected.json")) as f:
    landmarks = json.load(f)

mesh = mh_body.data
mesh.update()

# ============================================================
# Step 2: 用顶点法线验证特征点
# ============================================================
print("\n" + "="*60)
print("Step 2: 用顶点法线验证特征点")
print("="*60)

# 关节点的法线特征：
# - 腋窝/腹股沟：法线朝向身体内部（凹陷）
# - 肘窝/膝盖窝：法线朝向弯曲方向

for name, idx in sorted(landmarks.items()):
    if idx < len(mesh.vertices):
        v = mesh.vertices[idx]
        world_pos = mh_body.matrix_world @ v.co
        world_normal = v.normal.copy()
        world_normal.rotate(mh_body.matrix_world.to_3x3())
        
        print(f"{name:15s}: pos=({world_pos.x:6.3f}, {world_pos.y:6.3f}, {world_pos.z:6.3f}) normal=({world_normal.x:6.3f}, {world_normal.y:6.3f}, {world_normal.z:6.3f})")

# ============================================================
# Step 3: 基于特征点创建顶点组
# ============================================================
print("\n" + "="*60)
print("Step 3: 创建顶点组")
print("="*60)

# 为每个特征点创建顶点组（用于后续包裹）
for name, idx in landmarks.items():
    if idx < len(mesh.vertices):
        # 检查是否已存在
        vg = mh_body.vertex_groups.get(name)
        if not vg:
            vg = mh_body.vertex_groups.new(name=name)
        vg.add([idx], 1.0, 'REPLACE')
        print(f"  创建顶点组: {name} (vertex {idx})")

# ============================================================
# Step 4: 保存
# ============================================================
print("\n" + "="*60)
print("Step 4: 保存")
print("="*60)

blend_path = os.path.join(OUT_DIR, "landmarks_final.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

# 保存最终特征点
final_path = os.path.join(OUT_DIR, "body_landmarks_final.json")
with open(final_path, 'w') as f:
    json.dump(landmarks, f, indent=2)
print(f"特征点: {final_path}")

print("\nDONE")
