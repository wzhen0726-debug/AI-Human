"""
诊断：检查模型朝向、骨骼、控制器状态
"""
import bpy, numpy as np
from mathutils import Vector

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_tripo\tripo_final_fixed.blend"
bpy.ops.wm.open_mainfile(filepath=BLEND)

print("="*60)
print("1. 场景层级")
for obj in bpy.data.objects:
    indent = "  " * (len([p for p in [obj] if obj.parent]) if obj.parent else 0)
    parent = obj.parent.name if obj.parent else "-"
    print(f"  {obj.name} [{obj.type}] parent={parent}")

print("\n"+"="*60)
print("2. Mesh 模型信息")
for obj in bpy.data.objects:
    if obj.type=='MESH':
        mesh = obj.data
        vs = [obj.matrix_world @ v.co for v in mesh.vertices]
        xs=[v.x for v in vs]; ys=[v.y for v in vs]; zs=[v.z for v in vs]
        print(f"  {obj.name}: {len(mesh.vertices)}v {len(mesh.polygons)}f")
        print(f"    location: {list(obj.location)}")
        print(f"    rotation: {list(obj.rotation_euler)}")
        print(f"    scale: {list(obj.scale)}")
        print(f"    bbox: X[{min(xs):.2f},{max(xs):.2f}] Y[{min(ys):.2f},{max(ys):.2f}] Z[{min(zs):.2f},{max(zs):.2f}]")
        # 检查面朝向（采样几个面）
        f_normals = [p.normal for p in mesh.polygons[:5]]
        print(f"    前5个面法线: {[list(n) for n in f_normals]}")
        # 检查修改器
        for mod in obj.modifiers:
            print(f"    modifier: {mod.name} [{mod.type}]")

print("\n"+"="*60)
print("3. Armature 骨骼信息")
for obj in bpy.data.objects:
    if obj.type=='ARMATURE':
        print(f"  {obj.name}: {len(obj.data.bones)} bones")
        print(f"    location: {list(obj.location)}")
        print(f"    rotation: {list(obj.rotation_euler)}")
        print(f"    scale: {list(obj.scale)}")
        # 头部骨骼的朝向
        for bone in obj.data.bones[:5]:
            print(f"    bone[{bone.name}]: head={list(bone.head_local)} tail={list(bone.tail_local)}")
        # 检查是否是 Rigify 生成的控制绑定
        if 'RIG' in obj.name.upper():
            print(f"    这是Rigify控制绑定")
            # 检查控制器大小
            for bone in obj.pose.bones[:5]:
                print(f"    pose[{bone.name}]: loc={list(bone.location)} rot={list(bone.rotation_euler)} scale={list(bone.scale)}")

print("\n"+"="*60)
print("4. 模型是否T-Pose？")
# 检查大致的手臂位置
for obj in bpy.data.objects:
    if obj.type=='MESH':
        vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
        # 找到 Y 轴最高的点（头顶）
        top_y = max(v.y for v in vs)
        # 找到 Y 轴中间的左右极值（手臂位置）
        mid_vs = [v for v in vs if v.y > 0.2 and v.y < 0.6]
        if mid_vs:
            left_x = min(v.x for v in mid_vs)
            right_x = max(v.x for v in mid_vs)
            print(f"  头顶Y: {top_y:.2f}")
            print(f"  中部X范围: {left_x:.2f} ~ {right_x:.2f}")
            print(f"  手臂展开宽度: {right_x - left_x:.2f}m")