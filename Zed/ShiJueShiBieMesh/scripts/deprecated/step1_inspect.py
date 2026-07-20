"""
步骤1：导入两个GLB模型，检查基本信息
"""
import bpy
import json
import os

# 清空场景
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 路径
base = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB"
template_path = os.path.join(base, "MetaHuman_head", "MH_Head.glb")
scan_path = os.path.join(base, "Scan_head", "Scan_Head.glb")

# 导入模板
print("=" * 60)
print("导入模板: MH_Head.glb")
bpy.ops.import_scene.gltf(filepath=template_path)
all_objs = bpy.context.selected_objects
template_obj = None
for obj in all_objs:
    if obj.type == 'MESH':
        template_obj = obj
        break

# 导入扫描
print("导入扫描: Scan_Head.glb")
bpy.ops.import_scene.gltf(filepath=scan_path)
all_objs = bpy.context.selected_objects
scan_obj = None
for obj in all_objs:
    if obj.type == 'MESH':
        scan_obj = obj
        break

# 检查模板
print("\n" + "=" * 60)
print("模板 (MH_Head) 信息:")
if template_obj:
    mesh = template_obj.data
    print(f"  名称: {template_obj.name}")
    print(f"  顶点数: {len(mesh.vertices):,}")
    print(f"  面数: {len(mesh.polygons):,}")
    print(f"  位置: {list(template_obj.location)}")
    print(f"  尺寸: {list(template_obj.dimensions)}")
    # 计算包围盒
    verts = [template_obj.matrix_world @ v.co for v in mesh.vertices]
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    print(f"  X范围: [{min(xs):.3f}, {max(xs):.3f}]")
    print(f"  Y范围: [{min(ys):.3f}, {max(ys):.3f}]")
    print(f"  Z范围: [{min(zs):.3f}, {max(zs):.3f}]")
    # 检查材质
    if mesh.materials:
        print(f"  材质: {[m.name for m in mesh.materials]}")
    else:
        print(f"  材质: 无")
    # 检查UV
    if mesh.uv_layers:
        print(f"  UV层: {[uv.name for uv in mesh.uv_layers]}")
    else:
        print(f"  UV层: 无")
    # 检查顶点色
    if mesh.color_attributes:
        print(f"  顶点色: {[c.name for c in mesh.color_attributes]}")
    else:
        print(f"  顶点色: 无")
else:
    print("  未找到模板mesh!")

# 检查扫描
print("\n" + "=" * 60)
print("扫描 (Scan_Head) 信息:")
if scan_obj:
    mesh = scan_obj.data
    print(f"  名称: {scan_obj.name}")
    print(f"  顶点数: {len(mesh.vertices):,}")
    print(f"  面数: {len(mesh.polygons):,}")
    print(f"  位置: {list(scan_obj.location)}")
    print(f"  尺寸: {list(scan_obj.dimensions)}")
    verts = [scan_obj.matrix_world @ v.co for v in mesh.vertices]
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    print(f"  X范围: [{min(xs):.3f}, {max(xs):.3f}]")
    print(f"  Y范围: [{min(ys):.3f}, {max(ys):.3f}]")
    print(f"  Z范围: [{min(zs):.3f}, {max(zs):.3f}]")
    if mesh.materials:
        print(f"  材质: {[m.name for m in mesh.materials]}")
    else:
        print(f"  材质: 无")
    if mesh.uv_layers:
        print(f"  UV层: {[uv.name for uv in mesh.uv_layers]}")
    else:
        print(f"  UV层: 无")
else:
    print("  未找到扫描mesh!")

# 对比
if template_obj and scan_obj:
    print("\n" + "=" * 60)
    print("对比分析:")
    ratio = len(scan_obj.data.vertices) / len(template_obj.data.vertices)
    print(f"  扫描/模板 顶点比: {ratio:.1f}x")
    
    # 中心点对比
    t_verts = [template_obj.matrix_world @ v.co for v in template_obj.data.vertices]
    s_verts = [scan_obj.matrix_world @ v.co for v in scan_obj.data.vertices]
    
    t_center = [
        (min([v.x for v in t_verts]) + max([v.x for v in t_verts])) / 2,
        (min([v.y for v in t_verts]) + max([v.y for v in t_verts])) / 2,
        (min([v.z for v in t_verts]) + max([v.z for v in t_verts])) / 2,
    ]
    s_center = [
        (min([v.x for v in s_verts]) + max([v.x for v in s_verts])) / 2,
        (min([v.y for v in s_verts]) + max([v.y for v in s_verts])) / 2,
        (min([v.z for v in s_verts]) + max([v.z for v in s_verts])) / 2,
    ]
    print(f"  模板中心: [{t_center[0]:.3f}, {t_center[1]:.3f}, {t_center[2]:.3f}]")
    print(f"  扫描中心: [{s_center[0]:.3f}, {s_center[1]:.3f}, {s_center[2]:.3f}]")
    
    offset = [s_center[i] - t_center[i] for i in range(3)]
    print(f"  中心偏移: [{offset[0]:.3f}, {offset[1]:.3f}, {offset[2]:.3f}]")
    
    # 尺寸对比
    t_size = [max([v.x for v in t_verts]) - min([v.x for v in t_verts]),
              max([v.y for v in t_verts]) - min([v.y for v in t_verts]),
              max([v.z for v in t_verts]) - min([v.z for v in t_verts])]
    s_size = [max([v.x for v in s_verts]) - min([v.x for v in s_verts]),
              max([v.y for v in s_verts]) - min([v.y for v in s_verts]),
              max([v.z for v in s_verts]) - min([v.z for v in s_verts])]
    print(f"  模板尺寸: [{t_size[0]:.3f}, {t_size[1]:.3f}, {t_size[2]:.3f}]")
    print(f"  扫描尺寸: [{s_size[0]:.3f}, {s_size[1]:.3f}, {s_size[2]:.3f}]")
    scale_ratio = [s_size[i] / t_size[i] if t_size[i] > 0 else 1 for i in range(3)]
    print(f"  尺寸比: [{scale_ratio[0]:.3f}, {scale_ratio[1]:.3f}, {scale_ratio[2]:.3f}]")

# 列出所有场景中的mesh对象
print("\n" + "=" * 60)
print("场景中所有Mesh对象:")
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        print(f"  {obj.name} ({len(obj.data.vertices)} 顶点, {len(obj.data.polygons)} 面)")

# 列出所有对象及其层级
print("\n" + "=" * 60)
print("场景中所有对象(含层级):")
for obj in bpy.data.objects:
    parent = obj.parent.name if obj.parent else "无"
    children = [c.name for c in obj.children]
    print(f"  {obj.name} [类型:{obj.type}] [父级:{parent}] [子级:{children}]")

print("\n完成!")