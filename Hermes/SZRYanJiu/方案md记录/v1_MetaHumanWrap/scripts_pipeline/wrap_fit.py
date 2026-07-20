"""
MetaHuman 式包裹：模板特征点 + 扫描特征点 → 约束贴合
1. 模板上自动检测面部特征点（鼻尖、眼角、嘴角、眉心等）
2. 扫描上找几何极值对应点
3. 特征点约束 + Shrinkwrap 贴合
"""
import bpy, os, numpy as np, time
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
import math

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final"
BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
print("1. 加载")
bpy.ops.wm.open_mainfile(filepath=BLEND)
scan_obj = bpy.data.objects.get("Scan_Head")
for obj in list(bpy.data.objects):
    if obj.type=='MESH' and obj!=scan_obj: bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.wm.obj_import(filepath=TEMPLATE)
template_obj = None
for obj in bpy.data.objects:
    if obj.type=='MESH' and obj!=scan_obj: template_obj=obj; break

# 关键修复：用直接顶点旋转匹配扫描坐标系
rot = scan_obj.rotation_euler[0]  # ~1.57 rad (90 deg around X)
rot_mat = Matrix.Rotation(rot, 3, 'X')
for v in template_obj.data.vertices:
    v.co = rot_mat @ v.co
template_obj.data.update()

tm = template_obj.matrix_world; sm = scan_obj.matrix_world
scan_n = len(scan_obj.data.vertices)

# 中心对齐
def bbox(obj):
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs=[v.x for v in vs];ys=[v.y for v in vs];zs=[v.z for v in vs]
    return {'center':((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2),
            'size':(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs))}
tb = bbox(template_obj); sb = bbox(scan_obj)
print(f"  模板bbox: ({tb['size'][0]:.3f},{tb['size'][1]:.3f},{tb['size'][2]:.3f})")
print(f"  扫描bbox: ({sb['size'][0]:.3f},{sb['size'][1]:.3f},{sb['size'][2]:.3f})")
off = [sb['center'][i]-tb['center'][i] for i in range(3)]
template_obj.location.x += off[0]; template_obj.location.y += off[1]; template_obj.location.z += off[2]
bpy.context.view_layer.update()

# 缩放匹配
sr = [sb['size'][i]/tb['size'][i] if tb['size'][i]>1e-6 else 1 for i in range(3)]
us = sum(sr)/3
print(f"  缩放比: {sr} → 均匀={us:.4f}")
template_obj.scale = (us, us, us)
bpy.context.view_layer.update()
tm = template_obj.matrix_world; tm_inv = tm.inverted()
sm = scan_obj.matrix_world; sm_inv = sm.inverted()

# ============================================================
print("2. 扫描 KDTree")
sp = max(1, scan_n // 500000)
kd = KDTree(scan_n // sp + 1)
for i in range(0, scan_n, sp): kd.insert(sm @ scan_obj.data.vertices[i].co, i)
kd.balance()

# ============================================================
print("3. 模板特征点检测")
tcoords = np.array([tm @ v.co for v in template_obj.data.vertices])
n_verts = len(tcoords)
y_min, y_max = np.min(tcoords[:,1]), np.max(tcoords[:,1])
z_min, z_max = np.min(tcoords[:,2]), np.max(tcoords[:,2])
yr = y_max - y_min; zr = z_max - z_min

features = {}

# 鼻尖: 脸正面最高 Z 的顶点
face_fwd = tcoords[tcoords[:,2] > z_min + 0.7*zr]
if len(face_fwd) > 0:
    ni = np.argmax(face_fwd[:,2])
    mask = np.all(np.abs(tcoords - face_fwd[ni]) < 0.001, axis=1)
    features['nose_tip'] = np.where(mask)[0][0]

# 左眼角: 眼区 Z 最小（最凹陷）
eye_lo = y_min + 0.55*yr; eye_hi = y_min + 0.75*yr
eye_m = (tcoords[:,1] > eye_lo) & (tcoords[:,1] < eye_hi) & (tcoords[:,2] > z_min + 0.5*zr)
le_m = eye_m & (tcoords[:,0] < -0.01)
re_m = eye_m & (tcoords[:,0] > 0.01)
if np.any(le_m):
    idx = np.where(le_m)[0]; features['left_eye'] = idx[np.argmin(tcoords[idx,2])]
if np.any(re_m):
    idx = np.where(re_m)[0]; features['right_eye'] = idx[np.argmin(tcoords[idx,2])]

# 嘴角: 嘴区 X 最外
mouth_y = y_min + 0.32*yr
mm = (np.abs(tcoords[:,1] - mouth_y) < 0.04*yr) & (tcoords[:,2] > z_min + 0.5*zr)
lm = mm & (tcoords[:,0] < -0.01); rm = mm & (tcoords[:,0] > 0.01)
if np.any(lm):
    idx = np.where(lm)[0]; features['left_mouth'] = idx[np.argmin(tcoords[idx,0])]
if np.any(rm):
    idx = np.where(rm)[0]; features['right_mouth'] = idx[np.argmax(tcoords[idx,0])]

# 下巴: Y 最小 + Z 大
cm = (tcoords[:,1] < y_min + 0.1*yr) & (tcoords[:,2] > z_min + 0.3*zr)
if np.any(cm):
    idx = np.where(cm)[0]; features['chin'] = idx[np.argmin(tcoords[idx,1])]

# 眉心: Y 在两眼之间
br = (tcoords[:,1] > y_min + 0.65*yr) & (tcoords[:,1] < y_min + 0.72*yr) & (np.abs(tcoords[:,0]) < 0.005) & (tcoords[:,2] > z_min + 0.5*zr)
if np.any(br):
    idx = np.where(br)[0]; features['nose_bridge'] = idx[np.argmax(tcoords[idx,2])]

# 额头中心
fh = (tcoords[:,1] > y_min + 0.85*yr) & (np.abs(tcoords[:,0]) < 0.005)
if np.any(fh):
    idx = np.where(fh)[0]; features['forehead'] = idx[np.argmax(tcoords[idx,2])]

# 左右颧骨
for side, s in [('left_cheek', -1), ('right_cheek', 1)]:
    ck = (np.abs(tcoords[:,1] - (y_min+0.5*yr)) < 0.03*yr) & (s*tcoords[:,0] > 0.02) & (tcoords[:,2] > z_min+0.5*zr)
    if np.any(ck):
        idx = np.where(ck)[0]; features[side] = idx[np.argmax(tcoords[idx,2])]

print(f"  模板特征点: {len(features)}")
for name, idx in features.items():
    print(f"    {name}: ({tcoords[idx,0]:.4f},{tcoords[idx,1]:.4f},{tcoords[idx,2]:.4f})")

# ============================================================
print("\n4. 扫描特征点映射")
lm_constraints = []

for name, ti in features.items():
    tp = tcoords[ti]
    # 初始：模板特征点在扫描上的最近点
    co, ix, dist = kd.find(tuple(tp))
    refined = Vector(co)
    
    # 几何极值微调
    radius = 0.025  # 2.5cm 搜索半径
    if name == 'nose_tip':
        best_z = refined.z; bp = refined
        for i in range(0, scan_n, max(1, scan_n//300000)):
            sp = sm @ scan_obj.data.vertices[i].co
            if (sp - refined).length < radius and sp.z > best_z: best_z = sp.z; bp = sp
        refined = bp
    elif name in ('left_eye', 'right_eye'):
        best_z = refined.z; bp = refined
        for i in range(0, scan_n, max(1, scan_n//300000)):
            sp = sm @ scan_obj.data.vertices[i].co
            if (sp - refined).length < radius*1.5 and sp.z < best_z: best_z = sp.z; bp = sp
        refined = bp
    elif name == 'chin':
        best_y = refined.y; bp = refined
        for i in range(0, scan_n, max(1, scan_n//300000)):
            sp = sm @ scan_obj.data.vertices[i].co
            if (sp - refined).length < radius and sp.y < best_y: best_y = sp.y; bp = sp
        refined = bp
    
    lm_constraints.append((ti, refined, name))
    print(f"  {name}: t=({tp[0]:.4f},{tp[1]:.4f},{tp[2]:.4f}) → s=({refined.x:.4f},{refined.y:.4f},{refined.z:.4f}) d={dist*1000:.1f}mm")

# ============================================================
print("\n5. 特征点约束 + Shrinkwrap 贴合")

# 先做特征点约束的刚性变形
# 用特征点先做一次全局缩放+平移，让关键特征大致对齐
t_pts = np.array([tcoords[lm[0]] for lm in lm_constraints])
s_pts = np.array([lm[1] for lm in lm_constraints])

# 计算最优缩放
t_centroid = np.mean(t_pts, axis=0); s_centroid = np.mean(s_pts, axis=0)
t_centered = t_pts - t_centroid; s_centered = s_pts - s_centroid
scale_opt = np.sum(np.linalg.norm(s_centered, axis=1)) / max(np.sum(np.linalg.norm(t_centered, axis=1)), 1e-6)
print(f"  特征点最优缩放: {scale_opt:.4f}")

# 应用缩放+平移
template_obj.scale = (us * scale_opt, us * scale_opt, us * scale_opt)
bpy.context.view_layer.update()
tm = template_obj.matrix_world; tm_inv = tm.inverted()

# 平移使特征点质心对齐
tcoords2 = np.array([tm @ v.co for v in template_obj.data.vertices])
t_centroid2 = np.mean([tcoords2[lm[0]] for lm in lm_constraints], axis=0)
translation = s_centroid - t_centroid2
template_obj.location.x += translation[0]; template_obj.location.y += translation[1]; template_obj.location.z += translation[2]
bpy.context.view_layer.update()
tm = template_obj.matrix_world; tm_inv = tm.inverted()

# 现在做 Shrinkwrap——但特征点区域用更轻的力度
print("  Shrinkwrap 贴合...")
for i in range(4):
    sw = template_obj.modifiers.new("SW", 'SHRINKWRAP')
    sw.target = scan_obj
    sw.wrap_method = 'NEAREST_SURFACEPOINT' if i < 2 else 'PROJECT'
    sw.wrap_mode = 'ON_SURFACE'
    if sw.wrap_method == 'PROJECT':
        sw.use_project_x = sw.use_project_y = sw.use_project_z = True
        sw.use_negative_direction = sw.use_positive_direction = True
    sw.offset = 0.0
    bpy.ops.object.modifier_apply(modifier="SW")
    
    csm = template_obj.modifiers.new("CS", 'CORRECTIVE_SMOOTH')
    csm.iterations = 2
    csm.smooth_type = 'SIMPLE'
    csm.factor = 0.2 if i < 2 else 0.1
    bpy.ops.object.modifier_apply(modifier="CS")
    print(f"  [{i+1}/4]")

# 验证特征点是否还在正确位置
print("\n6. 验证特征点位置")
tm = template_obj.matrix_world
for name, ti in features.items():
    wp = tm @ template_obj.data.vertices[ti].co
    co, ix, dist = kd.find(tuple(wp))
    print(f"  {name}: err={dist*1000:.1f}mm")

# 保存
print("\n7. 保存")
out = os.path.join(OUTPUT_DIR, "head_wrapped.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
template_obj.select_set(True); bpy.context.view_layer.objects.active = template_obj
bpy.ops.export_scene.gltf(filepath=os.path.join(OUTPUT_DIR, "head_wrapped.glb"),
                           use_selection=True, export_format='GLB', export_apply=True)
print(f"  输出: {out}")