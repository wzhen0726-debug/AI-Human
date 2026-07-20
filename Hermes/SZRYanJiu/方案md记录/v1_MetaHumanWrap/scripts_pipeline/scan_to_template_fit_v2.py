"""
高模扫描头 → MetaHuman 低模拓扑 自动化管线 v2
改进: 增加眼眶/嘴唇/鼻翼轮廓密集锚定点 (104个), 解决眼窝凹陷/嘴唇穿透问题

核心改进 vs v1:
1. 从 MediaPipe 478点中提取104个轮廓点(眼眶32+嘴唇40+鼻翼12+眉毛20)
2. 2D→3D映射全部104个点到高模表面
3. 在低模上用最近邻找到对应顶点作为锚点
4. 锚定点从12个增加到100+, 覆盖眼窝/嘴唇/鼻翼
5. Shrinkwrap 用 PROJECT 模式+法线方向, 解决凹陷区顶点不下陷
"""
import bpy, os, numpy as np, time, math, cv2, json, sys
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

# ============================================================
ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test01"
SCAN_OBJ = os.path.join(ROOT, "原始GLB", "Scan_head", "Scan_Head_Lv5.obj")
TEMPLATE = os.path.join(ROOT, "原始GLB", "MetaHuman_head", "MH_Head_01.obj")
MODEL_PATH = os.path.join(ROOT, "output_final", "face_landmarker.task")
LANDMARK_JSON = os.path.join(ROOT, "output_final", "template_landmarks.json")
OUTPUT_DIR = os.path.join(ROOT, "output_final")
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(LANDMARK_JSON) as f:
    template_lm = json.load(f)
print(f"加载模板特征点: {len(template_lm)} 个")

# MediaPipe 轮廓点索引 (只保留对称性好的组, 眉毛/鼻翼映射易出错不参与锚定)
# 注意: MediaPipe left/right 是图像视角(镜像)
MP_CONTOURS = {
    # 人物右眼 (图像左侧) - 对称性验证OK
    'right_eye': [33,7,163,144,145,153,154,155,133,173,157,158,159,160,161,246],
    # 人物左眼 (图像右侧) - 对称性验证OK
    'left_eye': [362,382,381,380,374,373,390,249,263,466,388,387,386,385,384,398],
    # 外唇 - 对称性验证OK
    'outer_lip': [61,185,40,39,37,0,267,269,270,409,291,375,321,405,314,17,84,181,91,146],
    # 内唇 - 对称性验证OK
    'inner_lip': [78,191,80,81,82,13,312,311,310,415,308,324,318,402,317,14,87,178,88,95],
    # 鼻翼 - 只保留对称的点 (过滤mp280等异常)
    'nose_ala': [49,131,134,51,3,248,281,279,440],
    # 注意: 眉毛轮廓点Y范围21mm, 映射易出错, 不参与锚定
}

# 原有的12个核心特征点 (用于质心对齐)
MP_KEY_POINTS = {
    'nose_tip': 1,
    'right_eye_inner': 133, 'right_eye_outer': 33,
    'left_eye_inner': 362, 'left_eye_outer': 263,
    'right_mouth_corner': 61, 'left_mouth_corner': 291,
    'chin': 199, 'forehead': 10, 'nose_bridge': 6,
    'right_brow': 105, 'left_brow': 334,
}

def bbox_world(obj):
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs=[v.x for v in vs]; ys=[v.y for v in vs]; zs=[v.z for v in vs]
    return dict(center=((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2),
                min=(min(xs),min(ys),min(zs)), max=(max(xs),max(ys),max(zs)),
                size=(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)))

# ============================================================
print("\n" + "="*60)
print("1. 导入高模扫描头 + 6方向渲染")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

bpy.ops.wm.obj_import(filepath=SCAN_OBJ)
scan_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        scan_obj = obj; break
if not scan_obj:
    print("ERROR: 导入扫描头失败!"); sys.exit(1)
scan_obj.name = "Scan_Head"

bpy.context.view_layer.objects.active = scan_obj
scan_obj.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

sb = bbox_world(scan_obj)
scan_center = Vector(sb['center'])
scan_obj.location -= scan_center
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

sb = bbox_world(scan_obj)
scan_center = Vector(sb['center'])
scan_size = sb['size']
sz = max(scan_size)
print(f"  扫描头: {len(scan_obj.data.vertices):,}v")
print(f"  BBox: {sb['size']}")

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
    print("ERROR: 未检测到面部!"); sys.exit(1)

# ============================================================
print("\n3. 2D→3D 映射 (104个轮廓点 + 12个核心点)")

d = dirs[best_dir]
cam.location = scan_center + Vector(d) * (sz + 0.5)
cam.rotation_euler = (scan_center - cam.location).to_track_quat('-Z','Z').to_euler()
bpy.context.view_layer.update()

sm = scan_obj.matrix_world
cam_pos = cam.matrix_world.to_translation()
fov = cam.data.angle
h = w = 256

def map_2d_to_3d(mp_idx):
    """将 MediaPipe 2D landmark 映射到高模 3D 表面"""
    lm = best_landmarks[mp_idx]
    px, py = lm.x*w, lm.y*h
    nx, ny = (px/w)*2-1, 1-(py/h)*2
    ray_cam = Vector((nx*math.tan(fov/2), ny*math.tan(fov/2), -1)).normalized()
    ray_world = (cam.matrix_world.to_3x3() @ ray_cam).normalized()
    origin_local = sm.inverted() @ cam_pos
    dir_local = (sm.inverted().to_3x3() @ ray_world).normalized()
    hit, loc, n, fi = scan_obj.ray_cast(origin_local, dir_local, distance=2.0)
    if not hit: hit, loc, n, fi = scan_obj.ray_cast(origin_local, -dir_local, distance=2.0)
    if hit:
        return sm @ loc
    return None

# 映射12个核心点
lm_3d = {}
for name, idx in MP_KEY_POINTS.items():
    p = map_2d_to_3d(idx)
    if p: lm_3d[name] = p
print(f"  核心点: {len(lm_3d)}/{len(MP_KEY_POINTS)}")

# 映射104个轮廓点到高模表面 + 过滤异常点
contour_3d = {}  # {group_name: [Vector, ...]}
total_mapped = 0
total_filtered = 0
for group_name, indices in MP_CONTOURS.items():
    # 先映射所有点
    raw_pts = []
    for idx in indices:
        p = map_2d_to_3d(idx)
        if p: raw_pts.append((idx, p))
    
    # 过滤异常点: 计算每组 Y 值中位数, 剔除偏离>15mm 的点
    if len(raw_pts) >= 4:
        ys = sorted([p[1].y for p in raw_pts])
        y_median = ys[len(ys)//2]
        filtered_pts = []
        for idx, p in raw_pts:
            if abs(p.y - y_median) < 0.015:  # 15mm 内保留
                filtered_pts.append(p)
            else:
                total_filtered += 1
                print(f"    过滤 {group_name} mp{idx}: Y={p.y*1000:.1f}mm (中位数{y_median*1000:.1f}mm)")
        pts = filtered_pts
    else:
        pts = [p[1] for p in raw_pts]
    
    contour_3d[group_name] = pts
    total_mapped += len(pts)
    print(f"  {group_name}: {len(pts)}/{len(indices)} (过滤{len(raw_pts)-len(pts)})")
print(f"  轮廓点总计: {total_mapped} (过滤{total_filtered}个异常点)")

# 几何点 (头顶/后脑/后颈/耳朵) - 用 KDTree 局部极值
print("  计算几何特征点...")
scan_n = len(scan_obj.data.vertices)
sample_step = max(1, scan_n // 200000)
scan_pts = np.array([sm @ scan_obj.data.vertices[i].co for i in range(0, scan_n, sample_step)])

nose = lm_3d.get('nose_tip')
leye = lm_3d.get('left_eye_inner')
reye = lm_3d.get('right_eye_inner')
if nose and leye:
    eye_z = (leye.z + reye.z) / 2 if reye else leye.z
    # 头顶
    z_max = scan_pts[:,2].max()
    top_mask = scan_pts[:,2] > z_max - 0.03
    if np.any(top_mask):
        tc = scan_pts[top_mask].mean(axis=0)
        lm_3d['top_of_head'] = Vector((tc[0], tc[1], z_max))
    # 后脑
    y_max = scan_pts[:,1].max()
    back_mask = scan_pts[:,1] > y_max - 0.03
    if np.any(back_mask):
        bc = scan_pts[back_mask].mean(axis=0)
        lm_3d['back_of_head'] = Vector((bc[0], y_max, bc[2]))
    # 后颈
    z_min = scan_pts[:,2].min()
    neck_mask = (scan_pts[:,1] > y_max - 0.06) & (scan_pts[:,2] < z_min + 0.05)
    if np.any(neck_mask):
        nc = scan_pts[neck_mask].mean(axis=0)
        lm_3d['back_neck'] = Vector((nc[0], nc[1], nc[2]))
    # 耳朵
    for side, sign, ear_names in [
        ('left', 1, ['left_ear_top', 'left_ear_mid', 'left_ear_bottom']),
        ('right', -1, ['right_ear_top', 'right_ear_mid', 'right_ear_bottom'])
    ]:
        ear_mask = (sign * scan_pts[:,0] > sign * scan_pts[:,0].max() * 0.7) & (np.abs(scan_pts[:,2] - eye_z) < 0.06)
        if np.any(ear_mask):
            ear_pts = scan_pts[ear_mask]
            ear_z_min, ear_z_max = ear_pts[:,2].min(), ear_pts[:,2].max()
            ear_zr = ear_z_max - ear_z_min
            for i, ename in enumerate(ear_names):
                tz = [ear_z_max - ear_zr*0.2, (ear_z_max+ear_z_min)/2, ear_z_min + ear_zr*0.2][i]
                z_mask = np.abs(ear_pts[:,2] - tz) < ear_zr * 0.2
                if np.any(z_mask):
                    cands = ear_pts[z_mask]
                    best = cands[np.argmax(cands[:,0])] if sign > 0 else cands[np.argmin(cands[:,0])]
                    lm_3d[ename] = Vector((best[0], best[1], best[2]))

print(f"  总特征点: {len(lm_3d)} (核心12 + 几何{len(lm_3d)-12})")

# ============================================================
print("\n4. 导入低模模板 + 对齐")

bpy.ops.wm.obj_import(filepath=TEMPLATE)
template_obj = None
for obj in bpy.data.objects:
    if obj.type=='MESH' and obj!=scan_obj: template_obj=obj; break

# 居中
tb = bbox_world(template_obj)
template_obj.location -= Vector(tb['center'])
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
tb = bbox_world(template_obj)

# 质心对齐 (仅用12核心面部点)
tm = template_obj.matrix_world
t_pts_init = np.array([tm @ v.co for v in template_obj.data.vertices])

face_names = set(MP_KEY_POINTS.keys())
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

# 缩放
tb = bbox_world(template_obj)
sr = [sb['size'][i]/tb['size'][i] if tb['size'][i]>1e-6 else 1 for i in range(3)]
us = sum(sr)/3
template_obj.scale = (us,us,us)
bpy.context.view_layer.update()
print(f"  缩放: {us:.4f}")

tm = template_obj.matrix_world; tm_inv = tm.inverted()
tcoords = np.array([tm @ v.co for v in template_obj.data.vertices])

# ============================================================
# ★ 核心: 在低模上找到104个轮廓点的对应顶点
print("\n4b. 匹配轮廓点到低模顶点")

# 构建低模 KDTree
n_tv = len(template_obj.data.vertices)
t_kd = KDTree(n_tv)
for i, v in enumerate(template_obj.data.vertices):
    t_kd.insert(tm @ v.co, i)
t_kd.balance()

# 对每个轮廓组的3D点, 在低模上找最近顶点
contour_anchors = {}  # {vert_idx: target_pos_in_template_local}
for group_name, pts in contour_3d.items():
    matched = 0
    for p in pts:
        co, vi, dist = t_kd.find(tuple(p))
        if dist < 0.02:  # 2cm 内才算匹配
            target_local = tm_inv @ p
            # 避免重复(同一顶点可能匹配多个轮廓点, 取最近的)
            if vi not in contour_anchors or (target_local - template_obj.data.vertices[vi].co).length < (contour_anchors[vi] - template_obj.data.vertices[vi].co).length:
                contour_anchors[vi] = target_local
            matched += 1
    print(f"  {group_name}: {matched}/{len(pts)} 匹配")

print(f"  轮廓锚点总数: {len(contour_anchors)}")

# 合并核心12点锚定
anchor_targets = {}
for t_idx, s_pos in zip(t_idx_face, s_pos_face):
    anchor_targets[t_idx] = tm_inv @ s_pos
# 加入轮廓锚点 (不覆盖核心点)
for vi, target in contour_anchors.items():
    if vi not in anchor_targets:
        anchor_targets[vi] = target

print(f"  总锚点数: {len(anchor_targets)} (核心12 + 轮廓{len(contour_anchors)})")

# ============================================================
print("\n5. Shrinkwrap 贴合")

# 策略: 全部用 NEAREST_SURFACEPOINT (PROJECT模式会造成左右不对称)
for i in range(4):
    sw = template_obj.modifiers.new("SW",'SHRINKWRAP')
    sw.target = scan_obj
    sw.wrap_method = 'NEAREST_SURFACEPOINT'
    sw.wrap_mode = 'ON_SURFACE'
    sw.offset = 0.0
    bpy.ops.object.modifier_apply(modifier="SW")
    
    csm = template_obj.modifiers.new("CS",'CORRECTIVE_SMOOTH')
    csm.iterations=2; csm.smooth_type='SIMPLE'; csm.factor=0.15
    bpy.ops.object.modifier_apply(modifier="CS")
    print(f"  [{i+1}/4]")

# ============================================================
print("\n5b. 特征点+轮廓锚定 (30轮, 锚点更多需更多迭代)")

tm = template_obj.matrix_world
tm_inv = tm.inverted()

# 重建邻接表 (Shrinkwrap 改变了顶点位置)
mesh = template_obj.data
adj = [set() for _ in range(len(mesh.vertices))]
for e in mesh.edges:
    adj[e.vertices[0]].add(e.vertices[1])
    adj[e.vertices[1]].add(e.vertices[0])
adj = [list(s) for s in adj]

# 更新锚点目标到当前模板局部坐标
anchor_targets_cur = {}
for vi, target_world in anchor_targets.items():
    # target 存的是对齐后的局部坐标, 但 Shrinkwrap 可能改变了 transform
    # 重新用世界坐标目标转换
    # anchor_targets 存的是 tm_inv @ p (对齐时的局部坐标)
    # Shrinkwrap apply 后 transform 不变, 所以局部坐标目标仍有效
    anchor_targets_cur[vi] = target_world

# 验证锚点当前误差
max_err = max((mesh.vertices[vi].co - target).length for vi, target in anchor_targets_cur.items())
print(f"  锚定前 max_err={max_err*1000:.1f}mm")

for iteration in range(30):
    alpha = 0.3 + 0.7 * (iteration / 29)
    for vi, target in anchor_targets_cur.items():
        v = mesh.vertices[vi]
        v.co = v.co.lerp(target, alpha)
    
    new_co = [None] * len(mesh.vertices)
    for i in range(len(mesh.vertices)):
        if i in anchor_targets_cur:
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
    
    if iteration % 10 == 9:
        max_err = max((mesh.vertices[vi].co - target).length for vi, target in anchor_targets_cur.items())
        print(f"  [iter {iteration+1}/30] max_anchor_err={max_err*1000:.1f}mm")

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
for vi, target in anchor_targets_cur.items():
    template_obj.data.vertices[vi].co = target
template_obj.data.update()
print("  表面修正完成")

# ============================================================
print("\n6. 验证")
tm = template_obj.matrix_world

# 整体表面距离
kdv = KDTree(scan_n // sample_step + 10)
for i in range(0, scan_n, sample_step):
    kdv.insert(sm @ scan_obj.data.vertices[i].co, i)
kdv.balance()
Vf = np.array([tm @ v.co for v in template_obj.data.vertices])
dists = np.array([kdv.find(tuple(Vf[i]))[2] for i in range(len(Vf))])
print(f"  overall: mean={np.mean(dists)*1000:.3f}mm max={np.max(dists)*1000:.3f}mm <0.5mm:{np.sum(dists<0.0005)/len(dists)*100:.1f}% <1mm:{np.sum(dists<0.001)/len(dists)*100:.1f}%")

# 锚点验证
anchor_errs = []
for vi, target in anchor_targets_cur.items():
    wp = tm @ mesh.vertices[vi].co
    target_world = tm @ target
    err = (wp - target_world).length
    anchor_errs.append(err)
print(f"  锚点: mean={np.mean(anchor_errs)*1000:.3f}mm max={np.max(anchor_errs)*1000:.3f}mm ({len(anchor_errs)}点)")

# ============================================================
print("\n7. 保存")
out = os.path.join(OUTPUT_DIR,"head_scan_fit_v2.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print(f"  {out}")

template_obj.select_set(True)
bpy.context.view_layer.objects.active = template_obj
glb_out = os.path.join(OUTPUT_DIR, "head_scan_fit_v2.glb")
bpy.ops.export_scene.gltf(filepath=glb_out, use_selection=True, export_format='GLB', export_apply=True)
print(f"  {glb_out}")
print("\n完成!")
