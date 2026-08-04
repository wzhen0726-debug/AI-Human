import bpy, os, sys
from mathutils import Vector

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
TRIPO_BLEND = os.path.join(ROOT, "output", "tripo_tpose_prepared_v3.blend")
OUT_BLEND = os.path.join(ROOT, "output", "landmark_scene.blend")

print("="*60)
print("创建特征点空对象场景")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=TRIPO_BLEND)

# 删除现有空对象
for obj in list(bpy.data.objects):
    if obj.type == 'EMPTY':
        bpy.data.objects.remove(obj, do_unlink=True)

# 定义16个特征点（名称和初始位置）
# 初始位置放在模型中心附近，方便用户移动
landmarks = [
    # 头部
    ("LM_01_head_top", "头顶", (0, 0, 1.75)),
    ("LM_02_chin", "下巴", (0, -0.05, 1.55)),
    
    # 躯干
    ("LM_03_chest", "胸中心", (0, -0.05, 1.35)),
    ("LM_04_abdomen", "腹中心", (0, -0.03, 1.10)),
    ("LM_05_back", "背中心", (0, 0.10, 1.25)),
    ("LM_06_pelvis", "骨盆中心", (0, -0.02, 0.90)),
    
    # 左臂
    ("LM_07_shoulder_L", "左肩", (-0.20, -0.05, 1.50)),
    ("LM_08_elbow_L", "左肘", (-0.35, -0.05, 1.20)),
    ("LM_09_wrist_L", "左腕", (-0.50, -0.05, 0.90)),
    
    # 右臂
    ("LM_10_shoulder_R", "右肩", (0.20, -0.05, 1.50)),
    ("LM_11_elbow_R", "右肘", (0.35, -0.05, 1.20)),
    ("LM_12_wrist_R", "右腕", (0.50, -0.05, 0.90)),
    
    # 左腿
    ("LM_13_knee_L", "左膝", (-0.10, -0.02, 0.50)),
    ("LM_14_ankle_L", "左踝", (-0.10, -0.02, 0.05)),
    
    # 右腿
    ("LM_15_knee_R", "右膝", (0.10, -0.02, 0.50)),
    ("LM_16_ankle_R", "右踝", (0.10, -0.02, 0.05)),
]

# 创建空对象
for name, cn_name, loc in landmarks:
    bpy.ops.object.empty_add(type='SPHERE', radius=0.02)
    empty = bpy.context.active_object
    empty.name = name
    empty.location = loc
    # 设置显示颜色
    empty.color = (1.0, 0.2, 0.2, 1.0)  # 红色
    # 添加自定义属性显示中文名
    empty["cn_name"] = cn_name
    print(f"  {name} ({cn_name}): {loc}")

# 保存场景
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"\n保存: {OUT_BLEND}")
print("\nDONE")
