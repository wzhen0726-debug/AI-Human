import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
ALIGNED_BLEND = os.path.join(ROOT, "output", "wrap", "aligned_scene.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")

print("="*60)
print("Step 1: 导入并旋转手臂")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=ALIGNED_BLEND)
mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")

mesh = mh_body.data
mesh.update()

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
center_x = bbox['center'].x
shoulder_z = bbox['min'].z + bbox['size'].z * 0.82

# ============================================================
# Step 2: 识别手臂顶点
# ============================================================
print("\n" + "="*60)
print("Step 2: 识别手臂顶点")
print("="*60)

# 基于X坐标和Z坐标识别手臂顶点
# 手臂：|X| > 0.15 且 Z > 0.5m
left_arm_verts = []
right_arm_verts = []
torso_verts = []

for i, v in enumerate(mesh.vertices):
    world_pos = mh_body.matrix_world @ v.co
    if world_pos.z > 0.5:  # 上半身
        if world_pos.x < center_x - 0.15:  # 左臂
            left_arm_verts.append(i)
        elif world_pos.x > center_x + 0.15:  # 右臂
            right_arm_verts.append(i)
        else:  # 躯干
            torso_verts.append(i)

print(f"左臂顶点: {len(left_arm_verts)}")
print(f"右臂顶点: {len(right_arm_verts)}")
print(f"躯干顶点: {len(torso_verts)}")

# ============================================================
# Step 3: 旋转手臂到T-pose
# ============================================================
print("\n" + "="*60)
print("Step 3: 旋转手臂到T-pose")
print("="*60)

# 旋转中心：肩膀位置
left_shoulder = Vector((center_x - 0.2, 0, shoulder_z))
right_shoulder = Vector((center_x + 0.2, 0, shoulder_z))

# 旋转角度：A-pose到T-pose约45度
# 左臂：从下垂(-Y方向)旋转到水平(-X方向)
# 右臂：从下垂(-Y方向)旋转到水平(+X方向)

# 左臂旋转：绕Z轴-45度（从-Y到-X）
left_rot = Matrix.Rotation(math.radians(-45), 4, 'Z')
for vi in left_arm_verts:
    v = mesh.vertices[vi]
    world_pos = mh_body.matrix_world @ v.co
    # 平移到肩膀原点
    local_pos = world_pos - left_shoulder
    # 旋转
    rotated_pos = left_rot @ local_pos
    # 平移回去
    new_world_pos = rotated_pos + left_shoulder
    # 转回局部坐标
    v.co = mh_body.matrix_world.inverted() @ new_world_pos

# 右臂旋转：绕Z轴+45度（从-Y到+X）
right_rot = Matrix.Rotation(math.radians(45), 4, 'Z')
for vi in right_arm_verts:
    v = mesh.vertices[vi]
    world_pos = mh_body.matrix_world @ v.co
    local_pos = world_pos - right_shoulder
    rotated_pos = right_rot @ local_pos
    new_world_pos = rotated_pos + right_shoulder
    v.co = mh_body.matrix_world.inverted() @ new_world_pos

mesh.update()

print("手臂旋转完成")

# ============================================================
# Step 4: 保存
# ============================================================
print("\n" + "="*60)
print("Step 4: 保存")
print("="*60)

blend_path = os.path.join(OUT_DIR, "metahuman_tpose.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

# 验证
bbox = get_bbox(mh_body)
print(f"\n旋转后尺寸: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")

print("\nDONE")
