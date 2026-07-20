"""
贴合 v5 - 智能识别空洞区域，排除口腔/眼窝/鼻孔内部顶点
策略：
1. 用扫描构建"头部表面"——所有外部顶点应该贴合到扫描
2. 口腔/眼窝/鼻孔的"内部"顶点不直接贴合，而是跟随边界变形
3. 识别方法：对每个模板顶点，如果它的最近扫描点在其"反向"方向，就是内部顶点
"""
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
import time, os, json

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_v5"
BLEND_FILE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
print("=" * 60)
print("0. 加载 + 清理 + 导入 OBJ")
bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)
scan_obj = bpy.data.objects.get("Scan_Head")

for obj in list(bpy.data.objects):
    if obj.type == 'MESH' and obj != scan_obj:
        bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.outliner.orphans_purge(do_recursive=True)

bpy.ops.wm.obj_import(filepath=TEMPLATE_PATH)
template_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH' and obj != scan_obj:
        template_obj = obj; break

mesh = template_obj.data
n_verts = len(mesh.vertices)
n_faces = len(mesh.polygons)
quad_c = sum(1 for p in mesh.polygons if len(p.vertices) == 4)
print(f"模板: {n_verts} verts, {n_faces} faces, {quad_c} quads")

# ============================================================
print("\n" + "=" * 60)
print("1. 对齐（中心+缩放）")

tm = template_obj.matrix_world; sm = scan_obj.matrix_world
scan_n = len(scan_obj.data.vertices)

def bbox(obj):
    vs = [obj.matrix_world@v.co for v in obj.data.vertices]
    xs=[v.x for v in vs]; ys=[v.y for v in vs]; zs=[v.z for v in vs]
    return {'center':((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2),
            'size':(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs))}

tb = bbox(template_obj); sb = bbox(scan_obj)
off = [sb['center'][i]-tb['center'][i] for i in range(3)]
template_obj.location.x += off[0]; template_obj.location.y += off[1]; template_obj.location.z += off[2]
bpy.context.view_layer.update()

sr = [sb['size'][i]/tb['size'][i] if tb['size'][i]>1e-6 else 1 for i in range(3)]
us = sum(sr)/3
template_obj.scale = (us,us,us)
bpy.context.view_layer.update()
print(f"偏移=({off[0]:.3f},{off[1]:.3f},{off[2]:.3f}) 缩放={us:.4f}")

tm = template_obj.matrix_world; tm_inv = tm.inverted()
sm = scan_obj.matrix_world; sm_inv = sm.inverted()

# ============================================================
print("\n" + "=" * 60)
print("2. 构建 KDTree")

sample_step = max(1, scan_n // 300000)
kd = KDTree(scan_n // sample_step + 1)
for i in range(0, scan_n, sample_step):
    kd.insert(sm @ scan_obj.data.vertices[i].co, i)
kd.balance()
print(f"KDTree: {scan_n//sample_step+1:,} 点")

# ============================================================
print("\n" + "=" * 60)
print("3. 识别内部顶点（口腔/眼窝/鼻孔）")

# 计算每个模板顶点的法线
bm0 = bmesh.new(); bm0.from_mesh(template_obj.data)
bm0.verts.ensure_lookup_table(); bm0.faces.ensure_lookup_table()
vn = {}
for v in bm0.verts:
    n = Vector((0,0,0))
    for f in v.link_faces: n += f.normal
    if n.length>0: n.normalize()
    vn[v.index] = n

# 对每个模板顶点，计算"法线方向"的最近扫描点 vs "反法线方向"的最近扫描点
# 如果反法线方向的扫描点更近，说明该顶点在空洞内部
interior_mask = np.zeros(n_verts, dtype=bool)
for i, v in enumerate(template_obj.data.vertices):
    wc = tm @ v.co
    n = vn.get(i, Vector((0,0,1)))
    wn = (tm.to_3x3() @ n).normalized()
    
    # 最近扫描点
    co_near, idx, dist_near = kd.find(tuple(wc))
    
    # 法线反方向 2mm 处的最近扫描点
    opposite_pt = wc - wn * 0.005
    co_opp, idx2, dist_opp = kd.find(tuple(opposite_pt))
    
    # 如果反方向的点更近，说明顶点在扫描表面"后面"
    if dist_opp < dist_near * 0.7:
        interior_mask[i] = True

interior_count = np.sum(interior_mask)
surface_count = n_verts - interior_count
print(f"内部顶点: {interior_count} ({interior_count/n_verts*100:.1f}%)")
print(f"表面顶点: {surface_count} ({surface_count/n_verts*100:.1f}%)")

# 保存顶点组
if "CAVITY_INTERIOR" in template_obj.vertex_groups:
    template_obj.vertex_groups.remove(template_obj.vertex_groups["CAVITY_INTERIOR"])
vg = template_obj.vertex_groups.new(name="CAVITY_INTERIOR")
for i in range(n_verts):
    if interior_mask[i]:
        vg.add([i], 1.0, 'REPLACE')

# ============================================================
print("\n" + "=" * 60)
print("4. 构建邻接关系")

edges = [(e.vertices[0], e.vertices[1]) for e in template_obj.data.edges]
adj = {i: [] for i in range(n_verts)}
for a, b in edges:
    adj[a].append(b); adj[b].append(a)

# ============================================================
print("\n" + "=" * 60)
print("5. 非刚性贴合（表面顶点贴合扫描，内部顶点跟随邻居）")

V = np.array([tm @ v.co for v in template_obj.data.vertices])

for it in range(25):
    t0 = time.time()
    
    # 找最近扫描点
    C = np.array([kd.find(tuple(V[i]))[0] for i in range(n_verts)])
    
    alpha = 0.5 if it<5 else (0.3 if it<10 else (0.2 if it<15 else 0.1))
    V_new = V.copy()
    
    # 表面顶点：向扫描移动
    for i in range(n_verts):
        if not interior_mask[i]:
            V_new[i] = V[i] + alpha * (C[i] - V[i])
        # 内部顶点不动（后面平滑会处理）
    
    # Quad-safe 平滑（所有顶点）
    for i in range(n_verts):
        nbrs = adj[i]
        if not nbrs: continue
        avg = np.mean([V_new[j] for j in nbrs], axis=0)
        blend = min(0.5, len(nbrs)/8.0)
        if interior_mask[i]:
            blend = min(0.7, len(nbrs)/6.0)  # 内部顶点更依赖平滑
        V_new[i] = V_new[i]*(1-blend) + avg*blend
    
    V = V_new
    
    surface_c = np.array([V[i] for i in range(n_verts) if not interior_mask[i]])
    surface_t = np.array([C[i] for i in range(n_verts) if not interior_mask[i]])
    err_surface = np.mean(np.linalg.norm(surface_c - surface_t, axis=1))
    
    if it%5==0 or it==24:
        print(f"  [{it+1:2d}/25] surface_err={err_surface*1000:.3f}mm alpha={alpha} {time.time()-t0:.1f}s")

for i, v in enumerate(template_obj.data.vertices):
    v.co = tm_inv @ Vector(V[i])
template_obj.data.update()

# ============================================================
print("\n" + "=" * 60)
print("6. ray_cast 精贴（仅表面顶点）")

tm = template_obj.matrix_world; tm_inv = tm.inverted()
sm = scan_obj.matrix_world; sm_inv = sm.inverted()

for it in range(8):
    t0 = time.time()
    V = np.array([tm @ v.co for v in template_obj.data.vertices])
    hit_c = 0
    
    for i, v in enumerate(template_obj.data.vertices):
        if interior_mask[i]:
            continue  # 跳过内部顶点
        
        wc = tm @ v.co; lc = sm_inv @ wc
        n = vn.get(i, Vector((0,0,1)))
        wn = (tm.to_3x3()@n).normalized()
        ln = (sm_inv.to_3x3()@wn).normalized()
        
        ro = lc - ln*0.015
        hit, loc, hn, fi = scan_obj.ray_cast(ro, ln, distance=0.08)
        if not hit:
            hit, loc, hn, fi = scan_obj.ray_cast(lc+ln*0.015, -ln, distance=0.08)
        if hit:
            V[i] = sm @ loc; hit_c += 1
    
    # 平滑（轻，所有顶点）
    for i in range(n_verts):
        nbrs = adj[i]
        if not nbrs: continue
        avg = np.mean([V[j] for j in nbrs], axis=0)
        blend = 0.25
        V[i] = V[i]*(1-blend) + avg*blend
    
    for i, v in enumerate(template_obj.data.vertices):
        v.co = tm_inv @ Vector(V[i])
    template_obj.data.update()
    print(f"  [{it+1}/8] hit={hit_c}/{surface_count} {time.time()-t0:.1f}s")

bm0.free()

# ============================================================
print("\n" + "=" * 60)
print("7. 验证")

verify_step = max(1, scan_n // 1000000)
kd_v = KDTree(scan_n//verify_step+1)
for i in range(0, scan_n, verify_step):
    kd_v.insert(sm @ scan_obj.data.vertices[i].co, i)
kd_v.balance()

tm = template_obj.matrix_world
Vf = np.array([tm @ v.co for v in template_obj.data.vertices])
distances = np.array([kd_v.find(tuple(Vf[i]))[2] for i in range(len(Vf))])

# 分别统计表面和内部
surface_dists = distances[~interior_mask]
interior_dists = distances[interior_mask]

print(f"  表面顶点: 平均={np.mean(surface_dists)*1000:.2f}mm 中位数={np.median(surface_dists)*1000:.2f}mm")
print(f"  内部顶点: 平均={np.mean(interior_dists)*1000:.2f}mm 中位数={np.median(interior_dists)*1000:.2f}mm")
print(f"  全部顶点: 平均={np.mean(distances)*1000:.3f}mm 中位数={np.median(distances)*1000:.3f}mm")
print(f"  <0.5mm: {np.sum(distances<0.0005)/len(distances)*100:.1f}%")
print(f"  <1.0mm: {np.sum(distances<0.001)/len(distances)*100:.1f}%")
print(f"  <2.0mm: {np.sum(distances<0.002)/len(distances)*100:.1f}%")

# ============================================================
print("\n保存...")
blend_out = os.path.join(OUTPUT_DIR, "MH_Head_01_fitted.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_out)

template_obj.select_set(True)
bpy.context.view_layer.objects.active = template_obj
bpy.ops.export_scene.gltf(filepath=os.path.join(OUTPUT_DIR, "MH_Head_01_fitted.glb"),
                           use_selection=True, export_format='GLB', export_apply=True)
bpy.ops.wm.obj_export(filepath=os.path.join(OUTPUT_DIR, "MH_Head_01_fitted.obj"),
                       export_selected_objects=True)

json.dump({
    "verts": n_verts, "faces": n_faces,
    "interior_verts": int(interior_count),
    "surface_mean_mm": float(np.mean(surface_dists)*1000),
    "surface_median_mm": float(np.median(surface_dists)*1000),
    "interior_mean_mm": float(np.mean(interior_dists)*1000),
    "all_mean_mm": float(np.mean(distances)*1000),
    "all_median_mm": float(np.median(distances)*1000),
    "pct_0_5": float(np.sum(distances<0.0005)/len(distances)*100),
    "pct_1_0": float(np.sum(distances<0.001)/len(distances)*100),
}, open(os.path.join(OUTPUT_DIR, "quality.json"),'w'), indent=2)

print(f"output_v5/ 完成! 内部顶点={interior_count} 保存在 CAVITY_INTERIOR 顶点组")