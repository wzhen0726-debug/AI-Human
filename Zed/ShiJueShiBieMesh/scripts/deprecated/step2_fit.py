"""
完整流程：模板贴合扫描
1. 加载 blend 文件
2. 检查对齐状态
3. 精简扫描
4. 非刚性贴合
5. 验证质量
6. 导出结果
"""
import bpy
import numpy as np
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
import time
import os
import json

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output"
BLEND_FILE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"

# ============================================================
# 0. 加载
# ============================================================
print("=" * 60)
print("加载 blend 文件...")
bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)

template_obj = bpy.data.objects.get("MH_Head")
scan_obj = bpy.data.objects.get("Scan_Head")

if not template_obj or not scan_obj:
    print("错误: 找不到 MH_Head 或 Scan_Head!")
    raise SystemExit(1)

print(f"模板: {template_obj.name} ({len(template_obj.data.vertices):,} verts)")
print(f"扫描: {scan_obj.name} ({len(scan_obj.data.vertices):,} verts)")

# ============================================================
# 1. 检查对齐状态
# ============================================================
print("\n" + "=" * 60)
print("检查对齐状态...")

def get_bbox(obj):
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    return {
        'min': (min(xs), min(ys), min(zs)),
        'max': (max(xs), max(ys), max(zs)),
        'center': ((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2),
        'size': (max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    }

t_bbox = get_bbox(template_obj)
s_bbox = get_bbox(scan_obj)

print(f"模板包围盒: min={t_bbox['min']}, max={t_bbox['max']}")
print(f"模板尺寸: {t_bbox['size']}")
print(f"扫描包围盒: min={s_bbox['min']}, max={s_bbox['max']}")
print(f"扫描尺寸: {s_bbox['size']}")

center_offset = [s_bbox['center'][i] - t_bbox['center'][i] for i in range(3)]
print(f"中心偏移: {center_offset}")

size_ratio = [s_bbox['size'][i] / t_bbox['size'][i] if t_bbox['size'][i] > 0 else 1 for i in range(3)]
print(f"尺寸比: {size_ratio}")

# ============================================================
# 2. 精简扫描（降到 ~20万顶点）
# ============================================================
print("\n" + "=" * 60)
print("精简扫描...")

# 复制扫描
scan_copy = scan_obj.copy()
scan_copy.data = scan_obj.data.copy()
scan_copy.name = "Scan_Decimated"
bpy.context.collection.objects.link(scan_copy)
bpy.context.view_layer.objects.active = scan_copy

# Decimate modifier
target_ratio = 200000 / len(scan_obj.data.vertices)
print(f"目标 ratio: {target_ratio:.4f} ({200000:,} verts)")

dec_mod = scan_copy.modifiers.new(name="Decimate", type='DECIMATE')
dec_mod.ratio = target_ratio
dec_mod.use_collapse_triangulate = True

# Apply
bpy.ops.object.modifier_apply(modifier=dec_mod.name)
print(f"精简后: {len(scan_copy.data.vertices):,} verts")

# ============================================================
# 3. 非刚性贴合
# ============================================================
print("\n" + "=" * 60)
print("非刚性贴合...")

# 获取世界矩阵
tm = template_obj.matrix_world
tm_inv = tm.inverted()
sm = scan_copy.matrix_world

# 构建 KDTree（用精简后的扫描）
print("构建 KDTree...")
t0 = time.time()
scan_verts = [sm @ v.co for v in scan_copy.data.vertices]
kd = KDTree(len(scan_verts))
for i, v in enumerate(scan_verts):
    kd.insert(v, i)
kd.balance()
print(f"KDTree 构建完成: {time.time()-t0:.2f}s")

# 构建模板邻接关系
print("构建邻接关系...")
n_verts = len(template_obj.data.vertices)
edges = [(e.vertices[0], e.vertices[1]) for e in template_obj.data.edges]
adjacency = {i: set() for i in range(n_verts)}
for a, b in edges:
    adjacency[a].add(b)
    adjacency[b].add(a)
degree = np.array([len(adjacency[i]) for i in range(n_verts)], dtype=np.float64)

# 获取初始顶点位置（世界空间）
V = np.array([tm @ v.co for v in template_obj.data.vertices])

# 迭代贴合
print("开始迭代贴合...")
max_dist = 0.05  # 最大对应距离（米）
for it in range(20):
    # 找最近点
    C = np.zeros_like(V)
    valid = 0
    for i in range(n_verts):
        co, idx, dist = kd.find(tuple(V[i]))
        C[i] = co
        if dist < max_dist:
            valid += 1
    
    # 移动步长
    alpha = 0.5 if it < 5 else (0.3 if it < 10 else 0.15)
    
    # 向目标移动
    V_new = V + alpha * (C - V)
    
    # 拉普拉斯平滑
    for i in range(n_verts):
        if degree[i] == 0:
            continue
        neighbors = list(adjacency[i])
        if len(neighbors) == 0:
            continue
        avg = np.mean([V_new[j] for j in neighbors], axis=0)
        V_new[i] = V_new[i] * 0.5 + avg * 0.5
    
    V = V_new
    
    # 计算平均误差
    errors = np.linalg.norm(V - C, axis=1)
    avg_error = np.mean(errors[errors < max_dist]) if np.any(errors < max_dist) else 0
    print(f"  迭代 {it+1:2d}/20 | 有效对应 {valid:6d}/{n_verts} | 平均误差 {avg_error*1000:.3f}mm | alpha={alpha}")

# 写回模板
for i, v in enumerate(template_obj.data.vertices):
    v.co = tm_inv @ Vector(V[i])

template_obj.data.update()

# 删除精简扫描
bpy.data.objects.remove(scan_copy, do_unlink=True)

# ============================================================
# 4. 验证质量
# ============================================================
print("\n" + "=" * 60)
print("验证贴合质量...")

# 重新读取贴合后的顶点
V_fitted = np.array([tm @ v.co for v in template_obj.data.vertices])

# 用原始扫描做验证（取采样点）
print("用原始扫描做精度验证...")
# 采样原始扫描的点（每100个取1个）
scan_mesh = scan_obj.data
scan_mat = scan_obj.matrix_world
sample_step = max(1, len(scan_mesh.vertices) // 50000)
sample_verts = [scan_mat @ scan_mesh.vertices[i].co for i in range(0, len(scan_mesh.vertices), sample_step)]

# 构建高精度 KDTree
kd_verify = KDTree(len(sample_verts))
for i, v in enumerate(sample_verts):
    kd_verify.insert(v, i)
kd_verify.balance()

# 计算每个模板顶点到原始扫描的距离
distances = []
for i in range(len(V_fitted)):
    co, idx, dist = kd_verify.find(tuple(V_fitted[i]))
    distances.append(dist)

distances = np.array(distances)
print(f"  平均距离: {np.mean(distances)*1000:.3f} mm")
print(f"  中位数距离: {np.median(distances)*1000:.3f} mm")
print(f"  最大距离: {np.max(distances)*1000:.3f} mm")
print(f"  标准差: {np.std(distances)*1000:.3f} mm")
print(f"  <0.5mm: {np.sum(distances < 0.0005) / len(distances) * 100:.1f}%")
print(f"  <1.0mm: {np.sum(distances < 0.001) / len(distances) * 100:.1f}%")
print(f"  <2.0mm: {np.sum(distances < 0.002) / len(distances) * 100:.1f}%")
print(f"  >5.0mm: {np.sum(distances > 0.005) / len(distances) * 100:.1f}%")

# ============================================================
# 5. 保存 blend 文件
# ============================================================
print("\n" + "=" * 60)
print("保存结果...")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 保存 blend
blend_out = os.path.join(OUTPUT_DIR, "fitted_result.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_out)
print(f"Blend 已保存: {blend_out}")

# 导出贴合后的模板为 GLB
glb_out = os.path.join(OUTPUT_DIR, "MH_Head_fitted.glb")
template_obj.select_set(True)
bpy.context.view_layer.objects.active = template_obj
bpy.ops.export_scene.gltf(
    filepath=glb_out,
    use_selection=True,
    export_format='GLB',
    export_apply=True
)
print(f"GLB 已保存: {glb_out}")

# 导出贴合后的模板为 OBJ
obj_out = os.path.join(OUTPUT_DIR, "MH_Head_fitted.obj")
bpy.ops.export_scene.obj(
    filepath=obj_out,
    use_selection=True,
    use_materials=False
)
print(f"OBJ 已保存: {obj_out}")

# 保存质量报告
report = {
    "template": "MH_Head",
    "template_verts": len(template_obj.data.vertices),
    "template_faces": len(template_obj.data.polygons),
    "scan_verts_original": len(scan_obj.data.vertices),
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

print(f"质量报告已保存: {os.path.join(OUTPUT_DIR, 'quality_report.json')}")

print("\n" + "=" * 60)
print("完成!")
print(f"贴合后模板: {len(template_obj.data.vertices):,} verts, {len(template_obj.data.polygons):,} faces")
print(f"拓扑完全保留，形状贴合扫描")