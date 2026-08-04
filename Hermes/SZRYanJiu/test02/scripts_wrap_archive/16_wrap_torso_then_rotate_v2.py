import bpy, os, sys, math
from mathutils import Vector, Matrix
import bmesh

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
VERTEX_BLEND = os.path.join(ROOT, "output", "wrap", "vertex_groups.blend")
TRIPO_BLEND = os.path.join(ROOT, "output", "tripo_tpose_prepared_v3.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")

print("="*60)
print("重新分类并旋转手臂（修正右臂上部遗漏）")
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

# ============================================================
# Step 1: 重新分类手臂顶点（基于Z坐标和X坐标）
# ============================================================
print("\n" + "="*60)
print("Step 1: 重新分类手臂顶点")
print("="*60)

# 手臂：Z > 1.0 且 |X - center_x| > 0.1
# 但更关键的是：基于与肩膀的距离
shoulder_z = bbox['min'].z + bbox['size'].z * 0.82
left_shoulder = Vector((center_x - 0.15, 0, shoulder_z))
right_shoulder = Vector((center_x + 0.15, 0, shoulder_z))

left_arm_verts = []
right_arm_verts = []
torso_verts = []

for i, v in enumerate(mesh.vertices):
    if v.co.z > 1.0:  # 上半身
        # 计算到左右肩膀的距离
        dist_left = (v.co - left_shoulder).length
        dist_right = (v.co - right_shoulder).length
        
        # 如果离左肩更近，是左臂
        if dist_left < dist_right and dist_left < 0.5:
            left_arm_verts.append(i)
        # 如果离右肩更近，是右臂
        elif dist_right < dist_left and dist_right < 0.5:
            right_arm_verts.append(i)
        else:
            torso_verts.append(i)
    else:
        torso_verts.append(i)

print(f"左臂: {len(left_arm_verts)} verts")
print(f"右臂: {len(right_arm_verts)} verts")
print(f"躯干: {len(torso_verts)} verts")

# ============================================================
# Step 2: 只Shrinkwrap躯干
# ============================================================
print("\n" + "="*60)
print("Step 2: 只Shrinkwrap躯干")
print("="*60)

# 创建顶点组
for name, verts in [('left_arm', left_arm_verts), ('right_arm', right_arm_verts), ('torso', torso_verts)]:
    vg = mh_body.vertex_groups.get(name)
    if not vg:
        vg = mh_body.vertex_groups.new(name=name)
    vg.add(verts, 1.0, 'REPLACE')

# Shrinkwrap躯干
sw = mh_body.modifiers.new("Shrinkwrap_Torso", 'SHRINKWRAP')
sw.target = tripo
sw.wrap_method = 'NEAREST_SURFACEPOINT'
sw.wrap_mode = 'ON_SURFACE'
sw.offset = 0.0

# 创建只包含躯干的顶点组
torso_only_vg = mh_body.vertex_groups.new(name="torso_only")
torso_only_vg.add(torso_verts, 1.0, 'REPLACE')
sw.vertex_group = torso_only_vg.name

bpy.ops.object.modifier_apply(modifier="Shrinkwrap_Torso")

print("躯干Shrinkwrap完成")

# ============================================================
# Step 3: 旋转手臂到T-pose
# ============================================================
print("\n" + "="*60)
print("Step 3: 旋转手臂到T-pose")
print("="*60)

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
# Step 4: 保存
# ============================================================
print("\n" + "="*60)
print("Step 4: 保存")
print("="*60)

blend_path = os.path.join(OUT_DIR, "wrapped_torso_tpose_arms_v2.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

# 验证
bbox = get_bbox(mh_body)
print(f"\n最终尺寸: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")

print("\nDONE")
