import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
METAHUMAN_BLEND = os.path.join(ROOT, "output", "metahuman_rotated.blend")
TRIPO_BLEND = os.path.join(ROOT, "output", "tripo_tpose_prepared_v3.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")
os.makedirs(OUT_DIR, exist_ok=True)

print("="*60)
print("Step 1: 导入MetaHuman和Tripo")
print("="*60)

# 导入MetaHuman
bpy.ops.wm.open_mainfile(filepath=METAHUMAN_BLEND)
mh_meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
mh_body = None
mh_head = None
for m in mh_meshes:
    if 'Body' in m.name:
        mh_body = m
    elif 'Head' in m.name:
        mh_head = m

if not mh_body:
    mh_body = max(mh_meshes, key=lambda m: len(m.data.vertices))

print(f"MetaHuman Body: {mh_body.name} ({len(mh_body.data.vertices):,} verts)")
if mh_head:
    print(f"MetaHuman Head: {mh_head.name} ({len(mh_head.data.vertices):,} verts)")

# 导入Tripo
bpy.ops.wm.open_mainfile(filepath=TRIPO_BLEND)
tripo_meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
tripo = max(tripo_meshes, key=lambda m: len(m.data.vertices))
tripo.name = "Tripo_HighPoly"

print(f"Tripo: {tripo.name} ({len(tripo.data.vertices):,} verts)")

# 合并到同一场景
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 重新导入MetaHuman
bpy.ops.wm.open_mainfile(filepath=METAHUMAN_BLEND)
mh_meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
for m in mh_meshes:
    m.name = "MH_" + m.name

# 追加Tripo
with bpy.data.libraries.load(TRIPO_BLEND) as (data_from, data_to):
    data_to.objects = data_from.objects

for obj in data_to.objects:
    if obj is not None and obj.type == 'MESH':
        obj.name = "Tripo_" + obj.name
        bpy.context.collection.objects.link(obj)

# 获取最终对象
mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")
mh_head = bpy.data.objects.get("MH_NewMetaHumanCharacter_Head")
tripo = bpy.data.objects.get("Tripo_Tripo_HighPoly")

if not tripo:
    # 找最大的Tripo网格
    tripo_meshes = [o for o in bpy.data.objects if o.name.startswith("Tripo_") and o.type == 'MESH']
    tripo = max(tripo_meshes, key=lambda m: len(m.data.vertices))

print(f"\n最终对象:")
print(f"  MH Body: {mh_body.name if mh_body else 'NOT FOUND'}")
print(f"  MH Head: {mh_head.name if mh_head else 'NOT FOUND'}")
print(f"  Tripo: {tripo.name} ({len(tripo.data.vertices):,} verts)")

# ============================================================
# Step 2: 对齐比例
# ============================================================
print("\n" + "="*60)
print("Step 2: 对齐比例")
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

bbox_tripo = get_bbox(tripo)
bbox_mh = get_bbox(mh_body)

print(f"Tripo: X={bbox_tripo['size'].x:.3f} Y={bbox_tripo['size'].y:.3f} Z={bbox_tripo['size'].z:.3f}")
print(f"MetaHuman: X={bbox_mh['size'].x:.3f} Y={bbox_mh['size'].y:.3f} Z={bbox_mh['size'].z:.3f}")

# 缩放MetaHuman到Tripo身高
scale_z = bbox_tripo['size'].z / bbox_mh['size'].z
print(f"\nZ轴缩放因子: {scale_z:.3f}")

for m in [mh_body, mh_head]:
    if m:
        m.scale = (scale_z, scale_z, scale_z)

bpy.context.view_layer.update()

# 应用缩放
for m in [mh_body, mh_head]:
    if m:
        bpy.context.view_layer.objects.active = m
        m.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        m.select_set(False)

bbox_mh = get_bbox(mh_body)
print(f"缩放后MetaHuman: X={bbox_mh['size'].x:.3f} Y={bbox_mh['size'].y:.3f} Z={bbox_mh['size'].z:.3f}")

# ============================================================
# Step 3: 对齐位置
# ============================================================
print("\n" + "="*60)
print("Step 3: 对齐位置")
print("="*60)

# 对齐中心点
offset = bbox_tripo['center'] - bbox_mh['center']
print(f"中心偏移: ({offset.x:.3f}, {offset.y:.3f}, {offset.z:.3f})")

for m in [mh_body, mh_head]:
    if m:
        m.location += offset

bpy.context.view_layer.update()

# 对齐Z轴底部（脚）
bbox_mh = get_bbox(mh_body)
z_offset = bbox_tripo['min'].z - bbox_mh['min'].z
print(f"Z轴底部偏移: {z_offset:.3f}")

for m in [mh_body, mh_head]:
    if m:
        m.location.z += z_offset

bpy.context.view_layer.update()

bbox_mh = get_bbox(mh_body)
print(f"对齐后MetaHuman Z范围: [{bbox_mh['min'].z:.3f}, {bbox_mh['max'].z:.3f}]")
print(f"Tripo Z范围: [{bbox_tripo['min'].z:.3f}, {bbox_tripo['max'].z:.3f}]")

# ============================================================
# Step 4: 保存对齐结果
# ============================================================
print("\n" + "="*60)
print("Step 4: 保存对齐结果")
print("="*60)

blend_path = os.path.join(OUT_DIR, "aligned_scene.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

print("\nDONE")
