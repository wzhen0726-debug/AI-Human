"""最小测试: reverse_faces vs normal_flip 在 bmesh 中的持久性.
创建一个简单面, 翻转它, 保存, 重新加载, 检查法线是否保持.
"""
import bpy, bmesh, os
from mathutils import Vector

# 创建新场景
bpy.ops.wm.read_factory_settings(use_empty=True)
mesh = bpy.data.meshes.new("test")
obj = bpy.data.objects.new("test", mesh)
bpy.context.collection.objects.link(obj)

# 创建一个简单quad面
bm = bmesh.new()
v1 = bm.verts.new((0, 0, 0))
v2 = bm.verts.new((1, 0, 0))
v3 = bm.verts.new((1, 0, 1))
v4 = bm.verts.new((0, 0, 1))
f = bm.faces.new((v1, v2, v3, v4))
bm.normal_update()
print(f"创建时: normal={f.normal}")  # 应该朝+Y或-Y

# 方法1: normal_flip
f.normal_flip()
bm.normal_update()
print(f"normal_flip后: normal={f.normal}")

bm.to_mesh(mesh)
bm.free()

# 保存
path1 = os.path.join(os.environ['TEMP'], 'test_flip.blend')
bpy.ops.wm.save_as_mainfile(filepath=path1)
print(f"保存: {path1}")

# 重新加载
bpy.ops.wm.open_mainfile(filepath=path1)
obj2 = bpy.data.objects["test"]
f2 = obj2.data.polygons[0]
print(f"重新加载后: normal={f2.normal}")

# 方法2: reverse_faces
bpy.ops.wm.read_factory_settings(use_empty=True)
mesh2 = bpy.data.meshes.new("test2")
obj3 = bpy.data.objects.new("test2", mesh2)
bpy.context.collection.objects.link(obj3)

bm2 = bmesh.new()
v1 = bm2.verts.new((0, 0, 0))
v2 = bm2.verts.new((1, 0, 0))
v3 = bm2.verts.new((1, 0, 1))
v4 = bm2.verts.new((0, 0, 1))
f = bm2.faces.new((v1, v2, v3, v4))
bm2.normal_update()
print(f"\n创建时: normal={f.normal}")

bm2.ops.reverse_faces(bm2, faces=[f])
bm2.normal_update()
print(f"reverse_faces后: normal={f.normal}")

bm2.to_mesh(mesh2)
bm2.free()

path2 = os.path.join(os.environ['TEMP'], 'test_reverse.blend')
bpy.ops.wm.save_as_mainfile(filepath=path2)
print(f"保存: {path2}")

bpy.ops.wm.open_mainfile(filepath=path2)
obj4 = bpy.data.objects["test2"]
f3 = obj4.data.polygons[0]
print(f"重新加载后: normal={f3.normal}")

print("\n=== 测试完成 ===")
