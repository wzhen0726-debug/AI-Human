"""
诊断：检查模板的开口边界（口腔、眼窝、鼻孔）
识别哪些顶点在空洞内部，应该排除在拟合之外
"""
import bpy
import bmesh
from mathutils import Vector

BLEND_FILE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_v4\MH_Head_01_fitted.blend"

bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)

# 找到模板和扫描
template_obj = None
scan_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        if 'Scan' in obj.name:
            scan_obj = obj
        else:
            template_obj = obj

if not template_obj or not scan_obj:
    raise SystemExit("找不到模型")

mesh = template_obj.data
print(f"模板: {len(mesh.vertices)} verts, {len(mesh.polygons)} faces")

# ============================================================
# 1. 使用 BMesh 分析边界
# ============================================================
bm = bmesh.new()
bm.from_mesh(mesh)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()

# 找所有边界边（只属于一个面的边 = 开口边缘）
boundary_edges = [e for e in bm.edges if e.is_boundary]
boundary_verts = set()
for e in boundary_edges:
    boundary_verts.add(e.verts[0].index)
    boundary_verts.add(e.verts[1].index)

print(f"\n边界边: {len(boundary_edges)}")
print(f"边界顶点: {len(boundary_verts)}")

# 找边界顶点组（连续的边界环）
visited = set()
boundary_loops = []

for start_vi in boundary_verts:
    if start_vi in visited:
        continue
    loop = []
    stack = [start_vi]
    while stack:
        vi = stack.pop()
        if vi in visited:
            continue
        visited.add(vi)
        loop.append(vi)
        v = bm.verts[vi]
        for e in v.link_edges:
            if e.is_boundary:
                other = e.other_vert(v).index
                if other not in visited:
                    stack.append(other)
    if len(loop) > 3:
        boundary_loops.append(loop)

print(f"找到 {len(boundary_loops)} 个边界环:")
for i, loop in enumerate(boundary_loops):
    # 计算中心
    centers = [bm.verts[vi].co for vi in loop]
    avg = sum(centers, Vector((0,0,0))) / len(centers)
    print(f"  环{i}: {len(loop)} 顶点, 中心=({avg.x:.4f}, {avg.y:.4f}, {avg.z:.4f})")

# ============================================================
# 2. 识别"内部"顶点——在鼻孔、口腔、眼窝深度方向的顶点
# ============================================================
# 方法：从每个边界环的顶点出发，BFS探索"内部"区域
# "内部" = 只通过非边界边可达、且在一定距离内的顶点

tm = template_obj.matrix_world

# 标记内部顶点
interior_verts = set()

for loop_i, loop in enumerate(boundary_loops):
    centers = [bm.verts[vi].co for vi in loop]
    loop_center = sum(centers, Vector((0,0,0))) / len(centers)
    
    # 从边界环开始 BFS，沿非边界边向内探索
    interior = set()
    queue = list(loop)
    depth_map = {vi: 0 for vi in loop}
    
    while queue:
        vi = queue.pop(0)
        depth = depth_map[vi]
        if depth > 10:  # 最多探索10步
            continue
        v = bm.verts[vi]
        for e in v.link_edges:
            if e.is_boundary:
                continue  # 不穿越边界
            other = e.other_vert(v).index
            if other not in depth_map and other not in loop:
                depth_map[other] = depth + 1
                queue.append(other)
                interior.add(other)
    
    interior_verts.update(interior)
    print(f"  环{loop_i} 内部顶点: {len(interior)}")

print(f"\n总内部顶点: {len(interior_verts)} ({len(interior_verts)/len(mesh.vertices)*100:.1f}%)")

# ============================================================
# 3. 检查这些内部顶点在当前贴合结果中的位置
# ============================================================
print("\n" + "=" * 60)
print("检查内部顶点贴合质量...")

# 获取内部顶点在当前模型中的世界坐标
interior_world = [tm @ template_obj.data.vertices[i].co for i in interior_verts]
surface_verts = set(range(len(mesh.vertices))) - interior_verts
surface_world = [tm @ template_obj.data.vertices[i].co for i in surface_verts]

# 构建扫描 KDTree
from mathutils.kdtree import KDTree
scan_n = len(scan_obj.data.vertices)
sm = scan_obj.matrix_world
sample_step = max(1, scan_n // 100000)
kd = KDTree(scan_n // sample_step + 1)
for i in range(0, scan_n, sample_step):
    kd.insert(sm @ scan_obj.data.vertices[i].co, i)
kd.balance()

# 检查内部顶点到扫描的距离
import numpy as np
interior_dists = [kd.find(tuple(v))[2] for v in interior_world]
surface_dists = [kd.find(tuple(v))[2] for v in surface_world]

print(f"内部顶点到扫描: 平均={np.mean(interior_dists)*1000:.2f}mm, 中位数={np.median(interior_dists)*1000:.2f}mm")
print(f"表面顶点到扫描: 平均={np.mean(surface_dists)*1000:.2f}mm, 中位数={np.median(surface_dists)*1000:.2f}mm")

# ============================================================
# 4. 可视化——创建顶点组标记内部顶点
# ============================================================
vg_name = "INTERIOR_CAVITY"
if vg_name in template_obj.vertex_groups:
    template_obj.vertex_groups.remove(template_obj.vertex_groups[vg_name])
vg = template_obj.vertex_groups.new(name=vg_name)
for vi in interior_verts:
    vg.add([vi], 1.0, 'REPLACE')

vg_name2 = "BOUNDARY_RING"
if vg_name2 in template_obj.vertex_groups:
    template_obj.vertex_groups.remove(template_obj.vertex_groups[vg_name2])
vg2 = template_obj.vertex_groups.new(name=vg_name2)
for loop in boundary_loops:
    for vi in loop:
        vg2.add([vi], 1.0, 'REPLACE')

bm.free()

# 保存
bpy.ops.wm.save_mainfile(filepath=BLEND_FILE.replace(".blend", "_diagnosis.blend"))
print(f"\n已保存诊断 blend，顶点组: INTERIOR_CAVITY ({len(interior_verts)}顶点) + BOUNDARY_RING")
print("打开后在 Blender 中选择这些顶点组查看")