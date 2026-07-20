"""
Lattice v2: 受控各向异性缩放 + Shrinkwrap 精贴合
不拖拽晶格点到扫描表面，只做整体比例匹配
"""
import bpy, os, numpy as np, time
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
import math

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final"
BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def bbox_world(obj):
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs=[v.x for v in vs]; ys=[v.y for v in vs]; zs=[v.z for v in vs]
    return dict(min=(min(xs),min(ys),min(zs)), max=(max(xs),max(ys),max(zs)),
                center=((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2),
                size=(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)))

# ============================================================
print("1. 加载")
bpy.ops.wm.open_mainfile(filepath=BLEND)
scan_obj = bpy.data.objects.get("Scan_Head")
for obj in list(bpy.data.objects):
    if obj.type=='MESH' and obj!=scan_obj:
        bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.wm.obj_import(filepath=TEMPLATE)
template_obj = None
for obj in bpy.data.objects:
    if obj.type=='MESH' and obj!=scan_obj: template_obj=obj; break

print(f"  模板: {len(template_obj.data.vertices)}v 扫描: {len(scan_obj.data.vertices):,}v")

# ============================================================
print("\n2. 对齐中心")
tb = bbox_world(template_obj); sb = bbox_world(scan_obj)
off = [sb['center'][i]-tb['center'][i] for i in range(3)]
template_obj.location.x += off[0]; template_obj.location.y += off[1]; template_obj.location.z += off[2]
bpy.context.view_layer.update()
print(f"  中心偏移: ({off[0]:.3f},{off[1]:.3f},{off[2]:.3f})")

# ============================================================
print("\n3. Lattice 各向异性缩放")
tb = bbox_world(template_obj); sb = bbox_world(scan_obj)
print(f"  模板尺寸: ({tb['size'][0]:.3f},{tb['size'][1]:.3f},{tb['size'][2]:.3f})")
print(f"  扫描尺寸: ({sb['size'][0]:.3f},{sb['size'][1]:.3f},{sb['size'][2]:.3f})")

# 创建晶格
bpy.ops.object.add(type='LATTICE')
lattice = bpy.context.active_object
lattice.name = "FitLattice"
lattice.data.points_u = 5; lattice.data.points_v = 5; lattice.data.points_w = 5
lattice.data.interpolation_type_u = 'KEY_BSPLINE'
lattice.data.interpolation_type_v = 'KEY_BSPLINE'
lattice.data.interpolation_type_w = 'KEY_BSPLINE'

# 放晶格到模板位置
pad = 0.02
lattice.location = Vector(tb['center'])
lattice.scale = Vector((tb['size'][0]/2+pad, tb['size'][1]/2+pad, tb['size'][2]/2+pad))
bpy.context.view_layer.update()

# 各向异性缩放：让晶格匹配扫描比例
scale_ratios = [sb['size'][i] / tb['size'][i] if tb['size'][i] > 1e-6 else 1.0 for i in range(3)]
print(f"  轴缩放比: X={scale_ratios[0]:.3f} Y={scale_ratios[1]:.3f} Z={scale_ratios[2]:.3f}")

# 给模板加 Lattice 修改器
lm = template_obj.modifiers.new("Lattice", 'LATTICE')
lm.object = lattice

# 各向异性缩放晶格点
for point in lattice.data.points:
    # 晶格点在单位空间 [-1, 1]，缩放后匹配模板 bbox
    # 不做任意拖拽——只做各向异性缩放
    point.co_deform.x *= scale_ratios[0]
    point.co_deform.y *= scale_ratios[1]
    point.co_deform.z *= scale_ratios[2]

# 应用 Lattice
bpy.context.view_layer.objects.active = template_obj
bpy.ops.object.modifier_apply(modifier="Lattice")
bpy.data.objects.remove(lattice, do_unlink=True)
print("  晶格变形完成")

# ============================================================
print("\n4. Shrinkwrap 精贴合")
sm = scan_obj.matrix_world

# 轮次1: 粗贴合
for i in range(3):
    sw = template_obj.modifiers.new("SW", 'SHRINKWRAP')
    sw.target = scan_obj
    sw.wrap_method = 'NEAREST_SURFACEPOINT'
    sw.wrap_mode = 'ON_SURFACE'
    sw.offset = 0.0
    bpy.ops.object.modifier_apply(modifier="SW")
    
    csm = template_obj.modifiers.new("CS", 'CORRECTIVE_SMOOTH')
    csm.iterations = 3
    csm.smooth_type = 'SIMPLE'
    csm.factor = 0.3
    bpy.ops.object.modifier_apply(modifier="CS")
    print(f"  粗贴 {i+1}/3")

# 轮次2: 精贴合
for i in range(2):
    sw = template_obj.modifiers.new("SW", 'SHRINKWRAP')
    sw.target = scan_obj
    sw.wrap_method = 'PROJECT'
    sw.wrap_mode = 'ON_SURFACE'
    sw.use_project_x = sw.use_project_y = sw.use_project_z = True
    sw.use_negative_direction = sw.use_positive_direction = True
    sw.offset = 0.0
    bpy.ops.object.modifier_apply(modifier="SW")
    
    csm = template_obj.modifiers.new("CS", 'CORRECTIVE_SMOOTH')
    csm.iterations = 2
    csm.smooth_type = 'SIMPLE'
    csm.factor = 0.1
    bpy.ops.object.modifier_apply(modifier="CS")
    print(f"  精贴 {i+1}/2")

# ============================================================
print("\n5. 验证")
scan_n = len(scan_obj.data.vertices)
vs = max(1, scan_n // 500000)
kdv = KDTree(scan_n // vs + 1)
for i in range(0, scan_n, vs):
    kdv.insert(sm @ scan_obj.data.vertices[i].co, i)
kdv.balance()

tm = template_obj.matrix_world
Vf = np.array([tm @ v.co for v in template_obj.data.vertices])
dists = np.array([kdv.find(tuple(Vf[i]))[2] for i in range(len(Vf))])
print(f"  平均: {np.mean(dists)*1000:.3f}mm 中位数: {np.median(dists)*1000:.3f}mm")
print(f"  <0.5mm: {np.sum(dists<0.0005)/len(dists)*100:.1f}% <1mm: {np.sum(dists<0.001)/len(dists)*100:.1f}% <2mm: {np.sum(dists<0.002)/len(dists)*100:.1f}%")

# ============================================================
print("\n6. 保存")
out = os.path.join(OUTPUT_DIR, "head_lattice_fit.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
template_obj.select_set(True); bpy.context.view_layer.objects.active = template_obj
bpy.ops.export_scene.gltf(filepath=os.path.join(OUTPUT_DIR, "head_lattice_fit.glb"),
                           use_selection=True, export_format='GLB', export_apply=True)
print(f"  输出: {out}")