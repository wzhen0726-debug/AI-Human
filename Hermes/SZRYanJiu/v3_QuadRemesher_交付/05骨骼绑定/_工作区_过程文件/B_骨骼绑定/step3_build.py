"""第3步: 用模板v6的官方命名标记直接构建ARP骨架.
模板里已有 root_loc/chin_loc/... 全部17点(官方命名), 跳过guess_markers直接go_detect."""
import bpy, sys, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
TPL = os.path.join(BASE, "_工作区_过程文件", "A_半自动打点", "08_arp打点模板_v6.blend")
OUT = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "07_arp_rig_v6.blend")
AI_PATH = r"C:\Users\Liyunzhong\Documents\AutoRigPro\AI"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=TPL)

# 身体
body = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices))
print(f"身体: {body.name}, {len(body.data.vertices)}顶点")

# 启用ARP + popup补丁
bpy.ops.preferences.addon_enable(module='auto_rig_pro-master')
if 'auto_rig_pro-master' in bpy.context.preferences.addons:
    bpy.context.preferences.addons['auto_rig_pro-master'].preferences.ai_presets_path = AI_PATH
for key, mod in list(sys.modules.items()):
    if 'auto_rig' in key and hasattr(mod, 'display_popup_message'):
        mod.display_popup_message = lambda m, h=' ', i='': print(f"[ARP {h}] {m}")
        break
print("ARP启用+补丁OK")

# 上下文
bpy.context.window.screen = bpy.data.screens['Layout']
area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
bpy.context.view_layer.objects.active = body

scn = bpy.context.scene
with bpy.context.temp_override(area=area, region=region):
    bpy.ops.id.get_selected_objects('EXEC_DEFAULT')
    print("get_selected_objects OK")

    # 标记已在模板里(官方命名), 直接构建
    scn.arp_smart_depth = False
    scn.arp_smart_fingers_engine = 'LEGACY'
    try:
        bpy.ops.id.go_detect('EXEC_DEFAULT')
        print("go_detect OK")
    except Exception as e:
        print(f"go_detect异常: {type(e).__name__}: {e}")

# 骨架+权重 (后台模式: 避免select_all等对window有要求的ops)
arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if arm:
    print(f"骨架: {arm.name}, {len(arm.data.bones)}骨")
    # 确保OBJECT模式(go_detect后可能停留在其他模式)
    bpy.context.view_layer.objects.active = arm
    if arm.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    # 直接用数据API选择(不用select_all ops)
    for o in bpy.data.objects:
        o.select_set(False)
    body.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    print(f"权重顶点组: {len(body.vertex_groups)}")
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print(f"保存: {OUT}")
else:
    print("ERROR: 未生成骨架")

print("STEP3_BUILD_DONE")
