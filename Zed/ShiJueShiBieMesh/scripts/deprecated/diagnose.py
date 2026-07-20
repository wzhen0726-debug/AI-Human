"""
诊断：检查两个模型的对齐状态和拓扑结构
"""
import bpy
import random
from mathutils import Vector

BLEND_FILE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.glb"

# 加载 blend
bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)

scan_obj = bpy.data.objects.get("Scan_Head")

# 导入模板
bpy.ops.import_scene.gltf(filepath=TEMPLATE_PATH)
template_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH' and obj.name != 'Scan_Head':
        template_obj = obj
        break

tm = template_obj.matrix_world
sm = scan_obj.matrix_world

print("=" * 60)
print("模板: ", template_obj.name)
print("扫描: ", scan_obj.name)

# ============================================================
# 1. 包围盒对比
# ============================================================
print("\n" + "=" * 60)
print("包围盒对比（世界空间）...")

def bbox(obj):
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [v.x for v in vs]; ys = [v.y for v in vs]; zs = [v.z for v in vs]
    return {
        'min': (min(xs), min(ys), min(zs)),
        'max': (max(xs), max(ys), max(zs)),
        'center': ((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2),
        'size': (max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    }

tb = bbox(template_obj)
sb = bbox(scan_obj)

print(f"模板: 中心=({tb['center'][0]:.4f}, {tb['center'][1]:.4f}, {tb['center'][2]:.4f})")
print(f"      尺寸=({tb['size'][0]:.4f}, {tb['size'][1]:.4f}, {tb['size'][2]:.4f})")
print(f"      min=({tb['min'][0]:.4f}, {tb['min'][1]:.4f}, {tb['min'][2]:.4f})")
print(f"      max=({tb['max'][0]:.4f}, {tb['max'][1]:.4f}, {tb['max'][2]:.4f})")

print(f"\n扫描: 中心=({sb['center'][0]:.4f}, {sb['center'][1]:.4f}, {sb['center'][2]:.4f})")
print(f"      尺寸=({sb['size'][0]:.4f}, {sb['size'][1]:.4f}, {sb['size'][2]:.4f})")
print(f"      min=({sb['min'][0]:.4f}, {sb['min'][1]:.4f}, {sb['min'][2]:.4f})")
print(f"      max=({sb['max'][0]:.4f}, {sb['max'][1]:.4f}, {sb['max'][2]:.4f})")

offset = [sb['center'][i] - tb['center'][i] for i in range(3)]
print(f"\n中心偏移: ({offset[0]:.4f}, {offset[1]:.4f}, {offset[2]:.4f})")

scale = [sb['size'][i] / tb['size'][i] if tb['size'][i] > 1e-6 else 1 for i in range(3)]
print(f"尺寸比(扫描/模板): ({scale[0]:.4f}, {scale[1]:.4f}, {scale[2]:.4f})")

# ============================================================
# 2. 拓扑检查
# ============================================================
print("\n" + "=" * 60)
print("模板拓扑检查...")

mesh = template_obj.data
print(f"顶点: {len(mesh.vertices)}")
print(f"边: {len(mesh.edges)}")
print(f"面: {len(mesh.polygons)}")

# 检查多边形类型
tri_count = 0
quad_count = 0
ngon_count = 0
for p in mesh.polygons:
    if len(p.vertices) == 3:
        tri_count += 1
    elif len(p.vertices) == 4:
        quad_count += 1
    else:
        ngon_count += 1

print(f"三角面: {tri_count}")
print(f"四边面: {quad_count}")
print(f"N-gon: {ngon_count}")

# 检查极点（非4度的顶点）
edge_count = {}
for e in mesh.edges:
    for vi in e.vertices:
        edge_count[vi] = edge_count.get(vi, 0) + 1

val3 = sum(1 for c in edge_count.values() if c == 3)
val4 = sum(1 for c in edge_count.values() if c == 4)
val5 = sum(1 for c in edge_count.values() if c == 5)
val6p = sum(1 for c in edge_count.values() if c > 5)

print(f"\n顶点度数分布:")
print(f"  3度 (N-pole): {val3}")
print(f"  4度 (regular): {val4}")
print(f"  5度 (E-pole): {val5}")
print(f"  6度+: {val6p}")

# ============================================================
# 3. 检查模板的变换矩阵
# ============================================================
print("\n" + "=" * 60)
print("模板变换矩阵:")
print(f"  location: {list(template_obj.location)}")
print(f"  rotation_euler: {list(template_obj.rotation_euler)}")
print(f"  scale: {list(template_obj.scale)}")

print("\n扫描变换矩阵:")
print(f"  location: {list(scan_obj.location)}")
print(f"  rotation_euler: {list(scan_obj.rotation_euler)}")
print(f"  scale: {list(scan_obj.scale)}")

# ============================================================
# 4. 采样几个顶点检查实际位置
# ============================================================
print("\n" + "=" * 60)
print("模板前5个顶点(世界空间):")
for i, v in enumerate(template_obj.data.vertices[:5]):
    wc = template_obj.matrix_world @ v.co
    print(f"  v{i}: local={list(v.co)} -> world={list(wc)}")

print("\n扫描前5个顶点(世界空间):")
rn = len(scan_obj.data.vertices)
sample_indices = [0, rn//4, rn//2, rn*3//4, rn-1]
for i in sample_indices:
    if i < rn:
        wc = scan_obj.matrix_world @ scan_obj.data.vertices[i].co
        print(f"  v{i}: world={list(wc)}")