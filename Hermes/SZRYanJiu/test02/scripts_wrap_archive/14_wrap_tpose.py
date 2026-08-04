import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh
import numpy as np

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
TPOSE_BLEND = os.path.join(ROOT, "output", "wrap", "metahuman_tpose_v2.blend")
TRIPO_BLEND = os.path.join(ROOT, "output", "tripo_tpose_prepared_v3.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")

print("="*60)
print("Step 1: 导入T-pose MetaHuman和Tripo")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=TPOSE_BLEND)
mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")

# 保存当前场景到临时文件
temp_blend = os.path.join(OUT_DIR, "temp_mh.blend")
bpy.ops.wm.save_as_mainfile(filepath=temp_blend)

# 导入Tripo
bpy.ops.wm.open_mainfile(filepath=TRIPO_BLEND)
tripo_meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
tripo = max(tripo_meshes, key=lambda m: len(m.data.vertices))
tripo.name = "Tripo_HighPoly"

# 追加MetaHuman
with bpy.data.libraries.load(temp_blend) as (data_from, data_to):
    data_to.objects = data_from.objects

for obj in data_to.objects:
    if obj is not None and obj.type == 'MESH':
        bpy.context.collection.objects.link(obj)

mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")

print(f"MH Body: {len(mh_body.data.vertices):,} verts")
print(f"Tripo: {len(tripo.data.vertices):,} verts")

# ============================================================
# Step 2: Shrinkwrap包裹
# ============================================================
print("\n" + "="*60)
print("Step 2: Shrinkwrap包裹")
print("="*60)

bpy.context.view_layer.objects.active = mh_body
mh_body.select_set(True)

sw = mh_body.modifiers.new("Shrinkwrap", 'SHRINKWRAP')
sw.target = tripo
sw.wrap_method = 'NEAREST_SURFACEPOINT'
sw.wrap_mode = 'ON_SURFACE'
sw.offset = 0.0

bpy.ops.object.modifier_apply(modifier="Shrinkwrap")

print("Shrinkwrap应用完成")

# ============================================================
# Step 3: Corrective Smooth
# ============================================================
print("\n" + "="*60)
print("Step 3: Corrective Smooth")
print("="*60)

cs = mh_body.modifiers.new("CorrectiveSmooth", 'CORRECTIVE_SMOOTH')
cs.iterations = 3
cs.smooth_type = 'SIMPLE'
cs.factor = 0.2

bpy.ops.object.modifier_apply(modifier="CorrectiveSmooth")

print("Corrective Smooth应用完成")

# ============================================================
# Step 4: 验证
# ============================================================
print("\n" + "="*60)
print("Step 4: 验证")
print("="*60)

mesh = mh_body.data
mesh.update()

from mathutils.kdtree import KDTree

tripo_verts = [tripo.matrix_world @ v.co for v in tripo.data.vertices]
step = max(1, len(tripo_verts) // 100000)
kdt = KDTree(len(tripo_verts[::step]))
for i, v in enumerate(tripo_verts[::step]):
    kdt.insert(v, i)
kdt.balance()

dists = []
for v in mesh.vertices:
    world_pos = mh_body.matrix_world @ v.co
    _, _, dist = kdt.find(world_pos)
    dists.append(dist)

dists = np.array(dists)
print(f"包裹精度:")
print(f"  平均距离: {dists.mean()*1000:.2f}mm")
print(f"  最大距离: {dists.max()*1000:.2f}mm")
print(f"  <1mm: {(dists < 0.001).sum() / len(dists) * 100:.1f}%")
print(f"  <2mm: {(dists < 0.002).sum() / len(dists) * 100:.1f}%")

# ============================================================
# Step 5: 保存
# ============================================================
print("\n" + "="*60)
print("Step 5: 保存")
print("="*60)

blend_path = os.path.join(OUT_DIR, "wrapped_tpose.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

print("\nDONE")
