"""ARP绑定 v2: 用用户从0打好的点(07_arp_markers.blend, 2026-08-27)驱动ARP Smart.
核心改进(vs arp_rig.py): 不用AI推理+几何修正猜位置 — 用户已摆好全部17个点.
流程: 打开用户点位blend → 启用ARP插件 → guess_markers(生成标记对象) →
      把用户17点的坐标写入对应 _loc/_sym 标记 → depth=False → go_detect生成骨架 → 权重."""
import bpy, sys, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
POINTS = os.path.join(BASE, "A_半自动打点", "07_arp_markers.blend")
OUT_BLEND = os.path.join(BASE, "B_骨骼绑定", "06_rig_arp.blend")
AI_PATH = r"C:\Users\Liyunzhong\Documents\AutoRigPro\AI"

# ===== 1) 读用户点位 =====
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=POINTS)
user_pts = {}
for o in bpy.data.objects:
    if o.get("arp_name") is not None:
        user_pts[o.get("arp_name")] = o.matrix_world.translation.copy()
print(f"用户点位: {len(user_pts)}")
for k in sorted(user_pts):
    print(f"  {k}: ({user_pts[k].x:.3f}, {user_pts[k].y:.3f}, {user_pts[k].z:.3f})")

# 身体网格
body = max((o for o in bpy.data.objects if o.type == 'MESH' and 'eye' not in o.name.lower()),
           key=lambda o: len(o.data.polygons))
print(f"身体: {body.name}, {len(body.data.vertices)}顶点")

# 腿侧修正: 用户'右手侧标(+x)' 模型面-Y → 是模型左侧(thigh_loc在+x时)
# ARP约定: thigh_loc/...在模型自身左 = 从正面看我们的+x? 需检验spec——先按原样写入,
# 若骨架左右颠倒再翻转(有对照数据可查)

# ===== 2) 启用ARP + 补丁 =====
bpy.ops.preferences.addon_enable(module='auto_rig_pro-master')
if 'auto_rig_pro-master' in bpy.context.preferences.addons:
    bpy.context.preferences.addons['auto_rig_pro-master'].preferences.ai_presets_path = AI_PATH
for key, mod in list(sys.modules.items()):
    if 'auto_rig' in key and hasattr(mod, 'display_popup_message'):
        mod.display_popup_message = lambda message, header=' ', icon_type='': print(f"[ARP {header}] {message}")
ars = None
for key, mod in list(sys.modules.items()):
    if 'auto_rig_smart' in key and hasattr(mod, '_screenshot_char'):
        ars = mod
        break
if ars:
    def screenshot_patched(self):
        print("(截图跳过: 用用户点位代替AI推理)")
        self.front_samples_rot = [0.0]
    ars._screenshot_char = screenshot_patched
print("ARP补丁OK")

# ===== 3) 上下文 =====
bpy.context.window.screen = bpy.data.screens['Layout']
area = next((a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'), None)
region = next((r for r in area.regions if r.type == 'WINDOW'), None)
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
bpy.context.view_layer.objects.active = body

scn = bpy.context.scene
with bpy.context.temp_override(area=area, region=region):
    # Step1: 注册选中物体
    bpy.ops.id.get_selected_objects('EXEC_DEFAULT')
    # Step2: guess_markers — AI截图补丁会跳过真实推理, 但仍会创建空标记集
    scn.arp_smart_AI_body_samples = 1
    try:
        bpy.ops.arp.guess_markers('EXEC_DEFAULT')
        print("guess_markers OK")
    except Exception as e:
        print(f"guess_markers异常(可能可忽略): {type(e).__name__}: {e}")

    # ===== 4) 写入用户点位到ARP标记 =====
    def set_mark(name, v):
        o = bpy.data.objects.get(name)
        if o:
            o.location = (v.x, v.y, v.z)
            return True
        return False

    mapping = {
        "root_loc": "root_loc", "chin_loc": "chin_loc", "neck_loc": "neck_loc",
        "shoulder_loc": "shoulder_loc", "elbow_loc": "elbow_loc",
        "hand_loc": "hand_loc", "hand_tip_loc": "hand_tip_loc",
        "thigh_loc": "thigh_loc", "knee_loc": "knee_loc", "foot_loc": "foot_loc",
    }
    wrote = []
    for arp_name, key in mapping.items():
        if key in user_pts:
            ok = set_mark(arp_name, user_pts[key])
            ok_sym = set_mark(arp_name + "_sym", user_pts[key])
            wrote.append((arp_name, ok, ok_sym))
    missing = [n for n, a, b in wrote if not (a or b)]
    print(f"点位写入: {sum(1 for _,a,b in wrote if a or b)}/{len(wrote)}, 缺: {missing}")

    # 手动补缺(如guess没创建某标记对象则无法写) — 记录即可
    all_marks = [o.name for o in bpy.data.objects if o.name.endswith("_loc") or o.name.endswith("_loc_sym")]
    print(f"ARP标记对象总数: {len(all_marks)}")

    # ===== 5) 关深度检测, 生成骨架 =====
    scn.arp_smart_depth = False
    # 手指引擎: 默认'AI'会找thumb1_loc等AI手指标记(我们没有→NoneType崩溃);
    # 设LEGACY且无_bot_auto对象时ARP自动跳过AI手指段, 用标准位置生成指骨
    scn.arp_smart_fingers_engine = 'LEGACY'
    try:
        bpy.ops.id.go_detect('EXEC_DEFAULT')
        print("go_detect OK")
    except Exception as e:
        print(f"go_detect异常: {type(e).__name__}: {e}")

# ===== 6) 骨架+权重 =====
arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if arm:
    print(f"骨架: {arm.name}, {len(arm.data.bones)}骨")
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    for o in bpy.data.objects:
        o.select_set(False)
    body.select_set(True)
    arm.select_set(True)
    win = bpy.context.window
    with bpy.context.temp_override(window=win, screen=bpy.context.screen, area=area, region=region):
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    print(f"权重顶点组: {len(body.vertex_groups)}")
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
else:
    print("ERROR: 未生成骨架")

print("ARP_RIG_V2_DONE")
