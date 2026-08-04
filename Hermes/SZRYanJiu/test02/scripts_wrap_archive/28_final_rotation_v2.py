import bpy, os, sys, math
from mathutils import Vector, Matrix

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
GLB_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\AI生成高模\02_tripoTpose\raw_model.glb"
OUT_BLEND = os.path.join(ROOT, "output", "landmark_scene_final_v2.blend")

print("="*60)
print("最终特征点场景 v2")
print("="*60)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

bpy.ops.import_scene.gltf(filepath=GLB_PATH)

mesh_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        mesh_obj = obj
        break

mesh_obj.name = "Tripo_HighPoly"
bpy.context.view_layer.objects.active = mesh_obj
mesh_obj.select_set(True)

# 应用变换
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# ============================================================
# 正确旋转：绕X轴-90° + 绕X轴180° + 绕Z轴180°
# ============================================================
print("\n" + "="*60)
print("正确旋转")
print("="*60)

# 第一次：绕X轴-90°
print("绕X轴-90°...")
mesh_obj.matrix_basis = Matrix.Rotation(math.radians(-90), 4, 'X') @ mesh_obj.matrix_basis
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 第二次：绕X轴180°
print("绕X轴180°...")
mesh_obj.matrix_basis = Matrix.Rotation(math.radians(180), 4, 'X') @ mesh_obj.matrix_basis
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 第三次：绕Z轴180°
print("绕Z轴180°...")
mesh_obj.matrix_basis = Matrix.Rotation(math.radians(180), 4, 'Z') @ mesh_obj.matrix_basis
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# ============================================================
# 缩放到1.8m
# ============================================================
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

bbox = get_bbox(mesh_obj)
print(f"\n旋转后: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")

scale_factor = 1.8 / bbox['size'].z
mesh_obj.scale = (scale_factor, scale_factor, scale_factor)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 重新居中并接地
bbox = get_bbox(mesh_obj)
mesh_obj.location.x = -bbox['center'].x
mesh_obj.location.y = -bbox['center'].y
mesh_obj.location.z = -bbox['min'].z
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bbox = get_bbox(mesh_obj)
print(f"最终: 高={bbox['size'].z:.2f}m, 宽={bbox['size'].x:.2f}m, 深={bbox['size'].y:.2f}m")

# ============================================================
# 创建16个特征点空对象
# ============================================================
landmarks = [
    ("LM_01_head_top", "头顶", (0, 0, 1.75)),
    ("LM_02_chin", "下巴", (0, -0.05, 1.55)),
    ("LM_03_chest", "胸中心", (0, -0.05, 1.35)),
    ("LM_04_abdomen", "腹中心", (0, -0.03, 1.10)),
    ("LM_05_back", "背中心", (0, 0.10, 1.25)),
    ("LM_06_pelvis", "骨盆中心", (0, -0.02, 0.90)),
    ("LM_07_shoulder_L", "左肩", (-0.20, -0.05, 1.50)),
    ("LM_08_elbow_L", "左肘", (-0.50, -0.05, 1.50)),
    ("LM_09_wrist_L", "左腕", (-0.80, -0.05, 1.50)),
    ("LM_10_shoulder_R", "右肩", (0.20, -0.05, 1.50)),
    ("LM_11_elbow_R", "右肘", (0.50, -0.05, 1.50)),
    ("LM_12_wrist_R", "右腕", (0.80, -0.05, 1.50)),
    ("LM_13_knee_L", "左膝", (-0.10, -0.02, 0.50)),
    ("LM_14_ankle_L", "左踝", (-0.10, -0.02, 0.05)),
    ("LM_15_knee_R", "右膝", (0.10, -0.02, 0.50)),
    ("LM_16_ankle_R", "右踝", (0.10, -0.02, 0.05)),
]

for name, cn_name, loc in landmarks:
    bpy.ops.object.empty_add(type='SPHERE', radius=0.02)
    empty = bpy.context.active_object
    empty.name = name
    empty.location = loc
    empty.color = (1.0, 0.2, 0.2, 1.0)
    empty["cn_name"] = cn_name

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"\n保存: {OUT_BLEND}")
print("DONE")
