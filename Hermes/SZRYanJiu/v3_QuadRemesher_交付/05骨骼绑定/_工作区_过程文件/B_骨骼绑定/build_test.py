"""端到端测试: AI预置标记 → ARP go_detect构建 → 验证手骨脚骨位置.
复用ai_guess_test.py的补丁(popup/截图), 但跳过guess_markers(标记已预置)."""
import bpy, sys, os, math
from mathutils import Vector

TPL = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\_工作区_过程文件\A_半自动打点\08_arp打点模板_AI预置.blend"
AI_PATH = r"C:\Users\Liyunzhong\Documents\AutoRigPro\AI"
BODY = "tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module='auto_rig_pro-master')
bpy.context.preferences.addons['auto_rig_pro-master'].preferences.ai_presets_path = AI_PATH
for key, mod in list(sys.modules.items()):
    if 'auto_rig' in key and hasattr(mod, 'display_popup_message'):
        mod.display_popup_message = lambda m, h=' ', i='': print(f"[ARP {h}] {m}")
        break

bpy.ops.wm.open_mainfile(filepath=TPL)
# 找主体(排除眼睛/标记球)
cands = [o for o in bpy.data.objects if o.type == 'MESH' and 'eye' not in o.name.lower()
         and not o.name.endswith('_loc') and not o.name.endswith('_loc_sym') and o.name != '说明']
body = max(cands, key=lambda o: len(o.data.polygons))
print(f"主体: {body.name} {len(body.data.vertices)}顶点")

bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
bpy.context.view_layer.objects.active = body

bpy.context.window.screen = bpy.data.screens['Layout']
area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')

with bpy.context.temp_override(area=area, region=region):
    print("--- get_selected_objects ---")
    bpy.ops.id.get_selected_objects('EXEC_DEFAULT')
    # 标记已由模板预置, 直接构建(关深度检测用标记Y)
    bpy.context.scene.arp_smart_depth = False
    print("--- go_detect ---")
    try:
        bpy.ops.id.go_detect('EXEC_DEFAULT')
        print("go_detect OK")
    except Exception as e:
        print(f"go_detect异常: {type(e).__name__}: {e}")

# 验证骨架
arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if not arm:
    print("FAIL: 无骨架")
    sys.exit(1)
print(f"骨架 {arm.name}: {len(arm.data.bones)}骨")

# 手骨脚骨位置对照(用户打的点)
mw = arm.matrix_world
checks = {
    "肩": ("upArm_fk.l", (0.194, -0.028, 1.454)),
    "腕": ("hand_fk.l", (0.710, -0.002, 1.436)),
    "踝": ("foot_fk.l", (0.143, 0.006, 0.101)),
}
for label, (bn, target) in checks.items():
    # 找含关键词的骨
    b = next((x for x in arm.data.bones if bn.replace("_fk.l","") in x.name.lower() and ".l" in x.name.lower()), None)
    if b:
        h = mw @ b.head_local
        d = ((Vector(h) - Vector(target)).length) * 100
        print(f"[{label}] {b.name}: ({h.x:.3f},{h.y:.3f},{h.z:.3f}) 差{d:.1f}cm")
    else:
        print(f"[{label}] 找不到骨")
# 手指骨数量
finger_bones = [b.name for b in arm.data.bones if any(f in b.name.lower() for f in ("thumb","index","middle","ring","pinky"))]
print(f"手指骨数: {len(finger_bones)}")
print("BUILD_TEST_DONE")
