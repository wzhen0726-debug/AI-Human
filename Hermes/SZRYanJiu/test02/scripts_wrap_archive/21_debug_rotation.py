import bpy, os, sys, math
from mathutils import Vector, Matrix
import bmesh

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
GLB_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\AI生成高模\02_tripoTpose\raw_model.glb"
OUT_BLEND = os.path.join(ROOT, "output", "tripo_debug.blend")

print("="*60)
print("调试Tripo旋转")
print("="*60)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

bpy.ops.import_scene.gltf(filepath=GLB_PATH)

mesh_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        mesh_obj = obj
        break

mesh_obj.name = "Tripo_HighPoly"
bpy.context.view_layer.objects.active = mesh_obj
mesh_obj.select_set(True)

# 先应用所有变换（包括GLB导入的rotation）
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

def get_bbox(obj):
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    return {
        'min': Vector((min(xs), min(ys), min(zs))),
        'max': Vector((max(xs), max(ys), max(zs))),
        'size': Vector((max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))),
        'center': Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    }

bbox = get_bbox(mesh_obj)
print(f"原始: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")
print(f"原始范围: X[{bbox['min'].x:.3f}, {bbox['max'].x:.3f}] Y[{bbox['min'].y:.3f}, {bbox['max'].y:.3f}] Z[{bbox['min'].z:.3f}, {bbox['max'].z:.3f}]")

# 打印前10个顶点坐标
print("\n前10个顶点坐标:")
for i in range(min(10, len(mesh_obj.data.vertices))):
    v = mesh_obj.data.vertices[i]
    print(f"  v{i}: ({v.co.x:.3f}, {v.co.y:.3f}, {v.co.z:.3f})")

# ============================================================
# 方法：使用Matrix旋转（而非bmesh手动修改）
# ============================================================
print("\n" + "="*60)
print("使用Matrix旋转")
print("="*60)

# 创建旋转矩阵：绕Z轴-90°
rot_z = Matrix.Rotation(math.radians(-90), 4, 'Z')

# 应用旋转到对象（不是顶点）
mesh_obj.rotation_euler = (0, 0, math.radians(-90))
bpy.context.view_layer.update()

# 应用旋转
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bbox = get_bbox(mesh_obj)
print(f"绕Z轴-90°后: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")

# 打印前10个顶点坐标
print("\n旋转后前10个顶点坐标:")
for i in range(min(10, len(mesh_obj.data.vertices))):
    v = mesh_obj.data.vertices[i]
    print(f"  v{i}: ({v.co.x:.3f}, {v.co.y:.3f}, {v.co.z:.3f})")

# 保存调试文件
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"\n保存: {OUT_BLEND}")

print("\nDONE")
