"""
完整贴合 v4
- 彻底清理旧数据
- 8,280 顶点四边面模板
- 处理头型差异(大小、鼻梁高低)
"""
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
import time, os, json

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_v4"
BLEND_FILE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
print("=" * 60)
print("0. 加载 blend + 彻底清理")
bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)

scan_obj = bpy.data.objects.get("Scan_Head")
if not scan_obj:
    raise SystemExit("找不到 Scan_Head!")

# 删除所有非扫描的 mesh 对象和数据块
mesh_names_to_keep = {scan_obj.data.name}
objs_to_delete = [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj != scan_obj]
for obj in objs_to_delete:
    mesh_name = obj.data.name
    bpy.data.objects.remove(obj, do_unlink=True)
    # 如果这个 mesh 不在保留列表中，删除 mesh data
    if mesh_name not in mesh_names_to_keep and mesh_name in bpy.data.meshes:
        bpy.data.meshes.remove(bpy.data.meshes[mesh_name], do_unlink=True)

# 强制清理孤儿数据
bpy.ops.outliner.orphans_purge(do_recursive=True)

# ============================================================
print("\n导入 OBJ...")
bpy.ops.wm.obj_import(filepath=TEMPLATE_PATH)

# 找到导入的模板
template_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH' and obj != scan_obj:
        template_obj = obj
        break

if not template_obj:
    raise SystemExit("找不到导入的模板!")

mesh = template_obj.data
n_verts = len(mesh.vertices)
n_faces = len(mesh.polygons)
tri_c = sum(1 for p in mesh.polygons if len(p.vertices) == 3)
quad_c = sum(1 for p in mesh.polygons if len(p.vertices) == 4)

print(f"模板: {template_obj.name}")
print(f"  顶点={n_verts}, 面={n_faces}, 三角={tri_c}, 四边={quad_c}")

if quad_c == 0 and tri_c > 0:
    print("  ⚠ OBJ被三角化了！尝试用bpy.ops.import_scene.obj...")
    # Blender 5.1 wm.obj_import 可能强制三角化
    # 尝试旧版导入器
    bpy.data.objects.remove(template_obj, do_unlink=True)
    bpy.ops.import_scene.obj(filepath=TEMPLATE_PATH)
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj != scan_obj:
            template_obj = obj
            break
    mesh = template_obj.data
    n_verts = len(mesh.vertices)
    n_faces = len(mesh.polygons)
    tri_c = sum(1 for p in mesh.polygons if len(p.vertices) == 3)
    quad_c = sum(1 for p in mesh.polygons if len(p.vertices) == 4)
    print(f"  重新导入: 顶点={n_verts}, 面={n_faces}, 三角={tri_c}, 四边={quad_c}")

# ============================================================
print("\n" + "=" * 60)
print("1. 对齐分析")

tm = template_obj.matrix_world
sm = scan_obj.matrix_world
scan_n = len(scan_obj.data.vertices)

def bbox(obj):
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs=[v.x for v in vs]; ys=[v.y for v in vs]; zs=[v.z for v in vs]
    return {
        'min': (min(xs),min(ys),min(zs)),
        'max': (max(xs),max(ys),max(zs)),
        'center': ((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2),
        'size': (max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    }

tb = bbox(template_obj)
sb = bbox(scan_obj)

print(f"模板: center={tb['center']}, size={tb['size']}")
print(f"扫描: center={sb['center']}, size={sb['size']}")
print(f"扫描旋转: {list(scan_obj.rotation_euler)}")
print(f"模板旋转: {list(template_obj.rotation_euler)}")

# 中心对齐
offset = [sb['center'][i] - tb['center'][i] for i in range(3)]
template_obj.location.x += offset[0]
template_obj.location.y += offset[1]
template_obj.location.z += offset[2]
bpy.context.view_layer.update()
print(f"中心偏移修正: ({offset[0]:.4f}, {offset[1]:.4f}, {offset[2]:.4f})")

# 缩放
scale_r = [sb['size'][i]/tb['size'][i] if tb['size'][i]>1e-6 else 1 for i in range(3)]
us = sum(scale_r)/3
template_obj.scale = (us, us, us)
bpy.context.view_layer.update()
print(f"均匀缩放: {us:.4f} (扫描/模板 = {scale_r})")

# ============================================================
print("\n" + "=" * 60)
print("2. 构建 KDTree...")
sample_step = max(1, scan_n // 300000)
kd = KDTree(scan_n // sample_step + 1)
for i in range(0, scan_n, sample_step):
    kd.insert(sm @ scan_obj.data.vertices[i].co, i)
kd.balance()
print(f"KDTree: {scan_n // sample_step + 1:,} 点")

# ============================================================
print("\n" + "=" * 60)
print("3. 非刚性贴合 (25 迭代)")

tm = template_obj.matrix_world
tm_inv = tm.inverted()
n_verts = len(template_obj.data.vertices)
edges = [(e.vertices[0], e.vertices[1]) for e in template_obj.data.edges]
adj = {i: [] for i in range(n_verts)}
for a, b in edges:
    adj[a].append(b); adj[b].append(a)

V = np.array([tm @ v.co for v in template_obj.data.vertices])

for it in range(25):
    t0 = time.time()
    C = np.array([kd.find(tuple(V[i]))[0] for i in range(n_verts)])
    
    alpha = 0.6 if it<5 else (0.4 if it<10 else (0.25 if it<15 else 0.12))
    V_new = V + alpha * (C - V)
    
    # quad-safe 平滑
    for i in range(n_verts):
        nbrs = adj[i]
        if not nbrs: continue
        avg = np.mean([V_new[j] for j in nbrs], axis=0)
        blend = min(0.5, len(nbrs)/8.0)
        V_new[i] = V_new[i]*(1-blend) + avg*blend
    
    V = V_new
    err = np.mean(np.linalg.norm(V-C, axis=1))
    if it%5==0 or it==24:
        print(f"  [{it+1:2d}/25] err={err*1000:.3f}mm alpha={alpha} {time.time()-t0:.1f}s")

for i, v in enumerate(template_obj.data.vertices):
    v.co = tm_inv @ Vector(V[i])
template_obj.data.update()

# ============================================================
print("\n" + "=" * 60)
print("4. ray_cast 精贴...")

tm = template_obj.matrix_world; tm_inv = tm.inverted()
sm = scan_obj.matrix_world; sm_inv = sm.inverted()

bm0 = bmesh.new(); bm0.from_mesh(template_obj.data)
bm0.verts.ensure_lookup_table(); bm0.faces.ensure_lookup_table()
vn = {}
for v in bm0.verts:
    n = Vector((0,0,0))
    for f in v.link_faces: n += f.normal
    if n.length>0: n.normalize()
    vn[v.index] = n

for it in range(8):
    t0 = time.time()
    hit_c = 0; V = np.array([tm @ v.co for v in template_obj.data.vertices])
    
    for i, v in enumerate(template_obj.data.vertices):
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
    
    for i in range(n_verts):
        nbrs = adj[i]
        if not nbrs: continue
        avg = np.mean([V[j] for j in nbrs], axis=0)
        V[i] = V[i]*0.7 + avg*0.3
    
    for i, v in enumerate(template_obj.data.vertices):
        v.co = tm_inv @ Vector(V[i])
    template_obj.data.update()
    print(f"  [{it+1}/8] hit={hit_c}/{n_verts} {time.time()-t0:.1f}s")

bm0.free()

# ============================================================
print("\n" + "=" * 60)
print("5. 验证...")

verify_step = max(1, scan_n // 1000000)
kd_v = KDTree(scan_n // verify_step + 1)
for i in range(0, scan_n, verify_step):
    kd_v.insert(sm @ scan_obj.data.vertices[i].co, i)
kd_v.balance()

tm = template_obj.matrix_world
Vf = np.array([tm @ v.co for v in template_obj.data.vertices])
distances = np.array([kd_v.find(tuple(Vf[i]))[2] for i in range(len(Vf))])

print(f"  平均: {np.mean(distances)*1000:.3f}mm")
print(f"  中位数: {np.median(distances)*1000:.3f}mm")
print(f"  最大: {np.max(distances)*1000:.3f}mm")
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

report = {
    "verts": n_verts, "faces": n_faces, "quads": quad_c,
    "mean_mm": float(np.mean(distances)*1000),
    "median_mm": float(np.median(distances)*1000),
    "max_mm": float(np.max(distances)*1000),
    "pct_0_5": float(np.sum(distances<0.0005)/len(distances)*100),
    "pct_1_0": float(np.sum(distances<0.001)/len(distances)*100),
    "pct_2_0": float(np.sum(distances<0.002)/len(distances)*100),
}
with open(os.path.join(OUTPUT_DIR, "quality.json"), 'w') as f:
    json.dump(report, f, indent=2)

print(f"\noutput_v4/ 完成!")