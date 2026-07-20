"""
MediaPipe 面部特征点 + 约束贴合
1. 渲染扫描正面视图
2. MediaPipe 468 个面部特征点
3. 2D → 3D 映射（raycast）
4. 特征点约束 + Shrinkwrap 贴合
"""
import bpy, os, numpy as np, time, math
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final"
BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
print("1. 加载场景 + 设置相机")
bpy.ops.wm.open_mainfile(filepath=BLEND)
scan_obj = bpy.data.objects.get("Scan_Head")

# 删除无关物体
for obj in list(bpy.data.objects):
    if obj.type=='MESH' and obj!=scan_obj:
        bpy.data.objects.remove(obj, do_unlink=True)

# 获取扫描包围盒
sm = scan_obj.matrix_world
vs = [sm @ v.co for v in scan_obj.data.vertices]
xs=[v.x for v in vs]; ys=[v.y for v in vs]; zs=[v.z for v in vs]
center_x = (min(xs)+max(xs))/2; center_y = (min(ys)+max(ys))/2; center_z = (min(zs)+max(zs))/2

# 从6个方向渲染
bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
bpy.context.scene.render.resolution_x = 512
bpy.context.scene.render.resolution_y = 512
bpy.context.scene.render.film_transparent = False

# 添加灯光
bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
sun = bpy.context.active_object
sun.data.energy = 5.0

# 添加相机
bpy.ops.object.camera_add()
cam = bpy.context.active_object
bpy.context.scene.camera = cam

scan_center = Vector((center_x, center_y, center_z))
sz = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))

# 6个方向
directions = [
    ('+Y', Vector((0, 1, 0))),   # 前
    ('-Y', Vector((0, -1, 0))),  # 后
    ('+X', Vector((1, 0, 0))),   # 右
    ('-X', Vector((-1, 0, 0))),  # 左
    ('+Z', Vector((0, 0, 1))),   # 上
    ('-Z', Vector((0, 0, -1))),  # 下
]

render_paths = {}
for name, direction in directions:
    cam.location = scan_center + direction * (sz + 0.5)
    # Look at center
    look_dir = scan_center - cam.location
    cam.rotation_euler = look_dir.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    
    path = os.path.join(OUTPUT_DIR, f"scan_{name}.png")
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    render_paths[name] = path
    print(f"  渲染 {name}: {path}")

# ============================================================
print("\n3. MediaPipe 面部特征点检测（尝试6个方向）")
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import cv2

model_path = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final\face_landmarker.task"

options = vision.FaceLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path=model_path),
    running_mode=vision.RunningMode.IMAGE,
    num_faces=1
)
detector = vision.FaceLandmarker.create_from_options(options)

best_result = None
best_dir = None
best_count = 0

for name, path in render_paths.items():
    img = cv2.imread(path)
    img = cv2.resize(img, (256, 256))
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    
    result = detector.detect(mp_img)
    if result.face_landmarks:
        count = len(result.face_landmarks[0])
        print(f"  {name}: {count} landmarks ✅")
        if count > best_count:
            best_result = result
            best_dir = name
            best_count = count
    else:
        print(f"  {name}: 未检测到脸")

detector.close()

if not best_result:
    print("  所有方向都未检测到面部! 检查渲染图")
    raise SystemExit(1)

print(f"  最佳方向: {best_dir} ({best_count} landmarks)")

face_landmarks = best_result.face_landmarks[0]
h, w = 256, 256

# 选择关键特征点
key_indices = {
    'nose_tip': 1,
    'left_eye_outer': 33, 'right_eye_outer': 263,
    'left_eye_inner': 133, 'right_eye_inner': 362,
    'left_mouth': 61, 'right_mouth': 291,
    'chin': 199,
    'forehead': 10,
    'nose_bridge': 6,
}

landmarks_2d = {}
for name, idx in key_indices.items():
    lm = face_landmarks[idx]
    landmarks_2d[name] = (lm.x * w, lm.y * h)
    print(f"    {name}: pixel=({lm.x*w:.0f}, {lm.y*h:.0f})")

# ============================================================
print("\n4. 2D → 3D 映射（使用最佳方向相机）")

# 获取最佳方向对应的相机参数
best_dir_vec = dict(directions)[best_dir]
cam.location = scan_center + best_dir_vec * (sz + 0.5)
look_dir = scan_center - cam.location
cam.rotation_euler = look_dir.to_track_quat('-Z', 'Y').to_euler()
bpy.context.view_layer.update()

cam_mat = cam.matrix_world
cam_pos = cam_mat.translation
fov = cam.data.angle
aspect = 1.0  # 512x512

# 对每个 2D 特征点，从相机位置发射射线
landmarks_3d = {}
for name, (px, py) in landmarks_2d.items():
    # 归一化到 [-1, 1]
    nx = (px / w) * 2 - 1
    ny = (py / h) * 2 - 1
    
    # 在相机空间中计算射线方向
    ray_cam = Vector((nx * math.tan(fov/2) * aspect, ny * math.tan(fov/2), -1))
    ray_cam.normalize()
    
    # 转换到世界空间
    ray_world = cam_mat.to_3x3() @ ray_cam
    ray_world.normalize()
    
    # 从相机位置发射射线（在扫描的局部空间）
    ray_origin_local = sm.inverted() @ cam_pos
    ray_dir_local = (sm.inverted().to_3x3() @ ray_world).normalized()
    
    # Ray cast
    hit, loc, normal, face_idx = scan_obj.ray_cast(ray_origin_local, ray_dir_local, distance=2.0)
    
    if hit:
        world_pos = sm @ loc
        landmarks_3d[name] = world_pos
        dist = (world_pos - cam_pos).length
        print(f"    {name}: 3D=({world_pos.x:.4f},{world_pos.y:.4f},{world_pos.z:.4f}) dist={dist:.3f}m")

print(f"  成功映射 {len(landmarks_3d)}/{len(landmarks_2d)} 个特征点到3D")

# ============================================================
print("\n5. 导入模板 + 特征点检测")

bpy.ops.wm.obj_import(filepath=TEMPLATE)
template_obj = None
for obj in bpy.data.objects:
    if obj.type=='MESH' and obj!=scan_obj: template_obj=obj; break

# 旋转模板匹配扫描坐标
rot = scan_obj.rotation_euler[0]
rot_mat = Matrix.Rotation(rot, 3, 'X')
for v in template_obj.data.vertices:
    v.co = rot_mat @ v.co
template_obj.data.update()

# 中心对齐
def bbox(obj):
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs=[v.x for v in vs];ys=[v.y for v in vs];zs=[v.z for v in vs]
    return {'center':((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2)}
tb = bbox(template_obj); sb = bbox(scan_obj)
off = [sb['center'][i]-tb['center'][i] for i in range(3)]
template_obj.location.x += off[0]; template_obj.location.y += off[1]; template_obj.location.z += off[2]
bpy.context.view_layer.update()

# 伸缩比
sr = [sb['size'][i]/tb['size'][i] if tb['size'][i]>1e-6 else 1 for i in range(3)]
us = sum(sr)/3
template_obj.scale = (us, us, us)
bpy.context.view_layer.update()

tm = template_obj.matrix_world; tm_inv = tm.inverted()
sm = scan_obj.matrix_world; sm_inv = sm.inverted()

# 模板上检测对应特征点
tcoords = np.array([tm @ v.co for v in template_obj.data.vertices])
yr = np.max(tcoords[:,1]) - np.min(tcoords[:,1]); zr = np.max(tcoords[:,2]) - np.min(tcoords[:,2])
y_mid = (np.min(tcoords[:,1]) + np.max(tcoords[:,1]))/2

template_features = {}
# 鼻尖：脸正面 Z 最大
face = tcoords[tcoords[:,2] > np.min(tcoords[:,2]) + 0.7*zr]
if len(face) > 0:
    idx = np.argmax(face[:,2])
    mask = np.all(np.abs(tcoords - face[idx]) < 0.001, axis=1)
    template_features['nose_tip'] = np.where(mask)[0][0]

# 眼内角：眼区 Z 最小
eye_y = np.min(tcoords[:,1]) + 0.55*yr
eye_mask = (np.abs(tcoords[:,1] - eye_y) < 0.06*yr) & (tcoords[:,2] > np.min(tcoords[:,2])+0.5*zr)
le = eye_mask & (tcoords[:,0] < 0); re = eye_mask & (tcoords[:,0] > 0)
if np.any(le):
    idx = np.where(le)[0]; template_features['left_eye_inner'] = idx[np.argmin(tcoords[idx,2])]
if np.any(re):
    idx = np.where(re)[0]; template_features['right_eye_inner'] = idx[np.argmin(tcoords[idx,2])]

# 嘴角
mouth_y = np.min(tcoords[:,1]) + 0.32*yr
mm = (np.abs(tcoords[:,1]-mouth_y) < 0.04*yr) & (tcoords[:,2] > np.min(tcoords[:,2])+0.5*zr)
lm = mm & (tcoords[:,0] < 0); rm = mm & (tcoords[:,0] > 0)
if np.any(lm):
    idx = np.where(lm)[0]; template_features['left_mouth'] = idx[np.argmin(tcoords[idx,0])]
if np.any(rm):
    idx = np.where(rm)[0]; template_features['right_mouth'] = idx[np.argmax(tcoords[idx,0])]

# 下巴
cm = (tcoords[:,1] < np.min(tcoords[:,1]) + 0.1*yr) & (tcoords[:,2] > np.min(tcoords[:,2]) + 0.3*zr)
if np.any(cm):
    idx = np.where(cm)[0]; template_features['chin'] = idx[np.argmin(tcoords[idx,1])]

# 眉心
br_mask = (np.abs(tcoords[:,1] - (np.min(tcoords[:,1])+0.68*yr)) < 0.03*yr) & (np.abs(tcoords[:,0]) < 0.005)
if np.any(br_mask):
    idx = np.where(br_mask)[0]; template_features['nose_bridge'] = idx[np.argmax(tcoords[idx,2])]

print(f"  模板特征点: {len(template_features)}")

# 匹配特征点对
lm_pairs = []
for name in template_features:
    if name in landmarks_3d:
        lm_pairs.append((template_features[name], landmarks_3d[name], name))
        tp = tcoords[template_features[name]]; sp = landmarks_3d[name]
        print(f"  {name}: t=({tp[0]:.4f},{tp[1]:.4f},{tp[2]:.4f}) → s=({sp.x:.4f},{sp.y:.4f},{sp.z:.4f})")

# ============================================================
print(f"\n6. 特征点约束 + Shrinkwrap ({len(lm_pairs)} 对特征点)")

# 用特征点做最优刚性变换
t_pts = np.array([tcoords[p[0]] for p in lm_pairs])
s_pts = np.array([[p[1].x, p[1].y, p[1].z] for p in lm_pairs])

tc = np.mean(t_pts, axis=0); sc = np.mean(s_pts, axis=0)
t_centered = t_pts - tc; s_centered = s_pts - sc
scale = np.sum(np.linalg.norm(s_centered, axis=1)) / max(np.sum(np.linalg.norm(t_centered, axis=1)), 1e-6)
print(f"  特征点缩放: {scale:.4f}")

template_obj.scale = (us * scale, us * scale, us * scale)
bpy.context.view_layer.update()
tm = template_obj.matrix_world; tm_inv = tm.inverted()

tcoords2 = np.array([tm @ v.co for v in template_obj.data.vertices])
tc2 = np.mean([tcoords2[p[0]] for p in lm_pairs], axis=0)
trans = sc - tc2
template_obj.location.x += trans[0]; template_obj.location.y += trans[1]; template_obj.location.z += trans[2]
bpy.context.view_layer.update()

# Shrinkwrap
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
    csm.factor = 0.15
    bpy.ops.object.modifier_apply(modifier="CS")

# ============================================================
print("\n7. 验证特征点精度")
tm = template_obj.matrix_world
for name, ti in template_features.items():
    if name in landmarks_3d:
        wp = tm @ template_obj.data.vertices[ti].co
        err = (wp - landmarks_3d[name]).length
        print(f"  {name}: err={err*1000:.1f}mm")

# 保存
print("\n8. 保存")
out = os.path.join(OUTPUT_DIR, "head_mediapipe.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
template_obj.select_set(True); bpy.context.view_layer.objects.active = template_obj
bpy.ops.export_scene.gltf(filepath=os.path.join(OUTPUT_DIR, "head_mediapipe.glb"),
                           use_selection=True, export_format='GLB', export_apply=True)
print(f"  {out}")