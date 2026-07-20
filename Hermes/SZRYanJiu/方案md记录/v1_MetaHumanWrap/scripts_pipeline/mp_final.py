"""
MediaPipe 面部特征点 + MetaHuman 式包裹 - 完整版
"""
import bpy, os, numpy as np, time, math,cv2
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final"
BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"
MODEL_PATH = os.path.join(OUTPUT_DIR, "face_landmarker.task")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def bbox_world(obj):
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs=[v.x for v in vs]; ys=[v.y for v in vs]; zs=[v.z for v in vs]
    return dict(center=((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2),
                size=(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)))

# ============================================================
print("1. 加载场景")
bpy.ops.wm.open_mainfile(filepath=BLEND)
scan_obj = bpy.data.objects.get("Scan_Head")
for obj in list(bpy.data.objects):
    if obj.type=='MESH' and obj!=scan_obj: bpy.data.objects.remove(obj, do_unlink=True)

sb = bbox_world(scan_obj)
scan_center = Vector(sb['center'])
scan_size = sb['size']
print(f"扫描: center={scan_center}, size={scan_size}")

# ============================================================
print("\n2. 6方向渲染 + MediaPipe 检测")

bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
bpy.context.scene.render.resolution_x = 512
bpy.context.scene.render.resolution_y = 512

# 灯光
bpy.ops.object.light_add(type='SUN', location=(0,0,10))
bpy.context.active_object.data.energy = 5.0

# 相机
bpy.ops.object.camera_add()
cam = bpy.context.active_object
bpy.context.scene.camera = cam

sz = max(scan_size)
dirs = {'+Y':(0,1,0), '-Y':(0,-1,0), '+X':(1,0,0), '-X':(-1,0,0), '+Z':(0,0,1), '-Z':(0,0,-1)}

render_paths = {}
for name, d in dirs.items():
    cam.location = scan_center + Vector(d) * (sz + 0.5)
    cam.rotation_euler = (scan_center - cam.location).to_track_quat('-Z','Y').to_euler()
    bpy.context.view_layer.update()
    p = os.path.join(OUTPUT_DIR, f"mp_{name}.png")
    bpy.context.scene.render.filepath = p
    bpy.ops.render.render(write_still=True)
    render_paths[name] = p
    print(f"  render {name}")

# MediaPipe
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
        print(f"  {name}: {n} landmarks ✅")
        if n > best_count:
            best_landmarks = result.face_landmarks[0]; best_dir = name; best_count = n
    else:
        print(f"  {name}: no face")
detector.close()

if not best_landmarks:
    print("ERROR: no face detected in any direction!")
    raise SystemExit(1)
print(f"BEST: {best_dir} ({best_count} landmarks)")

# 2D landmarks
h = w = 256
lm_2d = {}
key_idx = {'nose_tip':1, 'left_eye':33, 'right_eye':263,
           'left_mouth':61, 'right_mouth':291, 'chin':199,
           'forehead':10, 'nose_bridge':6}
for name, idx in key_idx.items():
    lm = best_landmarks[idx]
    lm_2d[name] = (lm.x*w, lm.y*h)

# ============================================================
print("\n3. 2D → 3D 映射")

# 设置最佳方向相机
d = dirs[best_dir]
cam.location = scan_center + Vector(d) * (sz + 0.5)
cam.rotation_euler = (scan_center - cam.location).to_track_quat('-Z','Y').to_euler()
bpy.context.view_layer.update()

sm = scan_obj.matrix_world
cam_pos = cam.matrix_world.to_translation()
fov = cam.data.angle

lm_3d = {}
for name, (px, py) in lm_2d.items():
    try:
        nx = (px/w)*2 - 1; ny = (py/h)*2 - 1
        ray_cam = Vector((nx * math.tan(fov/2), ny * math.tan(fov/2), -1)).normalized()
        ray_world = (cam.matrix_world.to_3x3() @ ray_cam).normalized()
        origin_local = sm.inverted() @ cam_pos
        dir_local = (sm.inverted().to_3x3() @ ray_world).normalized()
        
        hit, loc, n, fi = scan_obj.ray_cast(origin_local, dir_local, distance=2.0)
        if not hit:
            hit, loc, n, fi = scan_obj.ray_cast(origin_local, -dir_local, distance=2.0)
        if hit:
            lm_3d[name] = sm @ loc
            print(f"  {name}: ({lm_3d[name].x:.4f},{lm_3d[name].y:.4f},{lm_3d[name].z:.4f})")
        else:
            print(f"  {name}: raycast MISS")
    except Exception as e:
        print(f"  {name}: ERROR - {e}")
print(f"  mapped {len(lm_3d)}/{len(lm_2d)} to 3D")

# ============================================================
print("\n4. 导入模板 + 检测特征点")

bpy.ops.wm.obj_import(filepath=TEMPLATE)
template_obj = None
for obj in bpy.data.objects:
    if obj.type=='MESH' and obj!=scan_obj: template_obj=obj; break

# 旋转模板匹配扫描: 90°X + 180°Z（翻面）
rot = Matrix.Rotation(scan_obj.rotation_euler[0], 3, 'X')
for v in template_obj.data.vertices: v.co = rot @ v.co
rot_z = Matrix.Rotation(math.radians(180), 3, 'Z')
for v in template_obj.data.vertices: v.co = rot_z @ v.co
template_obj.data.update()
tm = template_obj.matrix_world

# 先检测模板特征点
print("  detecting template features...")
tcoords = np.array([tm @ v.co for v in template_obj.data.vertices])
y_min, y_max = tcoords[:,1].min(), tcoords[:,1].max()
z_min, z_max = tcoords[:,2].min(), tcoords[:,2].max()
yr = y_max-y_min; zr = z_max-z_min

t_features = {}
try:
    # 鼻尖
    fwd = tcoords[tcoords[:,2] > z_min+0.7*zr]
    if len(fwd)>0:
        ni = np.argmax(fwd[:,2])
        t_features['nose_tip'] = np.where(np.all(np.abs(tcoords-fwd[ni])<0.001,axis=1))[0][0]

    # 眼角
    eye_lo = y_min+0.55*yr; eye_hi = y_min+0.75*yr
    em = (tcoords[:,1]>eye_lo)&(tcoords[:,1]<eye_hi)&(tcoords[:,2]>z_min+0.5*zr)
    for side,s in [('left_eye',-1),('right_eye',1)]:
        m = em & (s*tcoords[:,0]>0.01)
        if np.any(m): idx = np.where(m)[0]; t_features[side] = idx[np.argmin(tcoords[idx,2])]

    # 嘴角
    my = y_min+0.32*yr
    mm = (np.abs(tcoords[:,1]-my)<0.04*yr)&(tcoords[:,2]>z_min+0.5*zr)
    for side,s in [('left_mouth',-1),('right_mouth',1)]:
        m = mm & (s*tcoords[:,0]>0.005)
        if np.any(m): idx = np.where(m)[0]; t_features[side] = idx[np.argmax(s*tcoords[idx,0])]

    # 下巴
    cm = tcoords[:,1] < y_min+0.1*yr
    if np.any(cm): idx = np.where(cm)[0]; t_features['chin'] = idx[np.argmin(tcoords[idx,1])]

    # 眉心
    br = (np.abs(tcoords[:,1]-(y_min+0.68*yr))<0.03*yr)&(np.abs(tcoords[:,0])<0.005)
    if np.any(br): idx = np.where(br)[0]; t_features['nose_bridge'] = idx[np.argmax(tcoords[idx,2])]

    # 额头
    fh = (tcoords[:,1]>y_min+0.85*yr)&(np.abs(tcoords[:,0])<0.005)
    if np.any(fh): idx = np.where(fh)[0]; t_features['forehead'] = idx[np.argmax(tcoords[idx,2])]
except Exception as e:
    print(f"  feature detection ERROR: {e}")

print(f"  template features: {len(t_features)}")

# 对齐：平移使特征点质心匹配
t_pts_init = np.array([tm @ v.co for v in template_obj.data.vertices])
tc_init = np.mean([t_pts_init[ti] for name,ti in t_features.items() if name in lm_3d], axis=0) if any(name in lm_3d for name in t_features) else np.mean(t_pts_init, axis=0)
sc_init = np.mean([np.array([lm_3d[name].x, lm_3d[name].y, lm_3d[name].z]) for name in t_features if name in lm_3d], axis=0) if any(name in lm_3d for name in t_features) else np.array(sb['center'])
trans_init = sc_init - tc_init
print(f"  feature centroid: t={tc_init} → s={sc_init}, trans={trans_init}")
template_obj.location.x += trans_init[0]; template_obj.location.y += trans_init[1]; template_obj.location.z += trans_init[2]
bpy.context.view_layer.update()
print(f"  after alignment: location={list(template_obj.location)}")

# 均匀缩放
tb = bbox_world(template_obj)
sr = [sb['size'][i]/tb['size'][i] if tb['size'][i]>1e-6 else 1 for i in range(3)]
us = sum(sr)/3
template_obj.scale = (us, us, us)
bpy.context.view_layer.update()

tm = template_obj.matrix_world; tm_inv = tm.inverted()

# 匹配特征点对
pairs = []
for name, ti in t_features.items():
    if name in lm_3d:
        tp = tcoords[ti]; sp = lm_3d[name]
        pairs.append((ti, sp, name))
        print(f"  {name}: t=({tp[0]:.4f},{tp[1]:.4f},{tp[2]:.4f}) → s=({sp.x:.4f},{sp.y:.4f},{sp.z:.4f})")

# ============================================================
print(f"\n5. 特征点约束贴合 ({len(pairs)} pairs)")

t_pts = np.array([tcoords[p[0]] for p in pairs])
s_pts = np.array([[p[1].x,p[1].y,p[1].z] for p in pairs])
tc, sc = t_pts.mean(axis=0), s_pts.mean(axis=0)
lm_scale = np.sum(np.linalg.norm(s_pts-sc,axis=1)) / max(np.sum(np.linalg.norm(t_pts-tc,axis=1)),1e-6)

template_obj.scale = (us*lm_scale, us*lm_scale, us*lm_scale)
bpy.context.view_layer.update()
tm = template_obj.matrix_world; tm_inv = tm.inverted()

tcoords2 = np.array([tm @ v.co for v in template_obj.data.vertices])
tc2 = np.mean([tcoords2[p[0]] for p in pairs], axis=0)
trans = sc - tc2
template_obj.location.x += trans[0]; template_obj.location.y += trans[1]; template_obj.location.z += trans[2]
bpy.context.view_layer.update()

# Shrinkwrap
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

# ============================================================
print("\n6. 验证")
tm = template_obj.matrix_world
for name, ti in t_features.items():
    if name in lm_3d:
        wp = tm @ template_obj.data.vertices[ti].co
        err = (wp - lm_3d[name]).length
        print(f"  {name}: err={err*1000:.1f}mm")

# 总体精度
scan_n = len(scan_obj.data.vertices)
vs = max(1,scan_n//500000)
kdv = KDTree(scan_n//vs+1)
for i in range(0,scan_n,vs): kdv.insert(sm @ scan_obj.data.vertices[i].co,i)
kdv.balance()
Vf = np.array([tm @ v.co for v in template_obj.data.vertices])
dists = np.array([kdv.find(tuple(Vf[i]))[2] for i in range(len(Vf))])
print(f"  overall: mean={np.mean(dists)*1000:.3f}mm <1mm:{np.sum(dists<0.001)/len(dists)*100:.1f}%")

# ============================================================
print("\n7. 保存")
out = os.path.join(OUTPUT_DIR,"head_mp.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print(f"  {out}")