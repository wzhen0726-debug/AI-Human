import bpy, os, sys, math
from mathutils import Vector, Matrix
import bmesh

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
VERTEX_BLEND = os.path.join(ROOT, "output", "wrap", "vertex_groups.blend")
TRIPO_BLEND = os.path.join(ROOT, "output", "tripo_tpose_prepared_v3.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")

print("="*60)
print("正确流程: 先包裹躯干，再旋转手臂")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=VERTEX_BLEND)
mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")

# 导入Tripo
bpy.ops.wm.open_mainfile(filepath=TRIPO_BLEND)
tripo_meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
tripo = max(tripo_meshes, key=lambda m: len(m.data.vertices))
tripo.name = "Tripo_HighPoly"

# 追加MetaHuman
with bpy.data.libraries.load(VERTEX_BLEND) as (data_from, data_to):
    data_to.objects = data_from.objects

for obj in data_to.objects:
    if obj is not None and obj.type == 'MESH':
        bpy.context.collection.objects.link(obj)

mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")

mesh = mh_body.data
mesh.update()

# 获取顶点组
left_arm_vg = mh_body.vertex_groups.get("left_arm")
right_arm_vg = mh_body.vertex_groups.get("right_arm")
torso_vg = mh_body.vertex_groups.get("torso")

if not left_arm_vg or not right_arm_vg or not torso_vg:
    print("ERROR: 顶点组不存在，先运行13_analyze_verts.py")
    sys.exit(1)

left_arm_verts = [v.index for v in mesh.vertices if left_arm_vg.index in [g.group for g in v.groups]]
right_arm_verts = [v.index for v in mesh.vertices if right_arm_vg.index in [g.group for g in v.groups]]
torso_verts = [v.index for v in mesh.vertices if torso_vg.index in [g.group for g in v.groups]]

print(f"左臂: {len(left_arm_verts)} verts")
print(f"右臂: {len(right_arm_verts)} verts")
print(f"躯干: {len(torso_verts)} verts")

# ============================================================
# Step 1: 只Shrinkwrap躯干
# ============================================================
print("\n" + "="*60)
print("Step 1: 只Shrinkwrap躯干")
print("="*60)

# 创建顶点组用于Shrinkwrap
# 新建一个只包含躯干的顶点组
bpy.context.view_layer.objects.active = mh_body
mh_body.select_set(True)

# 进入编辑模式，选择躯干顶点
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.object.mode_set(mode='OBJECT')

# 选择躯干顶点
for vi in torso_verts:
    mesh.vertices[vi].select = True

# 添加Shrinkwrap，只影响选中的顶点
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')  # 先全选
bpy.ops.object.mode_set(mode='OBJECT')

# 取消手臂选择
for vi in left_arm_verts + right_arm_verts:
    mesh.vertices[vi].select = False

# 添加Shrinkwrap修改器
sw = mh_body.modifiers.new("Shrinkwrap_Torso", 'SHRINKWRAP')
sw.target = tripo
sw.wrap_method = 'NEAREST_SURFACEPOINT'
sw.wrap_mode = 'ON_SURFACE'
sw.offset = 0.0
sw.vertex_group = torso_vg.name  # 只影响躯干

bpy.ops.object.modifier_apply(modifier="Shrinkwrap_Torso")

print("躯干Shrinkwrap完成")

# ============================================================
# Step 2: 旋转手臂到T-pose
# ============================================================
print("\n" + "="*60)
print("Step 2: 旋转手臂到T-pose")
print("="*60)

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

# 旋转中心：肩膀位置
left_shoulder = Vector((center_x - 0.15, 0, shoulder_z))
right_shoulder = Vector((center_x + 0.15, 0, shoulder_z))

# 左臂旋转：绕Z轴-45度
left_rot = Matrix.Rotation(math.radians(-45), 4, 'Z')
for vi in left_arm_verts:
    v = mesh.vertices[vi]
    local_pos = v.co - left_shoulder
    rotated_pos = left_rot @ local_pos
    v.co = rotated_pos + left_shoulder

# 右臂旋转：绕Z轴+45度
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

blend_path = os.path.join(OUT_DIR, "wrapped_torso_tpose_arms.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

# 验证
bbox = get_bbox(mh_body)
print(f"\n最终尺寸: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")

print("\nDONE")
