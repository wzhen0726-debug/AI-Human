"""
第1步：检查 Tripo 模型 + 可用插件
"""
import bpy, os

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_tripo"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TRIPO_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\原始Tripo高模\tripo_01.glb"

# 清空
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 导入
print("导入 Tripo 模型...")
bpy.ops.import_scene.gltf(filepath=TRIPO_PATH)

# 找 mesh
tripo = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        tripo = obj
        break

if not tripo:
    print("错误: 找不到 mesh!")
    raise SystemExit(1)

mesh = tripo.data
print(f"\n=== Tripo 模型 ===")
print(f"名称: {tripo.name}")
print(f"顶点: {len(mesh.vertices):,}")
print(f"面: {len(mesh.polygons):,}")
print(f"位置: {list(tripo.location)}")
print(f"旋转: {list(tripo.rotation_euler)}")
print(f"缩放: {list(tripo.scale)}")

# 尺寸
vs = [tripo.matrix_world @ v.co for v in mesh.vertices]
xs = [v.x for v in vs]; ys = [v.y for v in vs]; zs = [v.z for v in vs]
print(f"X: [{min(xs):.3f}, {max(xs):.3f}]")
print(f"Y: [{min(ys):.3f}, {max(ys):.3f}]")
print(f"Z: [{min(zs):.3f}, {max(zs):.3f}]")
print(f"尺寸: {max(xs)-min(xs):.3f} x {max(ys)-min(ys):.3f} x {max(zs)-min(zs):.3f}")

# 材质
print(f"材质: {[m.name for m in mesh.materials] if mesh.materials else '无'}")
print(f"UV: {[uv.name for uv in mesh.uv_layers] if mesh.uv_layers else '无'}")

# 检查可用插件
print("\n=== 可用插件 ===")
for addon_name in ['QuadRemesher', 'quad_remesher', 'Auto-Rig Pro', 'auto_rig_pro', 
                    'Rigify', 'rigify', 'MACHIN3tools', 'RetopoFlow']:
    enabled = addon_name in bpy.context.preferences.addons
    print(f"  {addon_name}: {'✅' if enabled else '❌'}")

# 列出所有启用的 addon
print("\n所有已启用 addon:")
for name in sorted(bpy.context.preferences.addons.keys()):
    if 'rig' in name.lower() or 'quad' in name.lower() or 'remesh' in name.lower() or 'retopo' in name.lower():
        print(f"  {name}")

# 保存初始 blend
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTPUT_DIR, "step1_import.blend"))
print(f"\n已保存: step1_import.blend")