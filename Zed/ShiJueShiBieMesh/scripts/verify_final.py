import bpy, numpy as np

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final\tripo_final.blend"
bpy.ops.wm.open_mainfile(filepath=BLEND)

print("="*70)
print("最终验证")

# 层级
print("\n1. 层级结构:")
for obj in bpy.data.objects:
    if obj.type in ['MESH', 'ARMATURE'] and not obj.name.startswith('WGT-'):
        parent = obj.parent.name if obj.parent else "无"
        cols = [c.name for c in obj.users_collection]
        print(f"  {obj.name} [{obj.type}] parent={parent} collections={cols}")

# 模型
print("\n2. 模型状态:")
for obj in bpy.data.objects:
    if obj.type == 'MESH' and not obj.name.startswith('WGT-'):
        verts = np.array([obj.matrix_world @ v.co for v in obj.data.vertices])
        print(f"  {obj.name}: {len(obj.data.vertices):,}v {len(obj.data.polygons):,}f")
        print(f"    BBox: X[{verts[:,0].min():.3f},{verts[:,0].max():.3f}] Y[{verts[:,1].min():.3f},{verts[:,1].max():.3f}] Z[{verts[:,2].min():.3f},{verts[:,2].max():.3f}]")
        print(f"    loc/rot/scale: {list(obj.location)} / {list(obj.rotation_euler)} / {list(obj.scale)}")
        quads = sum(1 for p in obj.data.polygons if len(p.vertices) == 4)
        tris = sum(1 for p in obj.data.polygons if len(p.vertices) == 3)
        print(f"    quads={quads}, tris={tris}")

# 骨骼
print("\n3. 骨骼状态:")
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE':
        print(f"  {obj.name}: {len(obj.data.bones)} bones")
        print(f"    loc/rot/scale: {list(obj.location)} / {list(obj.rotation_euler)} / {list(obj.scale)}")
        # 根骨骼
        for bone in obj.data.bones:
            if bone.name in ['root', 'spine']:
                print(f"    {bone.name}: head={list(bone.head_local)} tail={list(bone.tail_local)}")
                break

# 集合
print("\n4. 集合结构:")
for col in bpy.data.collections:
    objs = [o.name for o in col.objects]
    print(f"  {col.name}: {len(objs)} objects")
