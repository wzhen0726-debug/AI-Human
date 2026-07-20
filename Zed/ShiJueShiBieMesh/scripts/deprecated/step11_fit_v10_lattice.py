"""
贴合 v10 - Lattice 晶格粗变形 + Shrinkwrap 精贴合
用晶格做整体收放，避免局部拉伸
"""
import bpy, os, json, time, numpy as np
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_v10"
BLEND_FILE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
print("加载...")
bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)
scan_obj = bpy.data.objects.get("Scan_Head")
for obj in list(bpy.data.objects):
    if obj.type=='MESH' and obj!=scan_obj: bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.obj_import(filepath=TEMPLATE_PATH)
for obj in bpy.data.objects:
    if obj.type=='MESH' and obj!=scan_obj: template_obj=obj; break

# ============================================================
print("刚性对齐...")
def bbox(obj):
    vs=[obj.matrix_world@v.co for v in obj.data.vertices]
    xs=[v.x for v in vs];ys=[v.y for v in vs];zs=[v.z for v in vs]
    return {'c':((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2),
            'sz':(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)),
            'min':(min(xs),min(ys),min(zs)),'max':(max(xs),max(ys),max(zs))}
tb=bbox(template_obj); sb=bbox(scan_obj)
off=[sb['c'][i]-tb['c'][i] for i in range(3)]
template_obj.location.x+=off[0];template_obj.location.y+=off[1];template_obj.location.z+=off[2]
bpy.context.view_layer.update()
sr=[sb['sz'][i]/tb['sz'][i] if tb['sz'][i]>1e-6 else 1 for i in range(3)]
us=sum(sr)/3
template_obj.scale=(us,us,us)
bpy.context.view_layer.update()
print(f"偏移={off[0]:.3f},{off[1]:.3f},{off[2]:.3f} 缩放={us:.4f}")

tm=template_obj.matrix_world; sm=scan_obj.matrix_world
scan_n=len(scan_obj.data.vertices)

# ============================================================
# 阶段1: 构建扫描 KDTree
print("构建扫描 KDTree...")
sp=100000; ss=max(1,scan_n//sp)
kd=KDTree(scan_n//ss+1)
for i in range(0,scan_n,ss): kd.insert(sm@scan_obj.data.vertices[i].co,i)
kd.balance()

# ============================================================
# 阶段2: Lattice 晶格粗变形
print("\n"+"="*60)
print("Lattice 晶格变形...")

# 计算模板包围盒（世界空间）
tb=bbox(template_obj)
padding=0.02  # 2cm 边距

# 创建晶格
bpy.ops.object.add(type='LATTICE')
lattice_obj=bpy.context.active_object
lattice_obj.name="DeformLattice"
lattice_obj.data.name="DeformLatticeData"

# 设置晶格分辨率
lattice_obj.data.points_u=7
lattice_obj.data.points_v=7
lattice_obj.data.points_w=7
lattice_obj.data.interpolation_type_u='KEY_BSPLINE'
lattice_obj.data.interpolation_type_v='KEY_BSPLINE'
lattice_obj.data.interpolation_type_w='KEY_BSPLINE'

# 放置晶格到模板包围盒
lattice_obj.location=Vector(tb['c'])
lattice_obj.scale=Vector((tb['sz'][0]/2+padding, tb['sz'][1]/2+padding, tb['sz'][2]/2+padding))
bpy.context.view_layer.update()

# 给模板加 Lattice 修改器
lm=template_obj.modifiers.new("Lattice","LATTICE")
lm.object=lattice_obj

# 采样晶格点并变形到扫描
print("变形晶格点...")
total_pts=lattice_obj.data.points_u*lattice_obj.data.points_v*lattice_obj.data.points_w
for iter_count in range(15):
    moved=0
    for point in lattice_obj.data.points:
        # 晶格点世界坐标
        wp=lattice_obj.matrix_world@point.co_deform
        # 最近扫描点
        co,idx,dist=kd.find(tuple(wp))
        if dist<0.08:  # 8cm内
            # 向扫描移动
            direction=Vector(co)-wp
            if direction.length>0.0001:
                alpha=0.3 if iter_count<5 else (0.15 if iter_count<10 else 0.05)
                point.co_deform=point.co_deform+(lattice_obj.matrix_world.inverted()@direction)*alpha
                moved+=1
    
    if iter_count%3==0:
        print(f"  [{iter_count+1}/15] moved={moved}/{total_pts}")

# 应用 Lattice 修改器
bpy.context.view_layer.objects.active=template_obj
bpy.ops.object.modifier_apply(modifier="Lattice")
bpy.data.objects.remove(lattice_obj, do_unlink=True)

# ============================================================
# 阶段3: Shrinkwrap 精贴合
print("\n"+"="*60)
print("Shrinkwrap 精贴合...")

# 轻量 shrinkwrap（晶格已经做了大部分工作）
for i in range(4):
    t0=time.time()
    sw=template_obj.modifiers.new("SW","SHRINKWRAP")
    sw.target=scan_obj
    sw.wrap_method='NEAREST_SURFACEPOINT' if i<2 else 'PROJECT'
    sw.wrap_mode='ON_SURFACE'
    if sw.wrap_method=='PROJECT':
        sw.use_project_x=sw.use_project_y=sw.use_project_z=True
        sw.use_negative_direction=sw.use_positive_direction=True
    sw.offset=0.0
    bpy.ops.object.modifier_apply(modifier="SW")
    
    csm=template_obj.modifiers.new("CS","CORRECTIVE_SMOOTH")
    csm.iterations=3 if i<2 else 2
    csm.smooth_type='SIMPLE'
    csm.factor=0.4 if i<2 else (0.2 if i<3 else 0.1)
    bpy.ops.object.modifier_apply(modifier="CS")
    print(f"  [{i+1}/4] {time.time()-t0:.1f}s")

# ============================================================
# 验证
print("\n验证...")
tm=template_obj.matrix_world
vs=max(1,scan_n//500000)
kdv=KDTree(scan_n//vs+1)
for i in range(0,scan_n,vs): kdv.insert(sm@scan_obj.data.vertices[i].co,i)
kdv.balance()

Vf=np.array([tm@v.co for v in template_obj.data.vertices])
d=np.array([kdv.find(tuple(Vf[i]))[2] for i in range(len(Vf))])

print(f"平均: {np.mean(d)*1000:.3f}mm")
print(f"中位数: {np.median(d)*1000:.3f}mm")
print(f"最大: {np.max(d)*1000:.3f}mm")
print(f"<0.5mm: {np.sum(d<0.0005)/len(d)*100:.1f}%")
print(f"<1.0mm: {np.sum(d<0.001)/len(d)*100:.1f}%")
print(f"<2.0mm: {np.sum(d<0.002)/len(d)*100:.1f}%")

# 保存
print("\n保存...")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTPUT_DIR,"MH_Head_01_fitted.blend"))
template_obj.select_set(True); bpy.context.view_layer.objects.active=template_obj
bpy.ops.export_scene.gltf(filepath=os.path.join(OUTPUT_DIR,"MH_Head_01_fitted.glb"),
                           use_selection=True,export_format='GLB',export_apply=True)
json.dump({"mean_mm":float(np.mean(d)*1000),"median_mm":float(np.median(d)*1000),
           "max_mm":float(np.max(d)*1000),"pct_0_5":float(np.sum(d<0.0005)/len(d)*100)},
          open(os.path.join(OUTPUT_DIR,"quality.json"),'w'),indent=2)
print("output_v10/ 完成!")