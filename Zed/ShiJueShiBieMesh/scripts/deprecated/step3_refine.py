"""
第二轮精贴合：加载第一次结果，缩小采样步长，减小平滑，提升精度
"""
import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
import time
import os
import json

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output"
BLEND_IN = os.path.join(OUTPUT_DIR, "fitted_result.blend")

# ============================================================
print("=" * 60)
print("加载第一轮结果...")
bpy.ops.wm.open_mainfile(filepath=BLEND_IN)

template_obj = bpy.data.objects.get("MH_Head")
scan_obj = bpy.data.objects.get("Scan_Head")

if not template_obj or not scan_obj:
    print("错误: 找不到模型!")
    raise SystemExit(1)

tm = template_obj.matrix_world
tm_inv = tm.inverted()
sm = scan_obj.matrix_world
scan_n = len(scan_obj.data.vertices)

# ============================================================
# 构建高精度 KDTree（500k 采样）
# ============================================================
print("\n构建高精度 KDTree (500k 采样)...")
SAMPLE_COUNT = 500000
sample_step = max(1, scan_n // SAMPLE_COUNT)

t0 = time.time()
kd = KDTree(scan_n // sample_step + 1)
count = 0
for i in range(0, scan_n, sample_step):
    co = sm @ scan_obj.data.vertices[i].co
    kd.insert(co, i)
    count += 1
kd.balance()
print(f"KDTree: {count:,} 点, {time.time()-t0:.1f}s")

# ============================================================
# 构建邻接关系
# ============================================================
n_verts = len(template_obj.data.vertices)
edges = [(e.vertices[0], e.vertices[1]) for e in template_obj.data.edges]
adjacency = {i: [] for i in range(n_verts)}
for a, b in edges:
    adjacency[a].append(b)
    adjacency[b].append(a)

# ============================================================
# 精贴合：更小步长，更少平滑
# ============================================================
print("\n精贴合 (小步长+轻平滑)...")
V = np.array([tm @ v.co for v in template_obj.data.vertices])

for it in range(15):
    t_iter = time.time()
    
    # 找最近点
    C = np.zeros_like(V)
    for i in range(n_verts):
        co, idx, dist = kd.find(tuple(V[i]))
        C[i] = co
    
    # 极小步长
    alpha = 0.08
    
    # 向目标移动
    V_new = V + alpha * (C - V)
    
    # 极轻平滑（只做 1 次，系数 0.2）
    for i in range(n_verts):
        nbrs = adjacency[i]
        if len(nbrs) == 0:
            continue
        avg = np.mean([V_new[j] for j in nbrs], axis=0)
        V_new[i] = V_new[i] * 0.8 + avg * 0.2
    
    V = V_new
    
    errs = np.linalg.norm(V - C, axis=1)
    avg_err = np.mean(errs)
    med_err = np.median(errs)
    print(f"  精贴 {it+1:2d}/15 | 误差 {avg_err*1000:.3f}mm | 中位数 {med_err*1000:.3f}mm | {time.time()-t_iter:.1f}s")

# 写回
for i, v in enumerate(template_obj.data.vertices):
    v.co = tm_inv @ Vector(V[i])
template_obj.data.update()

# ============================================================
# 验证
# ============================================================
print("\n" + "=" * 60)
print("最终验证 (1M 采样)...")

verify_step = max(1, scan_n // 1000000)
print(f"采样步长: {verify_step}")

t0 = time.time()
kd_verify = KDTree(scan_n // verify_step + 1)
for i in range(0, scan_n, verify_step):
    co = sm @ scan_obj.data.vertices[i].co
    kd_verify.insert(co, i)
kd_verify.balance()
print(f"验证 KDTree: {time.time()-t0:.1f}s")

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
# 保存
# ============================================================
print("\n" + "=" * 60)
print("保存最终结果...")

blend_out = os.path.join(OUTPUT_DIR, "fitted_result_final.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_out)
print(f"Blend: {blend_out}")

template_obj.select_set(True)
bpy.context.view_layer.objects.active = template_obj

glb_out = os.path.join(OUTPUT_DIR, "MH_Head_fitted_final.glb")
bpy.ops.export_scene.gltf(
    filepath=glb_out,
    use_selection=True,
    export_format='GLB',
    export_apply=True
)
print(f"GLB: {glb_out}")

obj_out = os.path.join(OUTPUT_DIR, "MH_Head_fitted_final.obj")
try:
    bpy.ops.wm.obj_export(
        filepath=obj_out,
        export_selected_objects=True
    )
    print(f"OBJ: {obj_out}")
except:
    print("OBJ 导出失败 (Blender 5.1 API 变化)")

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
with open(os.path.join(OUTPUT_DIR, "quality_report_final.json"), 'w') as f:
    json.dump(report, f, indent=2)

print(f"\n最终质量报告: {os.path.join(OUTPUT_DIR, 'quality_report_final.json')}")
print("\n完成!")