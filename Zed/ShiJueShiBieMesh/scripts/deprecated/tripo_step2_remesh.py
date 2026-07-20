"""
Tripo 模型 → 合规数字人 完整管线
使用 QuadRemesher + Auto-Rig Pro
"""
import bpy, os, time

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_tripo"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
print("="*60)
print("1. 加载模型")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

TRIPO = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\原始Tripo高模\tripo_01.glb"
bpy.ops.import_scene.gltf(filepath=TRIPO)
tripo = None
for obj in bpy.data.objects:
    if obj.type=='MESH': tripo=obj; break

print(f"原始: {len(tripo.data.vertices):,} verts, {len(tripo.data.polygons):,} faces")

# 应用变换
bpy.context.view_layer.objects.active = tripo
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
print(f"位置: {list(tripo.location)}, 旋转: {list(tripo.rotation_euler)}, 缩放: {list(tripo.scale)}")

# 检查尺寸
vs = [tripo.matrix_world @ v.co for v in tripo.data.vertices]
xs=[v.x for v in vs]; ys=[v.y for v in vs]; zs=[v.z for v in vs]
print(f"尺寸: {max(xs)-min(xs):.3f} x {max(ys)-min(ys):.3f} x {max(zs)-min(zs):.3f} m")

# ============================================================
print("\n"+"="*60)
print("2. QuadRemesher 四边形化")

# 检查 QuadRemesher 是否可用
try:
    # QuadRemesher 注册的操作符
    bpy.ops.object.quadremesher_remesh
    print("QuadRemesher: 可用")
    
    tripo.select_set(True)
    bpy.context.view_layer.objects.active = tripo
    
    # 尝试调用 QuadRemesher
    t0 = time.time()
    try:
        bpy.ops.object.quadremesher_remesh()
        print(f"QuadRemesher 完成: {time.time()-t0:.1f}s")
    except Exception as e:
        print(f"QuadRemesher 调用失败: {e}")
        print("尝试查找正确的操作符名称...")
        # 列出所有 quadremesher 相关的操作符
        for name in dir(bpy.ops.object):
            if 'quad' in name.lower() or 'remesh' in name.lower():
                print(f"  找到: bpy.ops.object.{name}")
    
except AttributeError:
    print("QuadRemesher: 不可用")
    print("回退到 Blender 内置 QuadriFlow...")

# 保存
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTPUT_DIR,"step2_remesh.blend"))
print("已保存")