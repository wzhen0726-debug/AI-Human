import bpy, os, sys, math
from mathutils import Vector, Matrix

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
GLB_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\AI生成高模\02_tripoTpose\raw_model.glb"
OUT_BLEND = os.path.join(ROOT, "output", "landmark_scene_v6.blend")

print("="*60)
print("特征点场景 v6: 中英文命名 + 显示在最前方 + 精确定位")
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
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 旋转: 绕X-90 + 绕Z-90 + 绕Y-90
for axis in ['X', 'Z', 'Y']:
    mesh_obj.matrix_basis = Matrix.Rotation(math.radians(-90), 4, axis) @ mesh_obj.matrix_basis
    bpy.context.view_layer.update()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 缩放到1.8m
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
scale_factor = 1.8 / bbox['size'].z
mesh_obj.scale = (scale_factor, scale_factor, scale_factor)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bbox = get_bbox(mesh_obj)
mesh_obj.location.x = -bbox['center'].x
mesh_obj.location.y = -bbox['center'].y
mesh_obj.location.z = -bbox['min'].z
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bbox = get_bbox(mesh_obj)
print(f"模型: 高={bbox['size'].z:.2f}m, 宽={bbox['size'].x:.2f}m, 深={bbox['size'].y:.2f}m")

# ============================================================
# 创建16个特征点空对象
# 中英文命名 + 显示在最前方 + 精确定位
# ============================================================
# 坐标系: X=左右(左负右正), Y=前后(前负后正, -Y是正面), Z=上下

landmarks = [
    # 头部 - 标在正前方(面部)
    ("LM_01_头顶_head_top", "头顶正中(从正上方看,头部最高点的中心,标在头顶表面)", (0, -0.02, 1.75)),
    ("LM_02_下巴_chin", "下巴尖(下颌骨最前端,从正面看最下方的突出点)", (0, -0.08, 1.52)),

    # 躯干 - 标在正前方(胸部/腹部),背中心标在后方
    ("LM_03_胸口_chest", "胸口正中(两乳头连线中点,正面)", (0, -0.08, 1.38)),
    ("LM_04_腹部_abdomen", "肚脐(腹部正中,正面)", (0, -0.06, 1.10)),
    ("LM_05_后背_back", "后背正中(与胸口对应的高度,背面)", (0, 0.08, 1.38)),
    ("LM_06_骨盆_pelvis", "骨盆正中(裆部上方,正面)", (0, -0.04, 0.92)),

    # 左臂 - T-pose手臂水平,标在手臂中心(不分前后)
    ("LM_07_左肩_shoulder_L", "左肩关节(手臂与躯干连接处,从上方看是凹陷点)", (-0.22, -0.02, 1.48)),
    ("LM_08_左肘_elbow_L", "左肘关节(手臂中段弯曲处,标在手臂中心)", (-0.55, -0.02, 1.48)),
    ("LM_09_左腕_wrist_L", "左手腕(手掌与手臂连接处,标在手臂中心)", (-0.85, -0.02, 1.48)),

    # 右臂
    ("LM_10_右肩_shoulder_R", "右肩关节(手臂与躯干连接处,从上方看是凹陷点)", (0.22, -0.02, 1.48)),
    ("LM_11_右肘_elbow_R", "右肘关节(手臂中段弯曲处,标在手臂中心)", (0.55, -0.02, 1.48)),
    ("LM_12_右腕_wrist_R", "右手腕(手掌与手臂连接处,标在手臂中心)", (0.85, -0.02, 1.48)),

    # 左腿 - 标在腿中心(膝盖骨正面)
    ("LM_13_左膝_knee_L", "左膝盖(膝盖骨正前方)", (-0.12, -0.04, 0.50)),
    ("LM_14_左踝_ankle_L", "左脚踝(踝关节正前方)", (-0.12, -0.02, 0.06)),

    # 右腿
    ("LM_15_右膝_knee_R", "右膝盖(膝盖骨正前方)", (0.12, -0.04, 0.50)),
    ("LM_16_右踝_ankle_R", "右脚踝(踝关节正前方)", (0.12, -0.02, 0.06)),
]

for name, desc, loc in landmarks:
    bpy.ops.object.empty_add(type='SPHERE', radius=0.015)
    empty = bpy.context.active_object
    empty.name = name
    empty.location = loc
    empty.color = (1.0, 0.0, 0.0, 1.0)  # 红色
    empty["description"] = desc
    # 开启显示在最前方
    empty.empty_display_size = 0.015
    # 设置显示在最前方（在所有模式下都显示）
    empty.show_in_front = True

    print(f"  {name}")
    print(f"    位置: ({loc[0]:.2f}, {loc[1]:.2f}, {loc[2]:.2f})")
    print(f"    说明: {desc}")

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"\n保存: {OUT_BLEND}")
print("DONE")
