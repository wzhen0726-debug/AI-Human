"""
诊断 v2：检查新 OBJ 拓扑 + 对齐状态
"""
import bpy
import random
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
import numpy as np

BLEND_FILE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"

# 加载 blend
bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)
scan_obj = bpy.data.objects.get("Scan_Head")

# 导入 OBJ
bpy.ops.wm.obj_import(filepath=TEMPLATE_PATH)
template_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH' and obj.name != 'Scan_Head':
        template_obj = obj
        break

tm = template_obj.matrix_world
sm = scan_obj.matrix_world

print("=" * 60)
print("1. 模板拓扑检查")
print("=" * 60)
mesh = template_obj.data
print(f"顶点: {len(mesh.vertices)}")
print(f"边: {len(mesh.edges)}")
print(f"面: {len(mesh.polygons)}")

tri = sum(1 for p in mesh.polygons if len(p.vertices) == 3)
quad = sum(1 for p in mesh.polygons if len(p.vertices) == 4)
ngon = sum(1 for p in mesh.polygons if len(p.vertices) > 4)
print(f"三角面: {tri}")
print(f"四边面: {quad}")
print(f"N-gon: {ngon}")

# 度数分布
valence = {}
for e in mesh.edges:
    for vi in e.vertices:
        valence[vi] = valence.get(vi, 0) + 1
v3 = sum(1 for c in valence.values() if c == 3)
v4 = sum(1 for c in valence.values() if c == 4)
v5 = sum(1 for c in valence.values() if c == 5)
v6p = sum(1 for c in valence.values() if c > 5)
print(f"度数: 3度={v3}, 4度={v4}, 5度={v5}, 6度+={v6p}")

print("\n" + "=" * 60)
print("2. 对齐状态")
print("=" * 60)

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

print(f"模板中心: ({tb['center'][0]:.4f}, {tb['center'][1]:.4f}, {tb['center'][2]:.4f})")
print(f"模板尺寸: ({tb['size'][0]:.4f}, {tb['size'][1]:.4f}, {tb['size'][2]:.4f})")
print(f"扫描中心: ({sb['center'][0]:.4f}, {sb['center'][1]:.4f}, {sb['center'][2]:.4f})")
print(f"扫描尺寸: ({sb['size'][0]:.4f}, {sb['size'][1]:.4f}, {sb['size'][2]:.4f})")

offset = [sb['center'][i] - tb['center'][i] for i in range(3)]
print(f"中心偏移: ({offset[0]:.4f}, {offset[1]:.4f}, {offset[2]:.4f})")

scale = [sb['size'][i] / tb['size'][i] if tb['size'][i] > 1e-6 else 1 for i in range(3)]
print(f"尺寸比(扫描/模板): ({scale[0]:.4f}, {scale[1]:.4f}, {scale[2]:.4f})")

print(f"\n扫描旋转: {list(scan_obj.rotation_euler)}")
print(f"模板旋转: {list(template_obj.rotation_euler)}")

# 检查扫描是否旋转了90度
if abs(scan_obj.rotation_euler[0] - 1.57) < 0.01:
    print("\n⚠ 扫描绕X轴旋转了90度！需要修正。")

print("\n" + "=" * 60)
print("3. 刚性ICP对齐建议")
print("=" * 60)

# 采样模板和扫描的顶点
t_verts = [tm @ v.co for v in template_obj.data.vertices]
scan_n = len(scan_obj.data.vertices)
sample_step = max(1, scan_n // 50000)
s_verts = [sm @ scan_obj.data.vertices[i].co for i in range(0, scan_n, sample_step)]

# 构建KDTree
kd = KDTree(len(s_verts))
for i, v in enumerate(s_verts):
    kd.insert(v, i)
kd.balance()

# 计算模板到扫描的距离
distances = []
for v in t_verts:
    co, idx, dist = kd.find(tuple(v))
    distances.append(dist)

distances = np.array(distances)
print(f"当前模板到扫描距离: 平均={np.mean(distances):.4f}m, 中位数={np.median(distances):.4f}m, 最大={np.max(distances):.4f}m")

# 计算建议的缩放因子
uniform_scale = np.mean(scale)
print(f"\n建议均匀缩放: {uniform_scale:.4f}")
print(f"建议中心偏移: ({offset[0]:.4f}, {offset[1]:.4f}, {offset[2]:.4f})")