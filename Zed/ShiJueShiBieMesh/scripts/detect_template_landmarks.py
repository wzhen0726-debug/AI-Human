"""
在模板上自动检测面部特征点的顶点索引
渲染模板 → MediaPipe → 2D→3D映射 → 找最近顶点 → 保存索引
"""
import bpy, os, numpy as np, math, cv2
from mathutils import Vector, Matrix

TEMPLATE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"
MODEL_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final\face_landmarker.task"
OUTPUT = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final\template_landmarks.json"

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

# 清空场景
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 导入模板
bpy.ops.wm.obj_import(filepath=TEMPLATE)
template_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH': template_obj = obj; break

# 旋转模板到标准朝向（90° X，面朝 +Y）
rot = Matrix.Rotation(math.radians(90), 3, 'X')
for v in template_obj.data.vertices: v.co = rot @ v.co
template_obj.data.update()

# 渲染设置
bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
bpy.context.scene.render.resolution_x = 512
bpy.context.scene.render.resolution_y = 512

bpy.ops.object.light_add(type='SUN', location=(0,0,10))
bpy.context.active_object.data.energy = 5.0

bpy.ops.object.camera_add()
cam = bpy.context.active_object
bpy.context.scene.camera = cam

# 相机放在正面
vs = [template_obj.matrix_world @ v.co for v in template_obj.data.vertices]
xs=[v.x for v in vs]; ys=[v.y for v in vs]; zs=[v.z for v in vs]
center = Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
sz = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))

# 面朝 +Y，相机从 +Y 方向看
cam.location = center + Vector((0, 1, 0)) * (sz + 0.2)
cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
bpy.context.view_layer.update()

render_path = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final\template_render.png"
bpy.context.scene.render.filepath = render_path
bpy.ops.render.render(write_still=True)
print(f"渲染: {render_path}")

# MediaPipe 检测
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

opt = vision.FaceLandmarkerOptions(
    base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=vision.RunningMode.IMAGE, num_faces=1)
detector = vision.FaceLandmarker.create_from_options(opt)

img = cv2.resize(cv2.imread(render_path), (256,256))
rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
detector.close()

if not result.face_landmarks:
    print("错误: 模板上未检测到面部!")
    raise SystemExit(1)

landmarks = result.face_landmarks[0]
print(f"检测到 {len(landmarks)} 个特征点")

# 2D→3D 映射
w = h = 256
cam_pos = cam.matrix_world.to_translation()
fov = cam.data.angle

# 构建模板顶点 KDTree
from mathutils.kdtree import KDTree as BlKDTree
kd = BlKDTree(len(template_obj.data.vertices))
for i, v in enumerate(template_obj.data.vertices):
    kd.insert(template_obj.matrix_world @ v.co, i)
kd.balance()

# 关键特征点名称和 MediaPipe 索引
key_points = {
    'nose_tip': 1,
    'left_eye_outer': 33, 'right_eye_outer': 263,
    'left_eye_inner': 133, 'right_eye_inner': 362,
    'left_mouth': 61, 'right_mouth': 291,
    'upper_lip': 13, 'lower_lip': 14,
    'chin': 199,
    'nose_bridge': 6,
    'left_eyebrow': 105, 'right_eyebrow': 334,
    'forehead': 10,
}

landmark_data = {}
for name, idx in key_points.items():
    lm = landmarks[idx]
    px, py = lm.x * w, lm.y * h
    nx = (px/w)*2-1; ny = (py/h)*2-1
    ray_cam = Vector((nx*math.tan(fov/2), ny*math.tan(fov/2), -1)).normalized()
    ray_world = (cam.matrix_world.to_3x3() @ ray_cam).normalized()
    
    # raycast 到模板
    origin_local = template_obj.matrix_world.inverted() @ cam_pos
    dir_local = (template_obj.matrix_world.inverted().to_3x3() @ ray_world).normalized()
    hit, loc, n, fi = template_obj.ray_cast(origin_local, dir_local, distance=5.0)
    if not hit:
        hit, loc, n, fi = template_obj.ray_cast(origin_local, -dir_local, distance=5.0)
    
    if hit:
        world_pos = template_obj.matrix_world @ loc
        # 找最近的模板顶点
        co, vert_idx, dist = kd.find(tuple(world_pos))
        landmark_data[name] = {'vertex_index': vert_idx, 'distance_mm': dist*1000}
        print(f"  {name}: vertex={vert_idx}, dist={dist*1000:.2f}mm")

# 保存
import json
with open(OUTPUT, 'w') as f:
    json.dump(landmark_data, f, indent=2)
print(f"\n保存到: {OUTPUT}")
print(f"共 {len(landmark_data)} 个特征点")