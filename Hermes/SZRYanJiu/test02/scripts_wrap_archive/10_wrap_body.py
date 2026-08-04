import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
ALIGNED_BLEND = os.path.join(ROOT, "output", "wrap", "aligned_scene.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")

print("="*60)
print("Step 1: 导入并包裹")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=ALIGNED_BLEND)

mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")
tripo = bpy.data.objects.get("Tripo_Tripo_HighPoly")

print(f"MH Body: {len(mh_body.data.vertices):,} verts")
print(f"Tripo: {len(tripo.data.vertices):,} verts")

# 确保MH Body是活动对象
bpy.context.view_layer.objects.active = mh_body
mh_body.select_set(True)

# ============================================================
# Step 2: Shrinkwrap包裹
# ============================================================
print("\n" + "="*60)
print("Step 2: Shrinkwrap包裹")
print("="*60)

# 添加Shrinkwrap修改器
sw = mh_body.modifiers.new("Shrinkwrap", 'SHRINKWRAP')
sw.target = tripo
sw.wrap_method = 'NEAREST_SURFACEPOINT'
sw.wrap_mode = 'ON_SURFACE'
sw.offset = 0.0

# 应用修改器
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
# Step 4: 保存
# ============================================================
print("\n" + "="*60)
print("Step 4: 保存")
print("="*60)

blend_path = os.path.join(OUT_DIR, "wrapped_body.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

# 验证包裹结果
mesh = mh_body.data
mesh.update()

# 计算与Tripo的距离
from mathutils.kdtree import KDTree

# 采样Tripo顶点
tripo_verts = [tripo.matrix_world @ v.co for v in tripo.data.vertices]
step = max(1, len(tripo_verts) // 100000)
kdt = KDTree(len(tripo_verts[::step]))
for i, v in enumerate(tripo_verts[::step]):
    kdt.insert(v, i)
kdt.balance()

# 计算MH Body顶点到Tripo的距离
dists = []
for v in mesh.vertices:
    world_pos = mh_body.matrix_world @ v.co
    _, _, dist = kdt.find(world_pos)
    dists.append(dist)

import numpy as np
dists = np.array(dists)
print(f"\n包裹精度:")
print(f"  平均距离: {dists.mean()*1000:.2f}mm")
print(f"  最大距离: {dists.max()*1000:.2f}mm")
print(f"  <1mm: {(dists < 0.001).sum() / len(dists) * 100:.1f}%")
print(f"  <2mm: {(dists < 0.002).sum() / len(dists) * 100:.1f}%")

print("\nDONE")
