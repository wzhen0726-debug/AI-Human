"""
MediaPipe + 固定模板特征点 → MetaHuman 式包裹 - 最终版
"""
import bpy, os, numpy as np, time, math, cv2, json
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final"
BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"
MODEL_PATH = os.path.join(OUTPUT_DIR, "face_landmarker.task")
LANDMARK_JSON = os.path.join(OUTPUT_DIR, "template_landmarks.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 加载模板固定特征点
with open(LANDMARK_JSON) as f:
    template_lm = json.load(f)
print(f"加载模板特征点: {len(template_lm)} 个")

def bbox_world(obj):
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs=[v.x for v in vs]; ys=[v.y for v in vs]; zs=[v.z for v in vs]
    return dict(center=((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2),
                size=(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)))

# ============================================================
print("1. 加载场景 + 渲染")
bpy.ops.wm.open_mainfile(filepath=BLEND)
scan_obj = bpy.data.objects.get("Scan_Head")
for obj in list(bpy.data.objects):
    if obj.type=='MESH' and obj!=scan_obj: bpy.data.objects.remove(obj, do_unlink=True)

sb = bbox_world(scan_obj)
scan_center = Vector(sb['center'])
scan_size = sb['size']
sz = max(scan_size)

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
    p = os.path.join(OUTPUT_DIR, f"mp_{name}.png")
    bpy.context.scene.render.filepath = p
    bpy.ops.render.render(write_still=True)
    render_paths[name] = p

# ============================================================
print("2. MediaPipe")
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
        print(f"  {name}: {n} landmarks")
    else: print(f"  {name}: no face")
detector.close()
print(f"BEST: {best_dir} ({best_count} landmarks)")

# ============================================================
print("3. 2D→3D 映射")

d = dirs[best_dir]
cam.location = scan_center + Vector(d) * (sz + 0.5)
cam.rotation_euler = (scan_center - cam.location).to_track_quat('-Z','Z').to_euler()
bpy.context.view_layer.update()

sm = scan_obj.matrix_world
cam_pos = cam.matrix_world.to_translation()
fov = cam.data.angle

# MediaPipe 索引 → 名称映射
# 注意: MediaPipe 的 left/right 是从图像视角定义的（镜像）。
# idx 33 在图像左侧 = 人物的右眼，应匹配模板的 right_eye_outer（在 -X）。
# idx 263 在图像右侧 = 人物的左眼，应匹配模板的 left_eye_outer（在 +X）。
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
    nx, ny = (px/w)*2-1, 1-(py/h)*2  # flip Y: image top → camera +Y
    ray_cam = Vector((nx*math.tan(fov/2), ny*math.tan(fov/2), -1)).normalized()
    ray_world = (cam.matrix_world.to_3x3() @ ray_cam).normalized()
    origin_local = sm.inverted() @ cam_pos
    dir_local = (sm.inverted().to_3x3() @ ray_world).normalized()
    hit, loc, n, fi = scan_obj.ray_cast(origin_local, dir_local, distance=2.0)
    if not hit: hit, loc, n, fi = scan_obj.ray_cast(origin_local, -dir_local, distance=2.0)
    if hit:
        lm_3d[name] = sm @ loc
        print(f"  {name}: ({lm_3d[name].x:.4f},{lm_3d[name].y:.4f},{lm_3d[name].z:.4f})")
print(f"  mapped {len(lm_3d)}/{len(mp_indices)} to 3D")

# ---- 非面部特征点：几何估算 ----
# 耳朵: 模板 left_ear 在 +X，right_ear 在 -X
# 耳朵在头部中段偏后，不在眼睛 Y 位置（眼睛太靠前）
if 'left_eye_inner' in lm_3d and 'nose_tip' in lm_3d:
    eye_y = lm_3d['left_eye_inner'].y
    eye_z = lm_3d['left_eye_inner'].z
    nose_y = lm_3d['nose_tip'].y
    # 耳朵大约在眼睛和后脑中间的 Y 位置
    # 用眼睛 Y + (后脑方向偏移) 来估算
    ear_y = eye_y + 0.06  # 向后偏移 6cm（经验值）
    
    # 左耳 (+X 侧): 从 +X 外部向 -X 射
    for offset_z, name in [(0.02, 'left_ear_top'), (0.0, 'left_ear_mid'), (-0.02, 'left_ear_bottom')]:
        origin = Vector((0.3, ear_y, eye_z + offset_z))
        dir_vec = Vector((-1, 0, 0))
        hit, loc, n, fi = scan_obj.ray_cast(sm.inverted() @ origin, (sm.inverted().to_3x3()@dir_vec).normalized(), distance=2.0)
        if hit: lm_3d[name] = sm @ loc
    # 右耳 (-X 侧): 从 -X 外部向 +X 射
    for offset_z, name in [(0.02, 'right_ear_top'), (0.0, 'right_ear_mid'), (-0.02, 'right_ear_bottom')]:
        origin = Vector((-0.3, ear_y, eye_z + offset_z))
        dir_vec = Vector((1, 0, 0))
        hit, loc, n, fi = scan_obj.ray_cast(sm.inverted() @ origin, (sm.inverted().to_3x3()@dir_vec).normalized(), distance=2.0)
        if hit: lm_3d[name] = sm @ loc

# 后脑: 从 +Y 外部向 -Y 射（Z 用眼睛高度而非鼻子高度，鼻子太低）
if 'left_eye_inner' in lm_3d:
    eye_z = lm_3d['left_eye_inner'].z
    origin = Vector((0, 0.3, eye_z))
    dir_vec = Vector((0, -1, 0))
    hit, loc, n, fi = scan_obj.ray_cast(sm.inverted() @ origin, (sm.inverted().to_3x3()@dir_vec).normalized(), distance=2.0)
    if hit: lm_3d['back_of_head'] = sm @ loc

# 头顶: +Z 方向
origin = Vector((0, 0, 3.0))
dir_vec = Vector((0, 0, -1))
hit, loc, n, fi = scan_obj.ray_cast(sm.inverted() @ origin, (sm.inverted().to_3x3()@dir_vec).normalized(), distance=5.0)
if hit: lm_3d['top_of_head'] = sm @ loc

# 后颈: 底部 +Y
scan_z_min = scan_center.z - scan_size[2]/2
origin = Vector((0, 0.3, scan_z_min))
dir_vec = Vector((0, -1, 0))
hit, loc, n, fi = scan_obj.ray_cast(sm.inverted() @ origin, (sm.inverted().to_3x3()@dir_vec).normalized(), distance=2.0)
if hit: lm_3d['back_neck'] = sm @ loc

print(f"  总计 3D 特征点: {len(lm_3d)} (面部 {len(mp_indices)} + 几何 {len(lm_3d)-len(mp_indices)})")

# ============================================================
print("4. 导入模板 + 旋转")

bpy.ops.wm.obj_import(filepath=TEMPLATE)
template_obj = None
for obj in bpy.data.objects:
    if obj.type=='MESH' and obj!=scan_obj: template_obj=obj; break

# 旋转（只做90°X，不做180°Z——避免左右翻转）
for v in template_obj.data.vertices: v.co = Matrix.Rotation(scan_obj.rotation_euler[0],3,'X') @ v.co
template_obj.data.update()

# 特征点质心对齐（仅用可靠的面部 MediaPipe 点，不用几何估算的耳朵/后脑等）
tm = template_obj.matrix_world
t_pts_init = np.array([tm @ v.co for v in template_obj.data.vertices])

# 仅用面部点做对齐
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

# 完整匹配列表（包含几何点，用于后续验证）
t_idx_list = []; s_pos_list = []
for name, t_idx in template_lm.items():
    if name in lm_3d:
        t_idx_list.append(t_idx); s_pos_list.append(lm_3d[name])

# 缩放
tb = bbox_world(template_obj)
sr = [sb['size'][i]/tb['size'][i] if tb['size'][i]>1e-6 else 1 for i in range(3)]
us = sum(sr)/3
template_obj.scale = (us,us,us)
bpy.context.view_layer.update()

tm = template_obj.matrix_world; tm_inv = tm.inverted()
tcoords = np.array([tm @ v.co for v in template_obj.data.vertices])

# 特征点匹配验证
print(f"\n  特征点匹配 ({len(t_idx_list)} pairs):")
for i in range(min(5, len(t_idx_list))):
    tp = tcoords[t_idx_list[i]]; sp = s_pos_list[i]
    print(f"    t=({tp[0]:.4f},{tp[1]:.4f},{tp[2]:.4f}) → s=({sp.x:.4f},{sp.y:.4f},{sp.z:.4f})")

# ============================================================
print("\n5. Shrinkwrap 贴合（无锚定，自然贴合）")
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
# 迭代：把面部特征点拉向目标，同时平滑邻域避免撕裂
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
    # 1. 把锚点直接设到目标（带阻尼）
    alpha = 0.3 + 0.7 * (iteration / 19)  # 渐进增加
    for t_idx, target in anchor_targets.items():
        v = mesh.vertices[t_idx]
        v.co = v.co.lerp(target, alpha)
    
    # 2. 平滑锚点邻域（拉普拉斯平滑，仅非锚点）
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
        # 检查锚点误差
        max_err = 0
        for t_idx, target in anchor_targets.items():
            err = (mesh.vertices[t_idx].co - target).length
            if err > max_err: max_err = err
        print(f"  [iter {iteration+1}/20] max_anchor_err={max_err*1000:.1f}mm")

mesh.update()
print("  锚定完成")

# 5c. 轻量 Shrinkwrap 修正表面（不在锚点区域）
print("\n5c. 表面修正")
sw2 = template_obj.modifiers.new("SW2",'SHRINKWRAP')
sw2.target = scan_obj
sw2.wrap_method = 'NEAREST_SURFACEPOINT'
sw2.wrap_mode = 'ON_SURFACE'
sw2.offset = 0.0
bpy.ops.object.modifier_apply(modifier="SW2")
# 再平滑一次
csm2 = template_obj.modifiers.new("CS2",'CORRECTIVE_SMOOTH')
csm2.iterations=1; csm2.smooth_type='SIMPLE'; csm2.factor=0.1
bpy.ops.object.modifier_apply(modifier="CS2")
# 重新锚定（Shrinkwrap 会把锚点移走，再拉回来）
for t_idx, target in anchor_targets.items():
    template_obj.data.vertices[t_idx].co = target
template_obj.data.update()
print("  表面修正完成")

# ============================================================
print("\n6. 验证")
tm = template_obj.matrix_world
tcoords_final = np.array([tm @ v.co for v in template_obj.data.vertices])
for i in range(len(t_idx_list)):
    wp = tcoords_final[t_idx_list[i]]; sp = s_pos_list[i]
    err = np.linalg.norm(wp - np.array([sp.x,sp.y,sp.z]))
    print(f"  {list(template_lm.keys())[i]}: err={err*1000:.1f}mm")

scan_n = len(scan_obj.data.vertices)
vs = max(1,scan_n//500000)
kdv = KDTree(scan_n//vs+1)
for i in range(0,scan_n,vs): kdv.insert(sm@scan_obj.data.vertices[i].co,i)
kdv.balance()
Vf = np.array([tm@v.co for v in template_obj.data.vertices])
dists = np.array([kdv.find(tuple(Vf[i]))[2] for i in range(len(Vf))])
print(f"  overall: mean={np.mean(dists)*1000:.3f}mm <1mm:{np.sum(dists<0.001)/len(dists)*100:.1f}%")

# ============================================================
print("\n7. 保存")
out = os.path.join(OUTPUT_DIR,"head_mp_final.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print(f"  {out}")