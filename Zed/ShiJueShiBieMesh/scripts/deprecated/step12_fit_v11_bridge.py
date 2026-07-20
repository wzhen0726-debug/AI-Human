"""
贴合 v11 - 用 24K MH_Head 做桥接
1. 把 24K MH_Head 贴合扫描（Shrinkwrap）
2. 用 DataTransfer 把形变传递给 8.2K MH_Head_01
3. 拓扑保持 + 精度保证
"""
import bpy, os, json, time, numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_v11"
BLEND_FILE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
print("加载...")
bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)
scan_obj = bpy.data.objects.get("Scan_Head")

# 找 24K MH_Head（已经在 blend 里）
mh_24k = None
for obj in bpy.data.objects:
    if obj.type=='MESH' and obj.name!='Scan_Head':
        mh_24k = obj
        break

if not mh_24k:
    raise SystemExit("找不到 24K MH_Head!")

print(f"24K MH_Head: {len(mh_24k.data.vertices):,} verts")
print(f"Scan: {len(scan_obj.data.vertices):,} verts")

# ============================================================
# 阶段1: 24K MH_Head 贴合扫描
print("\n"+"="*60)
print("阶段1: 24K MH_Head → 扫描")

bpy.context.view_layer.objects.active = mh_24k

# 轻量 Shrinkwrap（24K 顶点足够密，不需要强变形）
for i in range(5):
    t0=time.time()
    sw=mh_24k.modifiers.new("SW","SHRINKWRAP")
    sw.target=scan_obj
    sw.wrap_method='NEAREST_SURFACEPOINT' if i<3 else 'PROJECT'
    sw.wrap_mode='ON_SURFACE'
    if sw.wrap_method=='PROJECT':
        sw.use_project_x=sw.use_project_y=sw.use_project_z=True
        sw.use_negative_direction=sw.use_positive_direction=True
    sw.offset=0.0
    bpy.ops.object.modifier_apply(modifier="SW")
    
    if i<4:
        sm=mh_24k.modifiers.new("SM","CORRECTIVE_SMOOTH")
        sm.iterations=3
        sm.smooth_type='SIMPLE'
        sm.factor=0.3 if i<2 else 0.15
        bpy.ops.object.modifier_apply(modifier="SM")
    
    print(f"  [{i+1}/5] {time.time()-t0:.1f}s")

# 备份 24K 贴合后的 mesh 数据
fitted_24k = mh_24k

# ============================================================
# 阶段2: 导入 8.2K MH_Head_01
print("\n导入 8.2K MH_Head_01...")
bpy.ops.wm.obj_import(filepath=TEMPLATE_PATH)
mh_01 = None
for obj in bpy.data.objects:
    if obj.type=='MESH' and obj!=scan_obj and obj!=mh_24k:
        mh_01=obj; break

print(f"8.2K MH_Head_01: {len(mh_01.data.vertices):,} verts")

# 对齐 8.2K 到 24K 的位置
# 两个都是 MetaHuman 拓扑，位置应该很接近
# 计算包围盒并做刚性对齐
def bbox(obj):
    vs=[obj.matrix_world@v.co for v in obj.data.vertices]
    xs=[v.x for v in vs];ys=[v.y for v in vs];zs=[v.z for v in vs]
    return {'c':((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2),
            'sz':(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs))}

tb=bbox(mh_01); fb=bbox(fitted_24k)
off=[fb['c'][i]-tb['c'][i] for i in range(3)]
mh_01.location.x+=off[0]; mh_01.location.y+=off[1]; mh_01.location.z+=off[2]
bpy.context.view_layer.update()
sr=[fb['sz'][i]/tb['sz'][i] if tb['sz'][i]>1e-6 else 1 for i in range(3)]
us=sum(sr)/3
mh_01.scale=(us,us,us)
bpy.context.view_layer.update()
print(f"对齐: 偏移={off[0]:.3f},{off[1]:.3f},{off[2]:.3f} 缩放={us:.4f}")

# ============================================================
# 阶段3: DataTransfer 传递形变
print("\n"+"="*60)
print("阶段3: DataTransfer 24K → 8.2K")

bpy.context.view_layer.objects.active = mh_01

# Data Transfer modifier: 从 24K 传递顶点位置
dt=mh_01.modifiers.new("DataTransfer","DATA_TRANSFER")
dt.object=fitted_24k
dt.use_vert_data=True
dt.data_types_verts={'VGROUP_WEIGHTS'}  # 先不传顶点位置
# 实际上 DataTransfer 传的是顶点组权重，不是位置
# 我们需要用 Surface Deform 或 Shrinkwrap

# 改用 Surface Deform
mh_01.modifiers.remove(dt)

# 先让 8.2K 用 Shrinkwrap 贴合到 24K（24K 已经是扫描的形状）
sw=mh_01.modifiers.new("SW","SHRINKWRAP")
sw.target=fitted_24k
sw.wrap_method='NEAREST_SURFACEPOINT'
sw.wrap_mode='ON_SURFACE'
sw.offset=0.0
bpy.ops.object.modifier_apply(modifier="SW")

csm=mh_01.modifiers.new("CS","CORRECTIVE_SMOOTH")
csm.iterations=2
csm.smooth_type='SIMPLE'
csm.factor=0.2
bpy.ops.object.modifier_apply(modifier="CS")

# 再一次 Shrinkwrap 到扫描（精调）
sw=mh_01.modifiers.new("SW2","SHRINKWRAP")
sw.target=scan_obj
sw.wrap_method='PROJECT'
sw.wrap_mode='ON_SURFACE'
sw.use_project_x=sw.use_project_y=sw.use_project_z=True
sw.use_negative_direction=sw.use_positive_direction=True
sw.offset=0.0
bpy.ops.object.modifier_apply(modifier="SW2")

csm=mh_01.modifiers.new("CS2","CORRECTIVE_SMOOTH")
csm.iterations=2
csm.smooth_type='SIMPLE'
csm.factor=0.1
bpy.ops.object.modifier_apply(modifier="CS2")

# ============================================================
# 验证
print("\n验证...")
sm=scan_obj.matrix_world
scan_n=len(scan_obj.data.vertices)
vs=max(1,scan_n//500000)
kdv=KDTree(scan_n//vs+1)
for i in range(0,scan_n,vs): kdv.insert(sm@scan_obj.data.vertices[i].co,i)
kdv.balance()

tm=mh_01.matrix_world
Vf=np.array([tm@v.co for v in mh_01.data.vertices])
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
mh_01.select_set(True); bpy.context.view_layer.objects.active=mh_01
bpy.ops.export_scene.gltf(filepath=os.path.join(OUTPUT_DIR,"MH_Head_01_fitted.glb"),
                           use_selection=True,export_format='GLB',export_apply=True)
json.dump({"mean_mm":float(np.mean(d)*1000),"median_mm":float(np.median(d)*1000),
           "pct_0_5":float(np.sum(d<0.0005)/len(d)*100)},
          open(os.path.join(OUTPUT_DIR,"quality.json"),'w'),indent=2)
print("output_v11/ 完成!")