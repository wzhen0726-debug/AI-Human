import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh
import numpy as np

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
WRAPPED_BLEND = os.path.join(ROOT, "output", "wrap", "wrapped_body.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")

print("="*60)
print("Step 1: 导入包裹结果")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=WRAPPED_BLEND)
mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")
tripo = bpy.data.objects.get("Tripo_Tripo_HighPoly")

# ============================================================
# Step 2: 特征点锚定
# ============================================================
print("\n" + "="*60)
print("Step 2: 特征点锚定")
print("="*60)

with open(os.path.join(OUT_DIR, "body_landmarks_final.json")) as f:
    landmarks = json.load(f)

mesh = mh_body.data
mesh.update()

# 构建邻接表
adj = [set() for _ in range(len(mesh.vertices))]
for e in mesh.edges:
    adj[e.vertices[0]].add(e.vertices[1])
    adj[e.vertices[1]].add(e.vertices[0])
adj = [list(s) for s in adj]

# 特征点目标位置（Tripo上的对应点）
# 由于Tripo是T-pose，MetaHuman是A-pose，手臂特征点位置不同
# 我们只锚定躯干和头部的特征点

anchors = {}
for name, idx in landmarks.items():
    if name in ['pelvis', 'chest', 'neck', 'hip_l', 'hip_r', 'knee_l', 'ankle_l', 'ankle_r']:
        anchors[idx] = mesh.vertices[idx].co.copy()

print(f"锚定 {len(anchors)} 个特征点")

# 锚定迭代
for it in range(15):
    alpha = 0.3 + 0.5 * (it / 14)
    smooth_f = 0.35 - 0.25 * (it / 14)
    
    # 锚点保持
    for vi, tgt in anchors.items():
        mesh.vertices[vi].co = mesh.vertices[vi].co.lerp(tgt, alpha)
    
    # 非锚点平滑
    new_co = [None] * len(mesh.vertices)
    for i in range(len(mesh.vertices)):
        nb = adj[i]
        if nb:
            avg = Vector((0,0,0))
            for ni in nb:
                avg += mesh.vertices[ni].co
            avg /= len(nb)
            if i in anchors:
                new_co[i] = mesh.vertices[i].co.lerp(avg, smooth_f * 0.3)
            else:
                new_co[i] = mesh.vertices[i].co.lerp(avg, smooth_f)
        else:
            new_co[i] = mesh.vertices[i].co.copy()
    
    for i in range(len(mesh.vertices)):
        mesh.vertices[i].co = new_co[i]
    
    if it % 5 == 4:
        me = max((mesh.vertices[vi].co - tgt).length for vi, tgt in anchors.items())
        print(f"  [iter {it+1}/15] max_err={me*1000:.2f}mm")

mesh.update()

# ============================================================
# Step 3: 再次Shrinkwrap
# ============================================================
print("\n" + "="*60)
print("Step 3: 再次Shrinkwrap")
print("="*60)

sw = mh_body.modifiers.new("Shrinkwrap2", 'SHRINKWRAP')
sw.target = tripo
sw.wrap_method = 'NEAREST_SURFACEPOINT'
sw.wrap_mode = 'ON_SURFACE'
sw.offset = 0.0

bpy.ops.object.modifier_apply(modifier="Shrinkwrap2")

# ============================================================
# Step 4: 最终验证
# ============================================================
print("\n" + "="*60)
print("Step 4: 最终验证")
print("="*60)

mesh.update()

# 计算与Tripo的距离
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

blend_path = os.path.join(OUT_DIR, "wrapped_body_v2.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

print("\nDONE")
