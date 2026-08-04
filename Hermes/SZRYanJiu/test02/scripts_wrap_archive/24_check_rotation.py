import bpy, os, sys, math
from mathutils import Vector

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
GLB_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\AI生成高模\02_tripoTpose\raw_model.glb"

print("="*60)
print("检查旋转后的顶点坐标")
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

bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 打印原始顶点
print("\n原始前10个顶点:")
for i in range(min(10, len(mesh_obj.data.vertices))):
    v = mesh_obj.data.vertices[i]
    print(f"  v{i}: ({v.co.x:.3f}, {v.co.y:.3f}, {v.co.z:.3f})")

# 绕Z轴-90°
print("\n绕Z轴-90°...")
mesh_obj.rotation_euler = (0, 0, math.radians(-90))
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

print("绕Z轴-90°后前10个顶点:")
for i in range(min(10, len(mesh_obj.data.vertices))):
    v = mesh_obj.data.vertices[i]
    print(f"  v{i}: ({v.co.x:.3f}, {v.co.y:.3f}, {v.co.z:.3f})")

# 绕Y轴+90°
print("\n绕Y轴+90°...")
mesh_obj.rotation_euler = (0, math.radians(90), 0)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

print("绕Y轴+90°后前10个顶点:")
for i in range(min(10, len(mesh_obj.data.vertices))):
    v = mesh_obj.data.vertices[i]
    print(f"  v{i}: ({v.co.x:.3f}, {v.co.y:.3f}, {v.co.z:.3f})")

# 检查bbox
xs = [v.co.x for v in mesh_obj.data.vertices]
ys = [v.co.y for v in mesh_obj.data.vertices]
zs = [v.co.z for v in mesh_obj.data.vertices]

print(f"\n最终bbox:")
print(f"  X: {min(xs):.3f} to {max(xs):.3f}")
print(f"  Y: {min(ys):.3f} to {max(ys):.3f}")
print(f"  Z: {min(zs):.3f} to {max(zs):.3f}")

print("\nDONE")
