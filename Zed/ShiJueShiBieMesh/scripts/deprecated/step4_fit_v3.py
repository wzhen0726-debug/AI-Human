"""
MH_Head_01 贴合扫描 - 改进版
修复山根贴合问题：用 ray_cast 沿法线投影替代 KDTree 最近点
"""
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
import time
import os
import json
import random

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_v2"
BASE_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB"

# ============================================================
# 0. 导入模型
# ============================================================
print("=" * 60)
print("清空场景并导入模型...")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 导入模板
template_path = os.path.join(BASE_DIR, "MetaHuman_head", "MH_Head_01.glb")
scan_path = os.path.join(BASE_DIR, "Scan_head", "Scan_Head.glb")

print(f"导入模板: {template_path}")
bpy.ops.import_scene.gltf(filepath=template_path)
template_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH' and 'Head' in obj.name:
        template_obj = obj
        break

print(f"导入扫描: {scan_path}")
bpy.ops.import_scene.gltf(filepath=scan_path)
scan_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH' and 'Scan' in obj.name:
        scan_obj = obj
        break

if not template_obj or not scan_obj:
    print("错误: 找不到模型!")
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            print(f"  {obj.name}: {len(obj.data.vertices)} verts")
    raise SystemExit(1)

tm = template_obj.matrix_world
tm_inv = tm.inverted()
sm = scan_obj.matrix_world
sm_inv = sm.inverted()
scan_n = len(scan_obj.data.vertices)

print(f"模板: {template_obj.name} ({len(template_obj.data.vertices):,} verts)")
print(f"扫描: {scan_obj.name} ({scan_n:,} verts)")

# ============================================================
# 1. 检查对齐
# ============================================================
print("\n" + "=" * 60)
print("检查对齐...")

t_verts = [tm @ v.co for v in template_obj.data.vertices]
t_xs, t_ys, t_zs = [v.x for v in t_verts], [v.y for v in t_verts], [v.z for v in t_verts]
t_center = ((min(t_xs)+max(t_xs))/2, (min(t_ys)+max(t_ys))/2, (min(t_zs)+max(t_zs))/2)

sample_indices = random.sample(range(scan_n), min(100000, scan_n))
s_verts = [sm @ scan_obj.data.vertices[i].co for i in sample_indices]
s_xs, s_ys, s_zs = [v.x for v in s_verts], [v.y for v in s_verts], [v.z for v in s_verts]
s_center = ((min(s_xs)+max(s_xs))/2, (min(s_ys)+max(s_ys))/2, (min(s_zs)+max(s_zs))/2)

offset = [s_center[i] - t_center[i] for i in range(3)]
print(f"中心偏移: ({offset[0]:.3f}, {offset[1]:.3f}, {offset[2]:.3f})")

# 刚性对齐
if abs(offset[0]) > 0.01 or abs(offset[1]) > 0.01 or abs(offset[2]) > 0.01:
    print(f"执行刚性对齐...")
    template_obj.location.x += offset[0]
    template_obj.location.y += offset[1]
    template_obj.location.z += offset[2]
    bpy.context.view_layer.update()

# ============================================================
# 2. 阶段1：KDTree 粗贴合
# ============================================================
print("\n" + "=" * 60)
print("阶段1: KDTree 粗贴合...")

SAMPLE_COUNT = 300000
sample_step = max(1, scan_n // SAMPLE_COUNT)
kd = KDTree(scan_n // sample_step + 1)
for i in range(0, scan_n, sample_step):
    co = sm @ scan_obj.data.vertices[i].co
    kd.insert(co, i)
kd.balance()
print(f"KDTree: {scan_n // sample_step + 1:,} 点")

n_verts = len(template_obj.data.vertices)
edges = [(e.vertices[0], e.vertices[1]) for e in template_obj.data.edges]
adjacency = {i: [] for i in range(n_verts)}
for a, b in edges:
    adjacency[a].append(b)
    adjacency[b].append(a)

V = np.array([tm @ v.co for v in template_obj.data.vertices])

for it in range(15):
    t_iter = time.time()
    C = np.zeros_like(V)
    for i in range(n_verts):
        co, idx, dist = kd.find(tuple(V[i]))
        C[i] = co
    
    alpha = 0.5 if it < 5 else (0.3 if it < 10 else 0.15)
    V_new = V + alpha * (C - V)
    
    for i in range(n_verts):
        nbrs = adjacency[i]
        if len(nbrs) == 0: continue
        avg = np.mean([V_new[j] for j in nbrs], axis=0)
        V_new[i] = V_new[i] * 0.5 + avg * 0.5
    
    V = V_new
    errs = np.linalg.norm(V - C, axis=1)
    print(f"  粗贴 {it+1:2d}/15 | 误差 {np.mean(errs)*1000:.3f}mm | {time.time()-t_iter:.1f}s")

# 写回
for i, v in enumerate(template_obj.data.vertices):
    v.co = tm_inv @ Vector(V[i])
template_obj.data.update()

# ============================================================
# 3. 阶段2：ray_cast 精贴合（修复山根凹陷）
# ============================================================
print("\n" + "=" * 60)
print("阶段2: ray_cast 精贴合（修复凹陷区域）...")

# 计算模板顶点法线（用 BMesh）
bm = bmesh.new()
bm.from_mesh(template_obj.data)
bm.verts.ensure_lookup_table()
bm.faces.ensure_lookup_table()

vertex_normals = {}
for v in bm.verts:
    normal = Vector((0, 0, 0))
    for f in v.link_faces:
        normal += f.normal
    if normal.length > 0:
        normal.normalize()
    vertex_normals[v.index] = normal

# 更新模板世界矩阵
tm = template_obj.matrix_world
tm_inv = tm.inverted()
sm = scan_obj.matrix_world
sm_inv = sm.inverted()

V = np.array([tm @ v.co for v in template_obj.data.vertices])

for it in range(10):
    t_iter = time.time()
    hit_count = 0
    
    for i, v in enumerate(template_obj.data.vertices):
        world_co = tm @ v.co
        local_co = sm_inv @ world_co
        
        # 获取世界空间法线
        normal = vertex_normals.get(i, Vector((0, 0, 1)))
        world_normal = (tm.to_3x3() @ normal).normalized()
        local_normal = (sm_inv.to_3x3() @ world_normal).normalized()
        
        # 双向 ray_cast
        ray_origin = local_co - local_normal * 0.02  # 从略后方发射
        hit, location, hit_normal, face_index = scan_obj.ray_cast(ray_origin, local_normal, distance=0.1)
        
        if not hit:
            hit, location, hit_normal, face_index = scan_obj.ray_cast(
                local_co + local_normal * 0.02, -local_normal, distance=0.1
            )
        
        if hit:
            world_hit = sm @ location
            V[i] = world_hit
            hit_count += 1
    
    # 轻平滑
    for i in range(n_verts):
        nbrs = adjacency[i]
        if len(nbrs) == 0: continue
        avg = np.mean([V[j] for j in nbrs], axis=0)
        V[i] = V[i] * 0.7 + avg * 0.3
    
    # 写回
    for i, v in enumerate(template_obj.data.vertices):
        v.co = tm_inv @ Vector(V[i])
    template_obj.data.update()
    
    print(f"  精贴 {it+1:2d}/10 | ray_cast 命中 {hit_count}/{n_verts} | {time.time()-t_iter:.1f}s")

bm.free()

# ============================================================
# 4. 验证
# ============================================================
print("\n" + "=" * 60)
print("最终验证 (1M 采样)...")

verify_step = max(1, scan_n // 1000000)
kd_verify = KDTree(scan_n // verify_step + 1)
for i in range(0, scan_n, verify_step):
    co = sm @ scan_obj.data.vertices[i].co
    kd_verify.insert(co, i)
kd_verify.balance()

V_fitted = np.array([tm @ v.co for v in template_obj.data.vertices])
distances = []
for i in range(len(V_fitted)):
    co, idx, dist = kd_verify.find(tuple(V_fitted[i]))
    distances.append(dist)

distances = np.array(distances)
print(f"\n  平均距离: {np.mean(distances)*1000:.3f} mm")
print(f"  中位数: {np.median(distances)*1000:.3f} mm")
print(f"  最大距离: {np.max(distances)*1000:.3f} mm")
print(f"  标准差: {np.std(distances)*1000:.3f} mm")
print(f"  <0.5mm: {np.sum(distances < 0.0005) / len(distances) * 100:.1f}%")
print(f"  <1.0mm: {np.sum(distances < 0.001) / len(distances) * 100:.1f}%")
print(f"  <2.0mm: {np.sum(distances < 0.002) / len(distances) * 100:.1f}%")

# ============================================================
# 5. 保存
# ============================================================
print("\n" + "=" * 60)
print("保存结果...")
os.makedirs(OUTPUT_DIR, exist_ok=True)

blend_out = os.path.join(OUTPUT_DIR, "MH_Head_01_fitted.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_out)

template_obj.select_set(True)
bpy.context.view_layer.objects.active = template_obj

glb_out = os.path.join(OUTPUT_DIR, "MH_Head_01_fitted.glb")
bpy.ops.export_scene.gltf(
    filepath=glb_out,
    use_selection=True,
    export_format='GLB',
    export_apply=True
)

obj_out = os.path.join(OUTPUT_DIR, "MH_Head_01_fitted.obj")
bpy.ops.wm.obj_export(filepath=obj_out, export_selected_objects=True)

report = {
    "template": template_obj.name,
    "template_verts": len(template_obj.data.vertices),
    "template_faces": len(template_obj.data.polygons),
    "scan_verts_original": scan_n,
    "mean_distance_mm": float(np.mean(distances) * 1000),
    "median_distance_mm": float(np.median(distances) * 1000),
    "max_distance_mm": float(np.max(distances) * 1000),
    "std_distance_mm": float(np.std(distances) * 1000),
    "pct_under_0_5mm": float(np.sum(distances < 0.0005) / len(distances) * 100),
    "pct_under_1_0mm": float(np.sum(distances < 0.001) / len(distances) * 100),
    "pct_under_2_0mm": float(np.sum(distances < 0.002) / len(distances) * 100),
}
with open(os.path.join(OUTPUT_DIR, "quality_report.json"), 'w') as f:
    json.dump(report, f, indent=2)

print(f"Blend: {blend_out}")
print(f"GLB: {glb_out}")
print(f"OBJ: {obj_out}")
print(f"报告: {os.path.join(OUTPUT_DIR, 'quality_report.json')}")
print("\n完成!")