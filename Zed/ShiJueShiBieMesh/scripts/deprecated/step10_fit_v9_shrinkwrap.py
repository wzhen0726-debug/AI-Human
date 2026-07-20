"""
贴合 v9 - 完全用 Blender 内置修改器（Shrinkwrap + Smooth + CorrectiveSmooth）
放弃自定义顶点操作，彻底避免反面和挤压
"""
import bpy, os, json, time

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_v9"
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
tm=template_obj.matrix_world; sm=scan_obj.matrix_world
def bbox(obj):
    vs=[obj.matrix_world@v.co for v in obj.data.vertices]
    xs=[v.x for v in vs];ys=[v.y for v in vs];zs=[v.z for v in vs]
    return {'c':((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2),
            'sz':(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs))}
tb=bbox(template_obj); sb=bbox(scan_obj)
off=[sb['c'][i]-tb['c'][i] for i in range(3)]
template_obj.location.x+=off[0];template_obj.location.y+=off[1];template_obj.location.z+=off[2]
bpy.context.view_layer.update()
sr=[sb['sz'][i]/tb['sz'][i] if tb['sz'][i]>1e-6 else 1 for i in range(3)]
us=sum(sr)/3
template_obj.scale=(us,us,us)
bpy.context.view_layer.update()
print(f"偏移={off[0]:.3f},{off[1]:.3f},{off[2]:.3f} 缩放={us:.4f}")

bpy.context.view_layer.objects.active = template_obj

# ============================================================
print("\nShrinkwrap + Smooth 迭代贴合...")

# --- 轮次1: 粗贴合 (强Shrinkwrap + 强Smooth) ---
print("轮次1: 粗贴合...")
for i in range(5):
    t0=time.time()
    
    # Shrinkwrap - NEAREST_SURFACEPOINT
    sw=template_obj.modifiers.new("SW","SHRINKWRAP")
    sw.target=scan_obj
    sw.wrap_method='NEAREST_SURFACEPOINT'
    sw.wrap_mode='ON_SURFACE'
    sw.offset=0.0
    bpy.ops.object.modifier_apply(modifier="SW")
    
    # Smooth
    smm=template_obj.modifiers.new("SM","SMOOTH")
    smm.iterations=5
    smm.factor=0.6 if i<2 else (0.4 if i<4 else 0.2)
    bpy.ops.object.modifier_apply(modifier="SM")
    
    print(f"  [{i+1}/5] {time.time()-t0:.1f}s")

# --- 轮次2: 精细贴合 (轻Shrinkwrap + 极轻Smooth) ---
print("轮次2: 精细贴合...")
for i in range(3):
    t0=time.time()
    
    # Shrinkwrap - PROJECT模式（沿法线投影）
    sw=template_obj.modifiers.new("SW","SHRINKWRAP")
    sw.target=scan_obj
    sw.wrap_method='PROJECT'
    sw.wrap_mode='ON_SURFACE'
    sw.use_project_x=True; sw.use_project_y=True; sw.use_project_z=True
    sw.use_negative_direction=True; sw.use_positive_direction=True
    sw.offset=0.0
    bpy.ops.object.modifier_apply(modifier="SW")
    
    # CorrectiveSmooth (比普通Smooth更智能)
    csm=template_obj.modifiers.new("CS","CORRECTIVE_SMOOTH")
    csm.iterations=3
    csm.smooth_type='SIMPLE'
    csm.factor=0.3 if i<2 else 0.15
    bpy.ops.object.modifier_apply(modifier="CS")
    
    print(f"  [{i+1}/3] {time.time()-t0:.1f}s")

# --- 轮次3: 最终投影 (极轻平滑) ---
print("轮次3: 最终投影...")
sw=template_obj.modifiers.new("SW","SHRINKWRAP")
sw.target=scan_obj
sw.wrap_method='PROJECT'
sw.wrap_mode='ON_SURFACE'
sw.use_project_x=True; sw.use_project_y=True; sw.use_project_z=True
sw.use_negative_direction=True; sw.use_positive_direction=True
bpy.ops.object.modifier_apply(modifier="SW")

csm=template_obj.modifiers.new("CS","CORRECTIVE_SMOOTH")
csm.iterations=2
csm.smooth_type='SIMPLE'
csm.factor=0.1
bpy.ops.object.modifier_apply(modifier="CS")

# ============================================================
print("\n验证...")
from mathutils import Vector
from mathutils.kdtree import KDTree
import numpy as np

tm=template_obj.matrix_world
sm=scan_obj.matrix_world
scan_n=len(scan_obj.data.vertices)

vs=max(1, scan_n//500000)
kdv=KDTree(scan_n//vs+1)
for i in range(0,scan_n,vs):
    kdv.insert(sm@scan_obj.data.vertices[i].co,i)
kdv.balance()

Vf=np.array([tm@v.co for v in template_obj.data.vertices])
d=np.array([kdv.find(tuple(Vf[i]))[2] for i in range(len(Vf))])

print(f"平均: {np.mean(d)*1000:.3f}mm")
print(f"中位数: {np.median(d)*1000:.3f}mm")
print(f"最大: {np.max(d)*1000:.3f}mm")
print(f"<0.5mm: {np.sum(d<0.0005)/len(d)*100:.1f}%")
print(f"<1.0mm: {np.sum(d<0.001)/len(d)*100:.1f}%")
print(f"<2.0mm: {np.sum(d<0.002)/len(d)*100:.1f}%")

# ============================================================
print("\n保存...")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTPUT_DIR,"MH_Head_01_fitted.blend"))
template_obj.select_set(True)
bpy.context.view_layer.objects.active=template_obj
bpy.ops.export_scene.gltf(filepath=os.path.join(OUTPUT_DIR,"MH_Head_01_fitted.glb"),
                           use_selection=True,export_format='GLB',export_apply=True)
bpy.ops.wm.obj_export(filepath=os.path.join(OUTPUT_DIR,"MH_Head_01_fitted.obj"),
                       export_selected_objects=True)
json.dump({"mean_mm":float(np.mean(d)*1000),"median_mm":float(np.median(d)*1000),
           "max_mm":float(np.max(d)*1000),"pct_0_5":float(np.sum(d<0.0005)/len(d)*100)},
          open(os.path.join(OUTPUT_DIR,"quality.json"),'w'),indent=2)
print("output_v9/ 完成!")