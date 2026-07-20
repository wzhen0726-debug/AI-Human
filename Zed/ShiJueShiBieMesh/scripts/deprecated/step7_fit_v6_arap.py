"""
贴合 v6 - ARAP (尽可能刚性) 形变
核心思路：
1. 每次迭代找最近点 → 但不是逐个顶点移动
2. 而是给每个顶点的邻域计算最佳刚体变换（旋转+平移）
3. 然后用最小二乘求解全局最优顶点位置
4. 这样眼眶环、嘴环、鼻孔环保持圆形结构不变
"""
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
import time, os, json

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_v6"
BLEND_FILE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
print("=" * 60)
print("0. 加载+清理+导入")
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
print(f"模板: {n_verts} verts, {len(mesh.polygons)} faces")

# ============================================================
print("1. 对齐")
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
print("2. 构建KDTree+邻接")
sample_step = max(1, scan_n // 300000)
kd = KDTree(scan_n//sample_step+1)
for i in range(0, scan_n, sample_step):
    kd.insert(sm @ scan_obj.data.vertices[i].co, i)
kd.balance()

edges = [(e.vertices[0], e.vertices[1]) for e in template_obj.data.edges]
adj = {i: [] for i in range(n_verts)}
for a, b in edges: adj[a].append(b); adj[b].append(a)

# ============================================================
print("3. 识别内部顶点")
bm0 = bmesh.new(); bm0.from_mesh(template_obj.data)
bm0.verts.ensure_lookup_table(); bm0.faces.ensure_lookup_table()
vn = {}
for v in bm0.verts:
    n = Vector((0,0,0))
    for f in v.link_faces: n += f.normal
    if n.length>0: n.normalize()
    vn[v.index] = n

interior_mask = np.zeros(n_verts, dtype=bool)
for i, v in enumerate(template_obj.data.vertices):
    wc = tm @ v.co
    n = vn.get(i, Vector((0,0,1)))
    wn = (tm.to_3x3()@n).normalized()
    co_near, idx, dn = kd.find(tuple(wc))
    opposite = wc - wn*0.005
    co_opp, idx2, dopp = kd.find(tuple(opposite))
    if dopp < dn*0.7: interior_mask[i] = True

surface_mask = ~interior_mask
interior_count = np.sum(interior_mask)
print(f"内部: {interior_count}, 表面: {n_verts-interior_count}")

# 顶点组
if "CAVITY_INTERIOR" in template_obj.vertex_groups:
    template_obj.vertex_groups.remove(template_obj.vertex_groups["CAVITY_INTERIOR"])
vg = template_obj.vertex_groups.new(name="CAVITY_INTERIOR")
for i in range(n_verts):
    if interior_mask[i]: vg.add([i],1.0,'REPLACE')

# ============================================================
print("4. ARAP形变")

# 4a. 从模板构建每顶点的邻域（一阶邻居的坐标偏移）
# rest_edges[i] = [vj - vi for each neighbor j]
template_coords = np.array([tm @ v.co for v in template_obj.data.vertices])
rest_edges = []
for i in range(n_verts):
    neighbors = adj[i]
    if len(neighbors) < 2:
        rest_edges.append([])
    else:
        rest_edges.append([template_coords[j] - template_coords[i] for j in neighbors])

V = template_coords.copy()

# ARAP 迭代
for outer_it in range(3):  # 3轮ARAP
    print(f"\n--- ARAP 轮 {outer_it+1}/3 ---")
    
    for inner_it in range(10):
        t0 = time.time()
        
        # Step 1: 找最近扫描点
        C = np.array([kd.find(tuple(V[i]))[0] for i in range(n_verts)])
        
        # Step 2: 估算每顶点的最优旋转（SVD）
        rotations = np.zeros((n_verts, 3, 3))
        for i in range(n_verts):
            if interior_mask[i] or len(rest_edges[i]) < 2:
                rotations[i] = np.eye(3)
                continue
            
            # P = rest pose edges, Q = deformed edges  
            P = np.array(rest_edges[i]).T  # 3 x k
            Q = np.array([V[j] - V[i] for j in adj[i]]).T  # 3 x k
            
            try:
                U, _, Vt = np.linalg.svd(P @ Q.T)
                R = U @ Vt
                if np.linalg.det(R) < 0:
                    Vt[-1] *= -1
                    R = U @ Vt
                rotations[i] = R
            except:
                rotations[i] = np.eye(3)
        
        # Step 3: 最小二乘求解新位置
        # ARAP能量: sum_i sum_{j∈N(i)} || (V_j' - V_i') - R_i (V_j - V_i) ||^2
        # + lambda * ||V_i' - C_i||^2 (表面顶点向目标靠近)
        
        # 用简单的逐顶点迭代（收敛慢但代码简单）
        # 对每个顶点：新位置 = (sum邻居(旋转后rest位移) + lambda*目标) / (度 + lambda)
        
        V_new = V.copy()
        lambda_fit = 0.3 if outer_it == 0 else (0.5 if outer_it == 1 else 0.8)
        
        for i in range(n_verts):
            neighbors = adj[i]
            if len(neighbors) == 0:
                continue
            
            # 从邻居计算ARAP位置
            arap_pos = np.zeros(3)
            arap_weight = 0
            for idx, j in enumerate(neighbors):
                Rj = rotations[j]
                rest_edge_ji = rest_edges[j][adj[j].index(i)] if i in adj[j] else np.zeros(3)
                # 从vertex j的视角: i的位置 = V[j] + R_j * rest_edge_ji
                est = V[j] + Rj @ rest_edge_ji
                arap_pos += est
                arap_weight += 1
            
            if arap_weight > 0:
                arap_pos /= arap_weight
            
            if surface_mask[i]:
                # 表面顶点：ARAP位置 + 向目标移动
                V_new[i] = arap_pos * (1 - lambda_fit) + C[i] * lambda_fit
            else:
                # 内部顶点：纯ARAP
                V_new[i] = arap_pos
        
        V = V_new
        
        # 误差
        if surface_mask.any():
            surferr = np.mean(np.linalg.norm(V[surface_mask] - C[surface_mask], axis=1))
        else:
            surferr = 0
        print(f"  [{inner_it+1:2d}/10] surface_err={surferr*1000:.3f}mm lambda={lambda_fit} {time.time()-t0:.1f}s")

# ============================================================
print("\n5. ray_cast 精贴")
tm = template_obj.matrix_world; tm_inv = tm.inverted()
sm = scan_obj.matrix_world; sm_inv = sm.inverted()

for it in range(5):
    t0 = time.time()
    V = np.array([tm @ v.co for v in template_obj.data.vertices])
    hit_c = 0
    
    for i, v in enumerate(template_obj.data.vertices):
        if interior_mask[i]: continue
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
    
    # 极轻平滑
    for i in range(n_verts):
        nbrs = adj[i]
        if not nbrs: continue
        avg = np.mean([V[j] for j in nbrs], axis=0)
        V[i] = V[i]*0.85 + avg*0.15
    
    for i, v in enumerate(template_obj.data.vertices):
        v.co = tm_inv @ Vector(V[i])
    template_obj.data.update()
    print(f"  [{it+1}/5] hit={hit_c}/{interior_count} {time.time()-t0:.1f}s")

bm0.free()

# ============================================================
print("\n6. 验证")
verify_step = max(1, scan_n//1000000)
kd_v = KDTree(scan_n//verify_step+1)
for i in range(0, scan_n, verify_step):
    kd_v.insert(sm @ scan_obj.data.vertices[i].co, i)
kd_v.balance()

tm = template_obj.matrix_world
Vf = np.array([tm @ v.co for v in template_obj.data.vertices])
dists = np.array([kd_v.find(tuple(Vf[i]))[2] for i in range(len(Vf))])
sd = dists[surface_mask]
id_ = dists[interior_mask]

print(f"表面: 平均={np.mean(sd)*1000:.2f}mm 中位数={np.median(sd)*1000:.2f}mm")
print(f"内部: 平均={np.mean(id_)*1000:.2f}mm 中位数={np.median(id_)*1000:.2f}mm")
print(f"全部: 平均={np.mean(dists)*1000:.3f}mm 中位数={np.median(dists)*1000:.3f}mm")
print(f"<0.5mm:{np.sum(dists<0.0005)/len(dists)*100:.1f}% <1mm:{np.sum(dists<0.001)/len(dists)*100:.1f}% <2mm:{np.sum(dists<0.002)/len(dists)*100:.1f}%")

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
    "verts":n_verts, "interior":int(interior_count),
    "surface_mean_mm":float(np.mean(sd)*1000),
    "surface_median_mm":float(np.median(sd)*1000),
    "all_mean_mm":float(np.mean(dists)*1000),
}, open(os.path.join(OUTPUT_DIR,"quality.json"),'w'), indent=2)
print("output_v6/ 完成!")