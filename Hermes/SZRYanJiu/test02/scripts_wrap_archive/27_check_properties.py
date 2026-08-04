import bpy, os, sys, math

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
GLB_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\AI生成高模\02_tripoTpose\raw_model.glb"

print("="*60)
print("检查mesh_obj属性")
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

# 检查parent
print(f"\nparent: {mesh_obj.parent}")

# 检查matrix_basis
print(f"\nmatrix_basis:\n{mesh_obj.matrix_basis}")

# 检查matrix_parent_inverse
print(f"\nmatrix_parent_inverse:\n{mesh_obj.matrix_parent_inverse}")

# 检查matrix_local
print(f"\nmatrix_local:\n{mesh_obj.matrix_local}")

# 检查matrix_world
print(f"\nmatrix_world:\n{mesh_obj.matrix_world}")

# 设置rotation_euler
mesh_obj.rotation_euler = (0, 0, math.radians(-90))
print(f"\n设置rotation_euler后:")
print(f"  rotation_euler: {mesh_obj.rotation_euler}")
print(f"  matrix_basis:\n{mesh_obj.matrix_basis}")
print(f"  matrix_world:\n{mesh_obj.matrix_world}")

print("\nDONE")
