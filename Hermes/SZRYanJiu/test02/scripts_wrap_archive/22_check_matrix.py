import bpy, os, sys, math
from mathutils import Vector, Matrix

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
GLB_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\AI生成高模\02_tripoTpose\raw_model.glb"

print("="*60)
print("检查GLB导入后的matrix_world")
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

print(f"\n对象: {mesh_obj.name}")
print(f"matrix_world:\n{mesh_obj.matrix_world}")

# 检查matrix_world的旋转部分
rot = mesh_obj.matrix_world.to_3x3()
print(f"\n旋转矩阵:\n{rot}")

# 检查欧拉角
euler = mesh_obj.matrix_world.to_euler()
print(f"\n欧拉角: X={math.degrees(euler.x):.1f}° Y={math.degrees(euler.y):.1f}° Z={math.degrees(euler.z):.1f}°")

# 检查顶点坐标（世界坐标）
print("\n前10个顶点（世界坐标）:")
for i in range(min(10, len(mesh_obj.data.vertices))):
    v = mesh_obj.data.vertices[i]
    world_pos = mesh_obj.matrix_world @ v.co
    print(f"  v{i}: local=({v.co.x:.3f}, {v.co.y:.3f}, {v.co.z:.3f}) world=({world_pos.x:.3f}, {world_pos.y:.3f}, {world_pos.z:.3f})")

# 检查bbox（世界坐标）
xs = [(mesh_obj.matrix_world @ v.co).x for v in mesh_obj.data.vertices]
ys = [(mesh_obj.matrix_world @ v.co).y for v in mesh_obj.data.vertices]
zs = [(mesh_obj.matrix_world @ v.co).z for v in mesh_obj.data.vertices]

print(f"\n世界坐标bbox:")
print(f"  X: {min(xs):.3f} to {max(xs):.3f}")
print(f"  Y: {min(ys):.3f} to {max(ys):.3f}")
print(f"  Z: {min(zs):.3f} to {max(zs):.3f}")

print("\nDONE")
