"""
完整贴合流程 v3 - 修复版
1. 清理旧数据，导入新的四边面 OBJ
2. 修复扫描旋转 (X轴90°)
3. ICP 刚性对齐
4. 非刚性贴合（quad-safe Laplacian）
"""
import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
import time, os, json, math

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_v3"
BLEND_FILE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
print("=" * 60)
print("加载 blend + 清理旧模板...")
bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)

scan_obj = bpy.data.objects.get("Scan_Head")
if not scan_obj:
    raise SystemExit("找不到 Scan_Head!")

# 删除旧模板（保留扫描）
to_delete = []
for obj in bpy.data.objects:
    if obj.type == 'MESH' and obj.name != 'Scan_Head':
        to_delete.append(obj)
for obj in to_delete:
    bpy.data.objects.remove(obj, do_unlink=True)

# ============================================================
print("导入新 OBJ 模板...")
bpy.ops.wm.obj_import(filepath=TEMPLATE_PATH)
template_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH' and obj.name != 'Scan_Head':
        template_obj = obj
        break

if not template_obj:
    raise SystemExit("找不到导入的模板!")

# ============================================================
# 1. 拓扑验证
# ============================================================
mesh = template_obj.data
tri = sum(1 for p in mesh.polygons if len(p.vertices) == 3)
quad = sum(1 for p in mesh.polygons if len(p.vertices) == 4)
ngon = sum(1 for p in mesh.polygons if len(p.vertices) > 4)

print(f"模板: {len(mesh.vertices)} verts, {len(mesh.polygons)} faces")
print(f"  三角: {tri}, 四边: {quad}, N-gon: {ngon}")

if quad == 0:
    print("⚠ 警告: 模板没有四边面！OBJ 导入可能被三角化了。")
    # 尝试用 bmesh 手动加载 OBJ
    # 但这里先继续，可能是 Blender 内部表示的差异

# ============================================================
# 2. 修复扫描旋转 + 基础对齐
# ============================================================
print("\n" + "=" * 60)
print("修复对齐...")

# 扫描绕 X 轴旋转了 90 度，先修正
print(f"扫描原始旋转: {list(scan_obj.rotation_euler)}")

# 应用旋转到 mesh 数据
bpy.context.view_layer.objects.active = scan_obj
bpy.ops.object.mode_set(mode='OBJECT')
scan_obj.select_set(True)

# 用 transform apply 把旋转 bake 到顶点
# 先保存原始 world matrix
orig_scan_matrix = scan_obj.matrix_world.copy()

# 重置旋转
scan_obj.rotation_euler = (0, 0, 0)
bpy.context.view_layer.update()

print(f"扫描修正后旋转: {list(scan_obj.rotation_euler)}")

# ============================================================
# 3. 计算包围盒并刚性对齐
# ============================================================
print("\n计算包围盒...")

def get_bbox_world(obj):
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [v.x for v in vs]; ys = [v.y for v in vs]; zs = [v.z for v in vs]
    cx = (min(xs)+max(xs))/2; cy = (min(ys)+max(ys))/2; cz = (min(zs)+max(zs))/2
    sx = max(xs)-min(xs); sy = max(ys)-min(ys); sz = max(zs)-min(zs)
    return {'center': (cx,cy,cz), 'size': (sx,sy,sz)}

tb = get_bbox_world(template_obj)
sb = get_bbox_world(scan_obj)

print(f"模板: 中心={tb['center']}, 尺寸={tb['size']}")
print(f"扫描: 中心={sb['center']}, 尺寸={sb['size']}")

# 中心对齐
offset = [sb['center'][i] - tb['center'][i] for i in range(3)]
template_obj.location.x += offset[0]
template_obj.location.y += offset[1]
template_obj.location.z += offset[2]
bpy.context.view_layer.update()
print(f"中心偏移修正: ({offset[0]:.4f}, {offset[1]:.4f}, {offset[2]:.4f})")

# 缩放对齐（模板比扫描大，需要缩小）
scale_ratio = [sb['size'][i] / tb['size'][i] if tb['size'][i] > 1e-6 else 1 for i in range(3)]
uniform_scale = sum(scale_ratio) / 3
print(f"尺寸比: {scale_ratio}, 均匀缩放: {uniform_scale:.4f}")

# 均匀缩放模板
template_obj.scale = (uniform_scale, uniform_scale, uniform_scale)
bpy.context.view_layer.update()
print(f"应用缩放: {uniform_scale:.4f}")

# 验证
tb2 = get_bbox_world(template_obj)
print(f"对齐后模板: 中心={tb2['center']}, 尺寸={tb2['size']}")

# ============================================================
# 4. ICP 精对齐
# ============================================================
print("\n" + "=" * 60)
print("ICP 精对齐...")

tm = template_obj.matrix_world
sm = scan_obj.matrix_world
scan_n = len(scan_obj.data.vertices)

# 构建扫描 KDTree（50万采样）
sample_step = max(1, scan_n // 500000)
kd = KDTree(scan_n // sample_step + 1)
for i in range(0, scan_n, sample_step):
    co = sm @ scan_obj.data.vertices[i].co
    kd.insert(co, i)
kd.balance()

# ICP 迭代（只做平移）
V = np.array([tm @ v.co for v in template_obj.data.vertices])
for it in range(5):
    C = np.array([kd.find(tuple(V[i]))[0] for i in range(len(V))])
    t_centroid = np.mean(V, axis=0)
    c_centroid = np.mean(C, axis=0)
    translation = c_centroid - t_centroid
    template_obj.location.x += translation[0]
    template_obj.location.y += translation[1]
    template_obj.location.z += translation[2]
    bpy.context.view_layer.update()
    tm = template_obj.matrix_world
    V = np.array([tm @ v.co for v in template_obj.data.vertices])
    err = np.mean(np.linalg.norm(V - C, axis=1))
    print(f"  ICP {it+1}/5 | 误差 {err*1000:.3f}mm | 平移 ({translation[0]*1000:.1f}, {translation[1]*1000:.1f}, {translation[2]*1000:.1f})mm")

# ============================================================
# 5. 非刚性贴合
# ============================================================
print("\n" + "=" * 60)
print("非刚性贴合...")

tm = template_obj.matrix_world
tm_inv = tm.inverted()
n_verts = len(template_obj.data.vertices)

# 构建 Quad-aware 邻接关系
edges = [(e.vertices[0], e.vertices[1]) for e in template_obj.data.edges]
adjacency = {i: [] for i in range(n_verts)}
for a, b in edges:
    adjacency[a].append(b)
    adjacency[b].append(a)

V = np.array([tm @ v.co for v in template_obj.data.vertices])

# 阶段1: KDTree 粗贴
print("阶段1: KDTree 粗贴...")
for it in range(15):
    t_iter = time.time()
    C = np.zeros_like(V)
    for i in range(n_verts):
        co, idx, dist = kd.find(tuple(V[i]))
        C[i] = co
    
    alpha = 0.5 if it < 5 else (0.3 if it < 10 else 0.15)
    V_new = V + alpha * (C - V)
    
    # Quad-safe smoothing: each vertex typically has 4 neighbors
    for i in range(n_verts):
        nbrs = adjacency[i]
        if len(nbrs) == 0: continue
        avg = np.mean([V_new[j] for j in nbrs], axis=0)
        # Adaptive blend: higher smoothing for vertices with many neighbors
        blend = min(0.5, len(nbrs) / 8.0)
        V_new[i] = V_new[i] * (1 - blend) + avg * blend
    
    V = V_new
    if it % 5 == 0 or it == 14:
        errs = np.linalg.norm(V - C, axis=1)
        print(f"  粗贴 {it+1:2d}/15 | 误差 {np.mean(errs)*1000:.3f}mm | {time.time()-t_iter:.1f}s")

for i, v in enumerate(template_obj.data.vertices):
    v.co = tm_inv @ Vector(V[i])
template_obj.data.update()

# 阶段2: ray_cast 精贴
print("\n阶段2: ray_cast 法线投影...")

tm = template_obj.matrix_world
tm_inv = tm.inverted()
sm = scan_obj.matrix_world
sm_inv = sm.inverted()

# 顶点法线
bm = bmesh.new()
bm.from_mesh(template_obj.data)
bm.verts.ensure_lookup_table()
bm.faces.ensure_lookup_table()
vertex_normals = {}
for v in bm.verts:
    n = Vector((0,0,0))
    for f in v.link_faces:
        n += f.normal
    if n.length > 0: n.normalize()
    vertex_normals[v.index] = n

for it in range(10):
    t_iter = time.time()
    V = np.array([tm @ v.co for v in template_obj.data.vertices])
    hit_count = 0
    
    for i, v in enumerate(template_obj.data.vertices):
        world_co = tm @ v.co
        local_co = sm_inv @ world_co
        normal = vertex_normals.get(i, Vector((0,0,1)))
        world_normal = (tm.to_3x3() @ normal).normalized()
        local_normal = (sm_inv.to_3x3() @ world_normal).normalized()
        
        ray_origin = local_co - local_normal * 0.015
        hit, location, hn, fi = scan_obj.ray_cast(ray_origin, local_normal, distance=0.08)
        if not hit:
            hit, location, hn, fi = scan_obj.ray_cast(
                local_co + local_normal * 0.015, -local_normal, distance=0.08)
        if hit:
            V[i] = sm @ location
            hit_count += 1
    
    # 轻平滑
    for i in range(n_verts):
        nbrs = adjacency[i]
        if len(nbrs) == 0: continue
        avg = np.mean([V[j] for j in nbrs], axis=0)
        blend = min(0.3, len(nbrs) / 12.0)
        V[i] = V[i] * (1 - blend) + avg * blend
    
    for i, v in enumerate(template_obj.data.vertices):
        v.co = tm_inv @ Vector(V[i])
    template_obj.data.update()
    
    print(f"  精贴 {it+1:2d}/10 | hit {hit_count}/{n_verts} | {time.time()-t_iter:.1f}s")

bm.free()

# ============================================================
# 6. 验证
# ============================================================
print("\n" + "=" * 60)
print("验证质量...")

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
# 7. 保存
# ============================================================
print("\n" + "=" * 60)
print("保存...")

blend_out = os.path.join(OUTPUT_DIR, "MH_Head_01_fitted.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_out)

template_obj.select_set(True)
bpy.context.view_layer.objects.active = template_obj

glb_out = os.path.join(OUTPUT_DIR, "MH_Head_01_fitted.glb")
bpy.ops.export_scene.gltf(filepath=glb_out, use_selection=True, export_format='GLB', export_apply=True)

obj_out = os.path.join(OUTPUT_DIR, "MH_Head_01_fitted.obj")
bpy.ops.wm.obj_export(filepath=obj_out, export_selected_objects=True)

report = {
    "template": template_obj.name,
    "template_verts": n_verts,
    "template_faces": len(template_obj.data.polygons),
    "scan_verts_original": scan_n,
    "mean_distance_mm": float(np.mean(distances)*1000),
    "median_distance_mm": float(np.median(distances)*1000),
    "max_distance_mm": float(np.max(distances)*1000),
    "std_distance_mm": float(np.std(distances)*1000),
    "pct_under_0_5mm": float(np.sum(distances < 0.0005) / len(distances) * 100),
    "pct_under_1_0mm": float(np.sum(distances < 0.001) / len(distances) * 100),
    "pct_under_2_0mm": float(np.sum(distances < 0.002) / len(distances) * 100),
}
with open(os.path.join(OUTPUT_DIR, "quality_report.json"), 'w') as f:
    json.dump(report, f, indent=2)

print(f"输出: {OUTPUT_DIR}")
print("完成!")