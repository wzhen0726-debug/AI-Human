import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
VERTEX_BLEND = os.path.join(ROOT, "output", "wrap", "vertex_groups.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")

print("="*60)
print("Step 1: 导入并旋转手臂")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=VERTEX_BLEND)
mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")

mesh = mh_body.data
mesh.update()

# 获取顶点组
left_arm_vg = mh_body.vertex_groups.get("left_arm")
right_arm_vg = mh_body.vertex_groups.get("right_arm")

left_arm_verts = [v.index for v in mesh.vertices if left_arm_vg.index in [g.group for g in v.groups]]
right_arm_verts = [v.index for v in mesh.vertices if right_arm_vg.index in [g.group for g in v.groups]]

print(f"左臂顶点: {len(left_arm_verts)}")
print(f"右臂顶点: {len(right_arm_verts)}")

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
# Step 2: 旋转手臂到T-pose
# ============================================================
print("\n" + "="*60)
print("Step 2: 旋转手臂到T-pose")
print("="*60)

# 旋转中心：肩膀位置
left_shoulder = Vector((center_x - 0.15, 0, shoulder_z))
right_shoulder = Vector((center_x + 0.15, 0, shoulder_z))

# 左臂旋转：绕Z轴-45度（从-Y到-X）
left_rot = Matrix.Rotation(math.radians(-45), 4, 'Z')
for vi in left_arm_verts:
    v = mesh.vertices[vi]
    # 平移到肩膀原点
    local_pos = v.co - left_shoulder
    # 旋转
    rotated_pos = left_rot @ local_pos
    # 平移回去
    v.co = rotated_pos + left_shoulder

# 右臂旋转：绕Z轴+45度（从-Y到+X）
right_rot = Matrix.Rotation(math.radians(45), 4, 'Z')
for vi in right_arm_verts:
    v = mesh.vertices[vi]
    local_pos = v.co - right_shoulder
    rotated_pos = right_rot @ local_pos
    v.co = rotated_pos + right_shoulder

mesh.update()

print("手臂旋转完成")

# ============================================================
# Step 3: 保存
# ============================================================
print("\n" + "="*60)
print("Step 3: 保存")
print("="*60)

blend_path = os.path.join(OUT_DIR, "metahuman_tpose_v2.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

# 验证
bbox = get_bbox(mh_body)
print(f"\n旋转后尺寸: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")

print("\nDONE")
