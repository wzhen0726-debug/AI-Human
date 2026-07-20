"""
高模扫描头 → MetaHuman 低模拓扑 自动化管线
基于 mp_v2_final.py 架构，适配 Scan_Head_Lv5.obj 输入

输入：
  - 原始GLB/Scan_head/Scan_Head_Lv5.obj   (高模扫描头, ~297万顶点, Z-up, 面朝 -Y)
  - 原始GLB/MetaHuman_head/MH_Head_01.obj  (低模模板, 8280顶点, Z-up, 面朝 -Y)
  - output_final/template_landmarks.json   (模板 21 个特征点顶点索引)
  - output_final/face_landmarker.task      (MediaPipe 模型)

流程：
  1. 导入高模 + 6方向渲染
  2. MediaPipe 面部检测 → 选最佳视角
  3. 2D→3D 映射: 12面部点(raycast) + 8几何点(KDTree+局部极值)
  4. 导入低模模板 + 质心对齐 + 缩放 (仅用12面部点)
  5a. Shrinkwrap 包裹 (4轮)
  5b. 特征点锚定 (20轮迭代位移+拉普拉斯平滑)
  5c. 表面修正
  6. 质量验证
  7. 保存

改进点（vs 原管线）：
  - 输入改为 OBJ 文件，不再依赖 blend 场景
  - 高模与低模朝向一致(Z-up, 面朝-Y)，无需旋转
  - 几何特征点用 KDTree+局部极值搜索，替代朴素射线估算
    · 耳朵: 在眼角 Z 高度±偏移, X 极值顶点
    · 后脑: Y 最大(最后侧)区域顶点
    · 头顶: Z 最大区域中心
    · 后颈: Y 最大 + Z 最小区域
"""
import bpy, os, numpy as np, time, math, cv2, json, sys
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

# ============================================================
# 路径配置
ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test01"
SCAN_OBJ = os.path.join(ROOT, "原始GLB", "Scan_head", "Scan_Head_Lv5.obj")
TEMPLATE = os.path.join(ROOT, "原始GLB", "MetaHuman_head", "MH_Head_01.obj")
MODEL_PATH = os.path.join(ROOT, "output_final", "face_landmarker.task")
LANDMARK_JSON = os.path.join(ROOT, "output_final", "template_landmarks.json")
OUTPUT_DIR = os.path.join(ROOT, "output_final")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 加载模板固定特征点
with open(LANDMARK_JSON) as f:
    template_lm = json.load(f)
print(f"加载模板特征点: {len(template_lm)} 个")

def bbox_world(obj):
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs=[v.x for v in vs]; ys=[v.y for v in vs]; zs=[v.z for v in vs]
    return dict(center=((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2),
                min=(min(xs),min(ys),min(zs)), max=(max(xs),max(ys),max(zs)),
                size=(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)))

# ============================================================
print("\n" + "="*60)
print("1. 导入高模扫描头 + 6方向渲染")

# 清空场景
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 导入扫描头 OBJ
bpy.ops.wm.obj_import(filepath=SCAN_OBJ)
scan_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        scan_obj = obj; break
if not scan_obj:
    print("ERROR: 导入扫描头失败!")
    sys.exit(1)

# 统一命名为 Scan_Head, 方便后续脚本识别
scan_obj.name = "Scan_Head"

# 应用变换，居中到原点
bpy.context.view_layer.objects.active = scan_obj
scan_obj.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 居中到原点（便于后续对齐）
sb = bbox_world(scan_obj)
scan_center = Vector(sb['center'])
scan_obj.location -= scan_center
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

sb = bbox_world(scan_obj)
scan_center = Vector(sb['center'])
scan_size = sb['size']
sz = max(scan_size)
print(f"  扫描头: {len(scan_obj.data.vertices):,}v {len(scan_obj.data.polygons):,}f")
print(f"  BBox: X[{sb['min'][0]:.4f},{sb['max'][0]:.4f}] Y[{sb['min'][1]:.4f},{sb['max'][1]:.4f}] Z[{sb['min'][2]:.4f},{sb['max'][2]:.4f}]")
print(f"  Center: ({scan_center.x:.4f},{scan_center.y:.4f},{scan_center.z:.4f}) Size: {scan_size}")

# 渲染设置
bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
bpy.context.scene.render.resolution_x = 512
bpy.context.scene.render.resolution_y = 512
bpy.ops.object.light_add(type='SUN', location=(0,0,10))
bpy.context.active_object.data.energy = 5.0
bpy.ops.object.camera_add()
cam = bpy.context.active_object
bpy.context.scene.camera = cam

dirs = {'+Y':(0,1,0), '-Y':(0,-1,0), '+X':(1,0,0), '-X':(-1,0,0), '+Z':(0,0,1), '-Z':(0,0,-1)}
render_paths = {}
for name, d in dirs.items():
    cam.location = scan_center + Vector(d) * (sz + 0.5)
    cam.rotation_euler = (scan_center - cam.location).to_track_quat('-Z','Z').to_euler()
    bpy.context.view_layer.update()
    p = os.path.join(OUTPUT_DIR, f"scan_{name}.png")
    bpy.context.scene.render.filepath = p
    bpy.ops.render.render(write_still=True)
    render_paths[name] = p
    print(f"  渲染 {name}")

# ============================================================
print("\n2. MediaPipe 面部检测")
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

opt = vision.FaceLandmarkerOptions(
    base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=vision.RunningMode.IMAGE, num_faces=1)
detector = vision.FaceLandmarker.create_from_options(opt)

best_landmarks = None; best_dir = None; best_count = 0
for name, path in render_paths.items():
    img = cv2.resize(cv2.imread(path), (256,256))
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if result.face_landmarks:
        n = len(result.face_landmarks[0])
        if n > best_count: best_landmarks = result.face_landmarks[0]; best_dir = name; best_count = n
        print(f"  {name}: {n} landmarks ✅")
    else: print(f"  {name}: no face")
detector.close()
print(f"BEST: {best_dir} ({best_count} landmarks)")

if not best_landmarks:
    print("ERROR: 所有方向都未检测到面部!")
    sys.exit(1)

# ============================================================
print("\n3. 2D→3D 映射")

# 设置最佳方向相机
d = dirs[best_dir]
cam.location = scan_center + Vector(d) * (sz + 0.5)
cam.rotation_euler = (scan_center - cam.location).to_track_quat('-Z','Z').to_euler()
bpy.context.view_layer.update()

sm = scan_obj.matrix_world
cam_pos = cam.matrix_world.to_translation()
fov = cam.data.angle

# MediaPipe 索引 → 名称映射
# 注意: MediaPipe 的 left/right 是从图像视角定义的（镜像）。
# idx 33 在图像左侧 = 人物的右眼 → 匹配模板 right_eye_outer (在 -X)
# idx 263 在图像右侧 = 人物的左眼 → 匹配模板 left_eye_outer (在 +X)
mp_indices = {
    'nose_tip': 1,
    'right_eye_inner': 133, 'right_eye_outer': 33,
    'left_eye_inner': 362, 'left_eye_outer': 263,
    'right_mouth_corner': 61, 'left_mouth_corner': 291,
    'chin': 199, 'forehead': 10, 'nose_bridge': 6,
    'right_brow': 105, 'left_brow': 334,
}

h = w = 256
lm_3d = {}
for name, idx in mp_indices.items():
    lm = best_landmarks[idx]
    px, py = lm.x*w, lm.y*h
    nx, ny = (px/w)*2-1, 1-(py/h)*2  # flip Y
    ray_cam = Vector((nx*math.tan(fov/2), ny*math.tan(fov/2), -1)).normalized()
    ray_world = (cam.matrix_world.to_3x3() @ ray_cam).normalized()
    origin_local = sm.inverted() @ cam_pos
    dir_local = (sm.inverted().to_3x3() @ ray_world).normalized()
    hit, loc, n, fi = scan_obj.ray_cast(origin_local, dir_local, distance=2.0)
    if not hit: hit, loc, n, fi = scan_obj.ray_cast(origin_local, -dir_local, distance=2.0)
    if hit:
        lm_3d[name] = sm @ loc
        print(f"  {name}: ({lm_3d[name].x:.4f},{lm_3d[name].y:.4f},{lm_3d[name].z:.4f})")
print(f"  面部点映射: {len(lm_3d)}/{len(mp_indices)}")

# ---- 几何特征点：KDTree + 局部极值搜索 ----
print("  计算几何特征点 (KDTree+局部极值)...")

# 构建扫描头 KDTree（采样以加速，297万顶点全建太慢）
scan_n = len(scan_obj.data.vertices)
sample_step = max(1, scan_n // 200000)  # 采样到 ~20万点
kds = KDTree(scan_n // sample_step + 10)
sampled_idx = []
for i in range(0, scan_n, sample_step):
    wp = sm @ scan_obj.data.vertices[i].co
    kds.insert(wp, i)
    sampled_idx.append(i)
kds.balance()
print(f"  KDTree: {len(sampled_idx)} 采样点")

# 获取所有采样点的世界坐标数组
scan_pts = np.array([sm @ scan_obj.data.vertices[i].co for i in sampled_idx])

# 面部基准点（用于定位几何点）
nose = lm_3d.get('nose_tip')
leye = lm_3d.get('left_eye_inner')
reye = lm_3d.get('right_eye_inner')

if nose and leye:
    eye_z = (leye.z + reye.z) / 2 if reye else leye.z  # 眼睛高度
    nose_y = nose.y  # 鼻子 Y (面部最前)
    
    # --- 头顶 (top_of_head): Z 最大区域中心 ---
    z_max = scan_pts[:,2].max()
    top_mask = scan_pts[:,2] > z_max - 0.03  # 顶部 3cm 范围
    if np.any(top_mask):
        top_pts = scan_pts[top_mask]
        # 取中心区域（排除偏离的头发尖）
        top_center = top_pts.mean(axis=0)
        lm_3d['top_of_head'] = Vector((top_center[0], top_center[1], z_max))
        print(f"  top_of_head: ({top_center[0]:.4f},{top_center[1]:.4f},{z_max:.4f})")
    
    # --- 后脑 (back_of_head): Y 最大区域中心 ---
    y_max = scan_pts[:,1].max()
    back_mask = scan_pts[:,1] > y_max - 0.03
    if np.any(back_mask):
        back_pts = scan_pts[back_mask]
        back_center = back_pts.mean(axis=0)
        lm_3d['back_of_head'] = Vector((back_center[0], y_max, back_center[2]))
        print(f"  back_of_head: ({back_center[0]:.4f},{y_max:.4f},{back_center[2]:.4f})")
    
    # --- 后颈 (back_neck): Y 最大 + Z 最小区域 ---
    z_min = scan_pts[:,2].min()
    neck_mask = (scan_pts[:,1] > y_max - 0.06) & (scan_pts[:,2] < z_min + 0.05)
    if np.any(neck_mask):
        neck_pts = scan_pts[neck_mask]
        neck_center = neck_pts.mean(axis=0)
        lm_3d['back_neck'] = Vector((neck_center[0], neck_center[1], neck_center[2]))
        print(f"  back_neck: ({neck_center[0]:.4f},{neck_center[1]:.4f},{neck_center[2]:.4f})")
    
    # --- 耳朵: 在眼角 Z 高度附近, X 极值 ---
    # 左耳 (+X 侧), 右耳 (-X 侧)
    for side, sign, ear_names in [
        ('left', 1, ['left_ear_top', 'left_ear_mid', 'left_ear_bottom']),
        ('right', -1, ['right_ear_top', 'right_ear_mid', 'right_ear_bottom'])
    ]:
        # 耳朵区域: X 在该侧极值, Z 在眼睛高度附近
        ear_mask = (sign * scan_pts[:,0] > sign * scan_pts[:,0].max() * 0.7) & \
                   (np.abs(scan_pts[:,2] - eye_z) < 0.06)
        if np.any(ear_mask):
            ear_pts = scan_pts[ear_mask]
            ear_z_min = ear_pts[:,2].min()
            ear_z_max = ear_pts[:,2].max()
            ear_z_range = ear_z_max - ear_z_min
            # 三个点: top, mid, bottom
            for i, ename in enumerate(ear_names):
                if i == 0:  # top
                    target_z = ear_z_max - ear_z_range * 0.2
                elif i == 1:  # mid
                    target_z = (ear_z_max + ear_z_min) / 2
                else:  # bottom
                    target_z = ear_z_min + ear_z_range * 0.2
                # 找最接近 target_z 且 X 最外侧的点
                z_mask = np.abs(ear_pts[:,2] - target_z) < ear_z_range * 0.2
                if np.any(z_mask):
                    cands = ear_pts[z_mask]
                    # X 最外侧
                    if sign > 0:
                        best = cands[np.argmax(cands[:,0])]
                    else:
                        best = cands[np.argmin(cands[:,0])]
                    lm_3d[ename] = Vector((best[0], best[1], best[2]))
                    print(f"  {ename}: ({best[0]:.4f},{best[1]:.4f},{best[2]:.4f})")

print(f"  总计 3D 特征点: {len(lm_3d)} (面部 {len(mp_indices)} + 几何 {len(lm_3d)-len(mp_indices)})")

# ============================================================
print("\n4. 导入低模模板 + 对齐")

bpy.ops.wm.obj_import(filepath=TEMPLATE)
template_obj = None
for obj in bpy.data.objects:
    if obj.type=='MESH' and obj!=scan_obj: template_obj=obj; break

# 高模和低模朝向一致(Z-up, 面朝-Y), 无需旋转
# 仅居中到原点
tb = bbox_world(template_obj)
template_obj.location -= Vector(tb['center'])
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

tb = bbox_world(template_obj)
print(f"  模板: {len(template_obj.data.vertices)}v, BBox size: {tb['size']}")

# 特征点质心对齐（仅用可靠的面部 MediaPipe 点）
tm = template_obj.matrix_world
t_pts_init = np.array([tm @ v.co for v in template_obj.data.vertices])

face_names = set(mp_indices.keys())
t_idx_face = []; s_pos_face = []
for name, t_idx in template_lm.items():
    if name in lm_3d and name in face_names:
        t_idx_face.append(t_idx); s_pos_face.append(lm_3d[name])

tc_init = np.mean([t_pts_init[i] for i in t_idx_face], axis=0)
sc_init = np.mean([np.array([p.x,p.y,p.z]) for p in s_pos_face], axis=0)
trans = sc_init - tc_init
template_obj.location.x += trans[0]
template_obj.location.y += trans[1]
template_obj.location.z += trans[2]
bpy.context.view_layer.update()
print(f"  质心对齐: trans=({trans[0]:.4f},{trans[1]:.4f},{trans[2]:.4f})")

# 缩放
tb = bbox_world(template_obj)
sr = [sb['size'][i]/tb['size'][i] if tb['size'][i]>1e-6 else 1 for i in range(3)]
us = sum(sr)/3
template_obj.scale = (us,us,us)
bpy.context.view_layer.update()
print(f"  缩放: {sr} → 均匀={us:.4f}")

tm = template_obj.matrix_world; tm_inv = tm.inverted()
tcoords = np.array([tm @ v.co for v in template_obj.data.vertices])

# 完整匹配列表（含几何点，用于验证）
t_idx_list = []; s_pos_list = []
for name, t_idx in template_lm.items():
    if name in lm_3d:
        t_idx_list.append(t_idx); s_pos_list.append(lm_3d[name])

print(f"\n  特征点匹配 ({len(t_idx_list)} pairs):")
for i in range(min(5, len(t_idx_list))):
    tp = tcoords[t_idx_list[i]]; sp = s_pos_list[i]
    print(f"    t=({tp[0]:.4f},{tp[1]:.4f},{tp[2]:.4f}) → s=({sp.x:.4f},{sp.y:.4f},{sp.z:.4f})")

# ============================================================
print("\n5. Shrinkwrap 贴合")
for i in range(4):
    sw = template_obj.modifiers.new("SW",'SHRINKWRAP')
    sw.target = scan_obj
    sw.wrap_method = 'NEAREST_SURFACEPOINT' if i<2 else 'PROJECT'
    sw.wrap_mode = 'ON_SURFACE'
    if sw.wrap_method=='PROJECT':
        sw.use_project_x=sw.use_project_y=sw.use_project_z=True
        sw.use_negative_direction=sw.use_positive_direction=True
    bpy.ops.object.modifier_apply(modifier="SW")
    csm = template_obj.modifiers.new("CS",'CORRECTIVE_SMOOTH')
    csm.iterations=2; csm.smooth_type='SIMPLE'; csm.factor=0.15
    bpy.ops.object.modifier_apply(modifier="CS")
    print(f"  [{i+1}/4]")

# ============================================================
print("\n5b. 特征点锚定（迭代位移+平滑）")
tm = template_obj.matrix_world
tm_inv = tm.inverted()

# 构建邻接表
mesh = template_obj.data
adj = [set() for _ in range(len(mesh.vertices))]
for e in mesh.edges:
    adj[e.vertices[0]].add(e.vertices[1])
    adj[e.vertices[1]].add(e.vertices[0])
adj = [list(s) for s in adj]

# 面部锚点 → 目标局部坐标
anchor_targets = {}
for t_idx, s_pos in zip(t_idx_face, s_pos_face):
    anchor_targets[t_idx] = tm_inv @ s_pos

for iteration in range(20):
    alpha = 0.3 + 0.7 * (iteration / 19)
    for t_idx, target in anchor_targets.items():
        v = mesh.vertices[t_idx]
        v.co = v.co.lerp(target, alpha)
    
    new_co = [None] * len(mesh.vertices)
    for i in range(len(mesh.vertices)):
        if i in anchor_targets:
            new_co[i] = mesh.vertices[i].co.copy()
        else:
            neighbors = adj[i]
            if neighbors:
                avg = Vector((0,0,0))
                for ni in neighbors:
                    avg += mesh.vertices[ni].co
                avg /= len(neighbors)
                new_co[i] = mesh.vertices[i].co.lerp(avg, 0.3)
            else:
                new_co[i] = mesh.vertices[i].co.copy()
    
    for i in range(len(mesh.vertices)):
        mesh.vertices[i].co = new_co[i]
    
    if iteration % 5 == 4:
        max_err = 0
        for t_idx, target in anchor_targets.items():
            err = (mesh.vertices[t_idx].co - target).length
            if err > max_err: max_err = err
        print(f"  [iter {iteration+1}/20] max_anchor_err={max_err*1000:.1f}mm")

mesh.update()
print("  锚定完成")

# 5c. 表面修正
print("\n5c. 表面修正")
sw2 = template_obj.modifiers.new("SW2",'SHRINKWRAP')
sw2.target = scan_obj
sw2.wrap_method = 'NEAREST_SURFACEPOINT'
sw2.wrap_mode = 'ON_SURFACE'
sw2.offset = 0.0
bpy.ops.object.modifier_apply(modifier="SW2")
csm2 = template_obj.modifiers.new("CS2",'CORRECTIVE_SMOOTH')
csm2.iterations=1; csm2.smooth_type='SIMPLE'; csm2.factor=0.1
bpy.ops.object.modifier_apply(modifier="CS2")
for t_idx, target in anchor_targets.items():
    template_obj.data.vertices[t_idx].co = target
template_obj.data.update()
print("  表面修正完成")

# ============================================================
print("\n6. 验证")
tm = template_obj.matrix_world
tcoords_final = np.array([tm @ v.co for v in template_obj.data.vertices])
lm_names = list(template_lm.keys())
for i in range(len(t_idx_list)):
    wp = tcoords_final[t_idx_list[i]]; sp = s_pos_list[i]
    err = np.linalg.norm(wp - np.array([sp.x,sp.y,sp.z]))
    print(f"  {lm_names[i] if i<len(lm_names) else f'pt{i}'}: err={err*1000:.1f}mm")

# 整体表面距离（采样 KDTree）
kdv = KDTree(scan_n // sample_step + 10)
for i in range(0, scan_n, sample_step):
    kdv.insert(sm @ scan_obj.data.vertices[i].co, i)
kdv.balance()
Vf = np.array([tm @ v.co for v in template_obj.data.vertices])
dists = np.array([kdv.find(tuple(Vf[i]))[2] for i in range(len(Vf))])
print(f"  overall: mean={np.mean(dists)*1000:.3f}mm <1mm:{np.sum(dists<0.001)/len(dists)*100:.1f}% <2mm:{np.sum(dists<0.002)/len(dists)*100:.1f}%")

# ============================================================
print("\n7. 保存")
out = os.path.join(OUTPUT_DIR,"head_scan_fit.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print(f"  {out}")

# 同时导出 GLB
template_obj.select_set(True)
bpy.context.view_layer.objects.active = template_obj
glb_out = os.path.join(OUTPUT_DIR, "head_scan_fit.glb")
bpy.ops.export_scene.gltf(filepath=glb_out, use_selection=True, export_format='GLB', export_apply=True)
print(f"  {glb_out}")
print("\n完成!")
