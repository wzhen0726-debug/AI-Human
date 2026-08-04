import bpy, os, sys, math, json
from mathutils import Vector, Matrix
import bmesh

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
ALIGNED_BLEND = os.path.join(ROOT, "output", "wrap", "aligned_scene.blend")
OUT_DIR = os.path.join(ROOT, "output", "wrap")

print("="*60)
print("Step 1: 导入并分析顶点分布")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=ALIGNED_BLEND)
mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")

mesh = mh_body.data
mesh.update()

def get_bbox(obj):
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    return {
        'min': Vector((min(xs), min(ys), min(zs))),
        'max': Vector((max(xs), max(ys), max(zs))),
        'size': Vector((max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))),
        'center': Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    }

bbox = get_bbox(mh_body)
center_x = bbox['center'].x

# 分析X坐标分布
xs = [v.co.x for v in mesh.vertices]
print(f"X范围: {min(xs):.3f} to {max(xs):.3f}")
print(f"X中心: {center_x:.3f}")
print(f"X尺寸: {bbox['size'].x:.3f}")

# 统计X坐标分布
import numpy as np
xs_np = np.array(xs)
print(f"\nX坐标分布:")
print(f"  < center-0.2: {(xs_np < center_x - 0.2).sum()}")
print(f"  center-0.2 ~ center-0.1: {((xs_np >= center_x - 0.2) & (xs_np < center_x - 0.1)).sum()}")
print(f"  center-0.1 ~ center: {((xs_np >= center_x - 0.1) & (xs_np < center_x)).sum()}")
print(f"  center ~ center+0.1: {((xs_np >= center_x) & (xs_np < center_x + 0.1)).sum()}")
print(f"  center+0.1 ~ center+0.2: {((xs_np >= center_x + 0.1) & (xs_np < center_x + 0.2)).sum()}")
print(f"  > center+0.2: {(xs_np >= center_x + 0.2).sum()}")

# ============================================================
# Step 2: 重新分类手臂顶点
# ============================================================
print("\n" + "="*60)
print("Step 2: 重新分类手臂顶点")
print("="*60)

# 基于Z坐标和X坐标重新分类
# 手臂: Z > 0.5 且 |X| > center_x + 0.1
left_arm_verts = []
right_arm_verts = []
torso_verts = []

for i, v in enumerate(mesh.vertices):
    if v.co.z > 0.5:  # 上半身
        if v.co.x < center_x - 0.1:  # 左臂
            left_arm_verts.append(i)
        elif v.co.x > center_x + 0.1:  # 右臂
            right_arm_verts.append(i)
        else:  # 躯干
            torso_verts.append(i)

print(f"左臂顶点: {len(left_arm_verts)}")
print(f"右臂顶点: {len(right_arm_verts)}")
print(f"躯干顶点: {len(torso_verts)}")

# ============================================================
# Step 3: 保存分析结果
# ============================================================
print("\n" + "="*60)
print("Step 3: 保存分析结果")
print("="*60)

# 创建顶点组
for name, verts in [('left_arm', left_arm_verts), ('right_arm', right_arm_verts), ('torso', torso_verts)]:
    vg = mh_body.vertex_groups.get(name)
    if not vg:
        vg = mh_body.vertex_groups.new(name=name)
    vg.add(verts, 1.0, 'REPLACE')
    print(f"创建顶点组: {name} ({len(verts)} verts)")

blend_path = os.path.join(OUT_DIR, "vertex_groups.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"保存: {blend_path}")

print("\nDONE")
