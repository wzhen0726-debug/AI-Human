import bpy, os, sys, math
from mathutils import Vector

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
GLB_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\AI生成高模\02_tripoTpose\raw_model.glb"

print("="*60)
print("调试rotation_euler")
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

# 先应用所有变换
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 检查初始rotation_euler
print(f"\n初始rotation_euler: {mesh_obj.rotation_euler}")
print(f"初始matrix_world:\n{mesh_obj.matrix_world}")

# 设置rotation_euler
print("\n设置rotation_euler = (0, 0, -90°)...")
mesh_obj.rotation_euler = (0, 0, math.radians(-90))

# 立即检查
print(f"设置后rotation_euler: {mesh_obj.rotation_euler}")
print(f"设置后matrix_world:\n{mesh_obj.matrix_world}")

# 强制更新
bpy.context.view_layer.update()

# 再次检查
print(f"\n更新后rotation_euler: {mesh_obj.rotation_euler}")
print(f"更新后matrix_world:\n{mesh_obj.matrix_world}")

# 应用旋转
print("\n应用transform_apply...")
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 检查应用后
print(f"应用后rotation_euler: {mesh_obj.rotation_euler}")
print(f"应用后matrix_world:\n{mesh_obj.matrix_world}")

# 打印顶点
print("\n应用后前3个顶点:")
for i in range(min(3, len(mesh_obj.data.vertices))):
    v = mesh_obj.data.vertices[i]
    print(f"  v{i}: ({v.co.x:.3f}, {v.co.y:.3f}, {v.co.z:.3f})")

print("\nDONE")
