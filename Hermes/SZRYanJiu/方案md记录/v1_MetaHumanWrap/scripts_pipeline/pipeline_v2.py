"""
Tripo 高模 → 合规数字人 v2
1. 导入 + 缩放到 1.8m
2. 几何分析检测关节位置
3. 放置 Rigify 骨骼到检测到的位置
4. 绑定 + 生成控制 rig
"""
import bpy, os, time, numpy as np, math
from mathutils import Vector, Matrix

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final"
TRIPO = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\原始Tripo高模\tripo_01.glb"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
print("="*70)
print("阶段 1: 导入 + 缩放到 1.8m")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=TRIPO)
tripo = None
for obj in bpy.data.objects:
    if obj.type == 'MESH': tripo = obj; break

bpy.context.view_layer.objects.active = tripo
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

verts = np.array([v.co for v in tripo.data.vertices])
z_range = verts[:,2].max() - verts[:,2].min()
scale_factor = 1.8 / z_range
tripo.scale = (scale_factor, scale_factor, scale_factor)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

verts = np.array([v.co for v in tripo.data.vertices])
print(f"  缩放后: 高={verts[:,2].max()-verts[:,2].min():.3f}m ({len(tripo.data.vertices):,}v, {len(tripo.data.polygons):,}f)")
print(f"  BBox: X[{verts[:,0].min():.3f},{verts[:,0].max():.3f}] Y[{verts[:,1].min():.3f},{verts[:,1].max():.3f}] Z[{verts[:,2].min():.3f},{verts[:,2].max():.3f}]")

# 居中（脚在 Z=0）
z_min = verts[:,2].min()
for v in tripo.data.vertices:
    v.co.z -= z_min
tripo.data.update()
verts = np.array([v.co for v in tripo.data.vertices])
print(f"  居中后: Z[{verts[:,2].min():.3f},{verts[:,2].max():.3f}]")

# ============================================================
print("\n阶段 2: 精简 + 清理")
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.0001)
bpy.ops.mesh.delete_loose()
bpy.ops.mesh.normals_make_consistent(inside=False)

# 精简到 ~400K tris
target = 400000
current = len(tripo.data.polygons)
if current > target:
    ratio = target / current
    bpy.ops.mesh.decimate(ratio=ratio)
bpy.ops.object.mode_set(mode='OBJECT')
print(f"  精简后: {len(tripo.data.vertices):,}v {len(tripo.data.polygons):,}f")

# ============================================================
print("\n阶段 3: 几何分析 — 检测关节位置")

verts = np.array([v.co for v in tripo.data.vertices])
z_min, z_max = verts[:,2].min(), verts[:,2].max()
height = z_max - z_min
print(f"  身高: {height:.3f}m")

def slice_analysis(z_lo, z_hi):
    """分析 Z 高度范围内的水平截面，返回中心和左右极值"""
    mask = (verts[:,2] >= z_lo) & (verts[:,2] <= z_hi)
    if not np.any(mask): return None
    pts = verts[mask]
    center = pts.mean(axis=0)
    x_min = pts[:,0].min(); x_max = pts[:,0].max()
    y_min = pts[:,1].min(); y_max = pts[:,1].max()
    return {
        'center': (center[0], center[1], (z_lo+z_hi)/2),
        'x_range': (x_min, x_max),
        'y_range': (y_min, y_max),
        'count': len(pts)
    }

# --- 检测头部 ---
head_slice = slice_analysis(z_max - 0.15*height, z_max)
head_z = head_slice['center'][2] if head_slice else z_max * 0.92
head_x = head_slice['center'][0] if head_slice else 0
head_y = head_slice['center'][1] if head_slice else 0

# --- 检测脚底 ---
foot_slice = slice_analysis(z_min, z_min + 0.05*height)
foot_z = foot_slice['center'][2] if foot_slice else z_min + 0.02

# --- 检测躯干（多个截面） ---
slices_data = []
for frac in np.linspace(0.15, 0.95, 20):
    z = z_min + frac * height
    s = slice_analysis(z - 0.02*height, z + 0.02*height)
    if s: slices_data.append(s)

# --- 检测髋部（最宽的截面在下半身） ---
lower_slices = [s for s in slices_data if s['center'][2] < height*0.55]
if lower_slices:
    hip_slice = max(lower_slices, key=lambda s: s['x_range'][1] - s['x_range'][0])
    hip_z = hip_slice['center'][2]
    hip_x = hip_slice['center'][0]
    hip_y = hip_slice['center'][1]
else:
    hip_z = height * 0.5
    hip_x = hip_y = 0

# --- 检测肩部（上半身最宽的截面） ---
upper_slices = [s for s in slices_data if s['center'][2] > hip_z + 0.05*height]
if upper_slices:
    shoulder_slice = max(upper_slices, key=lambda s: s['x_range'][1] - s['x_range'][0])
    shoulder_z = shoulder_slice['center'][2]
    shoulder_x = shoulder_slice['center'][0]
    shoulder_y = shoulder_slice['center'][1]
else:
    shoulder_z = height * 0.78
    shoulder_x = shoulder_y = 0

# --- 检测脊椎 ---
spine_zs = []
for frac in np.linspace(0.15, 0.85, 6):
    z = z_min + frac * height
    s = slice_analysis(z - 0.03*height, z + 0.03*height)
    if s: spine_zs.append(s['center'])

# --- 检测膝盖 ---
knee_region = slice_analysis(z_min + 0.25*height, z_min + 0.35*height)
knee_z = knee_region['center'][2] if knee_region else height * 0.28

# --- 检测腿部 ---
# 在膝关节以下找两条腿的截面
leg_slice = slice_analysis(knee_z - 0.03*height, knee_z + 0.03*height)
leg_centers = []
if leg_slice:
    x_min, x_max = leg_slice['x_range']
    # 粗略分左右腿
    mid_x = (x_min + x_max) / 2
    left_pts = verts[(verts[:,2] >= leg_slice['center'][2] - 0.03*height) & 
                      (verts[:,2] <= leg_slice['center'][2] + 0.03*height) & 
                      (verts[:,0] < mid_x)]
    right_pts = verts[(verts[:,2] >= leg_slice['center'][2] - 0.03*height) & 
                       (verts[:,2] <= leg_slice['center'][2] + 0.03*height) & 
                       (verts[:,0] > mid_x)]
    if len(left_pts) > 10:
        leg_centers.append(('left', left_pts.mean(axis=0)))
    if len(right_pts) > 10:
        leg_centers.append(('right', right_pts.mean(axis=0)))

# --- 检测手臂 ---
arm_slices = []
for frac in np.linspace(0.55, 0.75, 5):
    z = z_min + frac * height
    s = slice_analysis(z - 0.02*height, z + 0.02*height)
    if s: arm_slices.append(s)

arm_data = {'left': [], 'right': []}
for s in arm_slices:
    x_min, x_max = s['x_range']
    mid_x = s['center'][0]
    # 左右臂：在躯干两侧的截面点
    arm_data['left'].append((s['center'][2], x_min, x_min))
    arm_data['right'].append((s['center'][2], x_max, x_max))

print(f"  检测结果:")
print(f"    头: ({head_x:.3f}, {head_y:.3f}, {head_z:.3f})")
print(f"    肩: ({shoulder_x:.3f}, {shoulder_y:.3f}, {shoulder_z:.3f})")
print(f"    髋: ({hip_x:.3f}, {hip_y:.3f}, {hip_z:.3f})")
print(f"    膝: {knee_z:.3f}")
print(f"    脚: {foot_z:.3f}")
print(f"    腿: {[f'{side}({c[0]:.2f},{c[2]:.2f})' for side,c in leg_centers]}")

# ============================================================
print("\n阶段 4: 放置 Rigify 骨骼到检测位置")

bpy.ops.object.select_all(action='DESELECT')
bpy.ops.object.armature_human_metarig_add()
rig = bpy.context.active_object
rig.name = "MetaRig"
rig.location = (0, 0, 0)

# 进入编辑模式
bpy.ops.object.mode_set(mode='EDIT')
edit_bones = rig.data.edit_bones

# 找到骨骼名称映射
bone_map = {b.name: b for b in edit_bones}
for name in bone_map:
    bone_map[name].select = False

# 辅助函数：设置骨骼位置
def set_bone(name, head_pos, tail_pos):
    if name in bone_map:
        b = bone_map[name]
        b.head = Vector(head_pos)
        b.tail = Vector(tail_pos)
    else:
        print(f"    警告: 找不到骨骼 {name}")

# 头部
set_bone('head', (head_x, head_y, head_z - 0.08), (head_x, head_y, head_z + 0.05))
neck_z = head_z - 0.12*height
set_bone('neck', (shoulder_x, shoulder_y, neck_z), (head_x, head_y, head_z - 0.08))

# 脊椎
spine_bones = ['spine', 'spine.001', 'spine.002', 'spine.003']
spine_zs_list = np.linspace(hip_z + 0.05, neck_z - 0.02, len(spine_bones) + 1)
for i, name in enumerate(spine_bones):
    if i < len(spine_zs_list) - 1:
        z_lo = spine_zs_list[i]
        z_hi = spine_zs_list[i + 1]
        set_bone(name, (shoulder_x, shoulder_y, z_lo), (shoulder_x, shoulder_y, z_hi))

# 髋部
set_bone('hips', (hip_x, hip_y, hip_z - 0.05), (hip_x, hip_y, hip_z + 0.08))

# 腿部
# 左腿
left_leg_z = [hip_z * 0.85, knee_z, z_min + 0.05]
for i, name in enumerate(['thigh.L', 'shin.L', 'foot.L']):
    if i < len(left_leg_z) - 1:
        leg_x = 0
        for side, c in leg_centers:
            if 'left' in side: leg_x = c[0]
        z_lo = left_leg_z[i]; z_hi = left_leg_z[i+1] if i+1 < len(left_leg_z) else z_lo + 0.01
        set_bone(name, (leg_x*0.6, hip_y, z_lo), (leg_x*0.6, hip_y, z_hi))
# 右腿
right_leg_z = [hip_z * 0.85, knee_z, z_min + 0.05]
for i, name in enumerate(['thigh.R', 'shin.R', 'foot.R']):
    if i < len(right_leg_z) - 1:
        leg_x = 0
        for side, c in leg_centers:
            if 'right' in side: leg_x = c[0]
        z_lo = right_leg_z[i]; z_hi = right_leg_z[i+1] if i+1 < len(right_leg_z) else z_lo + 0.01
        set_bone(name, (leg_x*0.6, hip_y, z_lo), (leg_x*0.6, hip_y, z_hi))

# 手臂 - 沿身体侧面下垂
shoulder_x_left = -0.058
shoulder_x_right = 0.058
arm_zs = [shoulder_z*0.95, shoulder_z*0.65, shoulder_z*0.4]
for side, prefix, sx in [('L', '.L', shoulder_x_left), ('R', '.R', shoulder_x_right)]:
    for i, name in enumerate([f'upper_arm{prefix}', f'forearm{prefix}', f'hand{prefix}']):
        if i < len(arm_zs):
            z = arm_zs[i]
            set_bone(name, (sx, shoulder_y, z), (sx*0.8, shoulder_y, z - 0.05))

bpy.ops.object.mode_set(mode='OBJECT')
print("  骨骼放置完成")

# ============================================================
print("\n阶段 5: 绑定 + Rigify 生成")

tripo.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = tripo
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
print("  自动权重完成")

bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT')
bpy.ops.pose.rigify_generate()
bpy.ops.object.mode_set(mode='OBJECT')
print("  Rigify 控制 rig 生成完成")

# 找控制 rig
rig_ctrl = None
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE' and 'RIG-' in obj.name:
        rig_ctrl = obj
        break

# ============================================================
print("\n阶段 6: 清理 + 保存")

# 删除原始 MetaRig
if rig:
    bpy.data.objects.remove(rig, do_unlink=True)

# 集合
wgt_col = bpy.data.collections.new(name="RigWidgets")
main_col = bpy.data.collections.new(name="Character")
bpy.context.scene.collection.children.link(wgt_col)
bpy.context.scene.collection.children.link(main_col)

for obj in list(bpy.data.objects):
    if obj.name.startswith("WGT-"):
        for col in obj.users_collection:
            col.objects.unlink(obj)
        wgt_col.objects.link(obj)

for obj in [tripo, rig_ctrl]:
    if obj:
        for col in obj.users_collection:
            col.objects.unlink(obj)
        main_col.objects.link(obj)

bpy.ops.object.select_all(action='DESELECT')
bpy.ops.object.select_by_type(type='CAMERA')
bpy.ops.object.select_by_type(type='LIGHT')
bpy.ops.object.delete()

out = os.path.join(OUTPUT_DIR, "tripo_v2.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)

tripo.select_set(True)
bpy.context.view_layer.objects.active = tripo
bpy.ops.export_scene.gltf(
    filepath=os.path.join(OUTPUT_DIR, "tripo_v2.glb"),
    use_selection=True, export_format='GLB', export_apply=True
)

quads = sum(1 for p in tripo.data.polygons if len(p.vertices)==4)
tris = sum(1 for p in tripo.data.polygons if len(p.vertices)==3)
print(f"\n{'='*70}")
print(f"完成: {out}")
print(f"  模型: {len(tripo.data.vertices):,}v {len(tripo.data.polygons):,}f ({quads}Q/{tris}T)")
print(f"  绑定: {rig_ctrl.name if rig_ctrl else 'N/A'}")