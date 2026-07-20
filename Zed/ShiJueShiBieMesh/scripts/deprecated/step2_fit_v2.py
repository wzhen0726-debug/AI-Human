"""
完整流程 v2：模板贴合扫描（随机采样代替 Decimate）
"""
import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
import time
import os
import json
import random

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output"
BLEND_FILE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"

# ============================================================
# 0. 加载
# ============================================================
print("=" * 60)
print("加载 blend 文件...")
t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)

template_obj = bpy.data.objects.get("MH_Head")
scan_obj = bpy.data.objects.get("Scan_Head")

if not template_obj or not scan_obj:
    print("错误: 找不到模型!")
    raise SystemExit(1)

print(f"模板: {template_obj.name} ({len(template_obj.data.vertices):,} verts)")
print(f"扫描: {scan_obj.name} ({len(scan_obj.data.vertices):,} verts)")
print(f"加载耗时: {time.time()-t0:.1f}s")

# ============================================================
# 1. 检查对齐状态
# ============================================================
print("\n" + "=" * 60)
print("检查对齐状态...")

tm = template_obj.matrix_world
sm = scan_obj.matrix_world

t_verts = [tm @ v.co for v in template_obj.data.vertices]
t_xs = [v.x for v in t_verts]
t_ys = [v.y for v in t_verts]
t_zs = [v.z for v in t_verts]
t_center = ((min(t_xs)+max(t_xs))/2, (min(t_ys)+max(t_ys))/2, (min(t_zs)+max(t_zs))/2)
t_size = (max(t_xs)-min(t_xs), max(t_ys)-min(t_ys), max(t_zs)-min(t_zs))

# 扫描只采样少量来算包围盒
scan_n = len(scan_obj.data.vertices)
sample_indices = random.sample(range(scan_n), min(100000, scan_n))
s_verts = [sm @ scan_obj.data.vertices[i].co for i in sample_indices]
s_xs = [v.x for v in s_verts]
s_ys = [v.y for v in s_verts]
s_zs = [v.z for v in s_verts]
s_center = ((min(s_xs)+max(s_xs))/2, (min(s_ys)+max(s_ys))/2, (min(s_zs)+max(s_zs))/2)
s_size = (max(s_xs)-min(s_xs), max(s_ys)-min(s_ys), max(s_zs)-min(s_zs))

print(f"模板中心: ({t_center[0]:.3f}, {t_center[1]:.3f}, {t_center[2]:.3f})")
print(f"模板尺寸: ({t_size[0]:.3f}, {t_size[1]:.3f}, {t_size[2]:.3f})")
print(f"扫描中心: ({s_center[0]:.3f}, {s_center[1]:.3f}, {s_center[2]:.3f})")
print(f"扫描尺寸: ({s_size[0]:.3f}, {s_size[1]:.3f}, {s_size[2]:.3f})")

offset = [s_center[i] - t_center[i] for i in range(3)]
print(f"中心偏移: ({offset[0]:.3f}, {offset[1]:.3f}, {offset[2]:.3f})")

ratio = [s_size[i] / t_size[i] if t_size[i] > 0 else 1 for i in range(3)]
print(f"尺寸比: ({ratio[0]:.3f}, {ratio[1]:.3f}, {ratio[2]:.3f})")

# ============================================================
# 2. 快速随机采样 KDTree（不做 Decimate）
# ============================================================
print("\n" + "=" * 60)
print("构建扫描 KDTree（随机采样）...")

SAMPLE_COUNT = 200000  # 20万采样点
sample_step = max(1, scan_n // SAMPLE_COUNT)
print(f"采样步长: {sample_step} (约 {scan_n // sample_step:,} 点)")

t0 = time.time()
kd = KDTree(scan_n // sample_step + 1)
sample_count = 0
for i in range(0, scan_n, sample_step):
    co = sm @ scan_obj.data.vertices[i].co
    kd.insert(co, i)
    sample_count += 1
kd.balance()
print(f"KDTree 构建完成: {sample_count:,} 点, 耗时 {time.time()-t0:.1f}s")

# ============================================================
# 3. 非刚性贴合
# ============================================================
print("\n" + "=" * 60)
print("非刚性贴合...")

tm_inv = tm.inverted()
n_verts = len(template_obj.data.vertices)

# 构建邻接关系
print("构建邻接关系...")
t0 = time.time()
edges = [(e.vertices[0], e.vertices[1]) for e in template_obj.data.edges]
adjacency = {i: [] for i in range(n_verts)}
for a, b in edges:
    adjacency[a].append(b)
    adjacency[b].append(a)
degree = np.array([float(len(adjacency[i])) for i in range(n_verts)], dtype=np.float64)
print(f"邻接关系构建完成: {time.time()-t0:.1f}s")

# 初始顶点位置
V = np.array([tm @ v.co for v in template_obj.data.vertices])

# 迭代贴合
print("开始迭代贴合...")
max_dist = 0.05  # 最大对应距离
total_iterations = 25

for it in range(total_iterations):
    t_iter = time.time()
    
    # 找最近点
    C = np.zeros_like(V)
    valid = 0
    for i in range(n_verts):
        co, idx, dist = kd.find(tuple(V[i]))
        C[i] = co
        if dist < max_dist:
            valid += 1
    
    # 移动步长（逐步减小）
    alpha = 0.6 if it < 5 else (0.4 if it < 10 else (0.25 if it < 15 else 0.15))
    
    # 向目标移动
    V_new = V + alpha * (C - V)
    
    # 拉普拉斯平滑
    for i in range(n_verts):
        nbrs = adjacency[i]
        if len(nbrs) == 0:
            continue
        avg = np.mean([V_new[j] for j in nbrs], axis=0)
        V_new[i] = V_new[i] * 0.5 + avg * 0.5
    
    V = V_new
    
    # 误差统计
    errs = np.linalg.norm(V - C, axis=1)
    valid_errs = errs[errs < max_dist]
    avg_err = np.mean(valid_errs) if len(valid_errs) > 0 else 0
    print(f"  迭代 {it+1:2d}/{total_iterations} | 有效 {valid:6d}/{n_verts} | "
          f"误差 {avg_err*1000:.3f}mm | 耗时 {time.time()-t_iter:.1f}s")

# 写回模板
for i, v in enumerate(template_obj.data.vertices):
    v.co = tm_inv @ Vector(V[i])

template_obj.data.update()
print("顶点已写回模板")

# ============================================================
# 4. 验证质量
# ============================================================
print("\n" + "=" * 60)
print("验证贴合质量...")

# 用原始扫描验证（更大采样率）
V_fitted = np.array([tm @ v.co for v in template_obj.data.vertices])

verify_step = max(1, scan_n // 500000)
print(f"验证采样步长: {verify_step} (约 {scan_n // verify_step:,} 点)")

t0 = time.time()
kd_verify = KDTree(scan_n // verify_step + 1)
for i in range(0, scan_n, verify_step):
    co = sm @ scan_obj.data.vertices[i].co
    kd_verify.insert(co, i)
kd_verify.balance()
print(f"验证 KDTree 构建: {time.time()-t0:.1f}s")

distances = []
for i in range(len(V_fitted)):
    co, idx, dist = kd_verify.find(tuple(V_fitted[i]))
    distances.append(dist)

distances = np.array(distances)
print(f"\n  平均距离: {np.mean(distances)*1000:.3f} mm")
print(f"  中位数距离: {np.median(distances)*1000:.3f} mm")
print(f"  最大距离: {np.max(distances)*1000:.3f} mm")
print(f"  标准差: {np.std(distances)*1000:.3f} mm")
print(f"  <0.5mm: {np.sum(distances < 0.0005) / len(distances) * 100:.1f}%")
print(f"  <1.0mm: {np.sum(distances < 0.001) / len(distances) * 100:.1f}%")
print(f"  <2.0mm: {np.sum(distances < 0.002) / len(distances) * 100:.1f}%")
print(f"  >5.0mm: {np.sum(distances > 0.005) / len(distances) * 100:.1f}%")

# ============================================================
# 5. 保存
# ============================================================
print("\n" + "=" * 60)
print("保存结果...")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 保存 blend
blend_out = os.path.join(OUTPUT_DIR, "fitted_result.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_out)
print(f"Blend: {blend_out}")

# 导出 GLB
template_obj.select_set(True)
bpy.context.view_layer.objects.active = template_obj
glb_out = os.path.join(OUTPUT_DIR, "MH_Head_fitted.glb")
bpy.ops.export_scene.gltf(
    filepath=glb_out,
    use_selection=True,
    export_format='GLB',
    export_apply=True
)
print(f"GLB: {glb_out}")

# 导出 OBJ
obj_out = os.path.join(OUTPUT_DIR, "MH_Head_fitted.obj")
bpy.ops.export_scene.obj(
    filepath=obj_out,
    use_selection=True,
    use_materials=False
)
print(f"OBJ: {obj_out}")

# 质量报告
report = {
    "template": "MH_Head",
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

print(f"\n质量报告: {os.path.join(OUTPUT_DIR, 'quality_report.json')}")

print("\n" + "=" * 60)
print("完成!")
print(f"贴合后模板: {len(template_obj.data.vertices):,} verts, {len(template_obj.data.polygons):,} faces")
print(f"拓扑完全保留，形状贴合扫描")