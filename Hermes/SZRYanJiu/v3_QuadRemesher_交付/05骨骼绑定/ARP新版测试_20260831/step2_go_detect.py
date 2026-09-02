"""ARP全新测试(2026-08-31) — 步骤2: go_detect 生成ARP骨架
输入: 01_AI打点.blend (用户已修正点位)
停下等用户确认参考骨架位置, 再继续步骤3 提取55骨.
输出: 02_go_detect骨架.blend + 参考骨位置报告"""
import bpy, sys, os

OUT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831"
IN = os.path.join(OUT, "01_AI打点.blend")

bpy.ops.wm.open_mainfile(filepath=IN)
bpy.ops.preferences.addon_enable(module='auto_rig_pro-master')

for key, mod in list(sys.modules.items()):
    if 'auto_rig' in key and hasattr(mod, 'display_popup_message'):
        mod.display_popup_message = lambda m, h=' ', i='': print(f"[ARP {h}] {m}")
        break

scn = bpy.context.scene
bpy.context.window.screen = bpy.data.screens['Layout']
area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')

print("########## 步骤2: go_detect ##########")
with bpy.context.temp_override(area=area, region=region):
    scn.arp_smart_depth = False
    scn.arp_smart_fingers_engine = 'LEGACY'
    bpy.ops.id.go_detect('EXEC_DEFAULT')
    print("go_detect OK")

rig = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
assert rig, "go_detect未生成骨架"
refs = [b for b in rig.data.bones if '_ref' in b.name]
print(f"ARP骨架: {len(rig.data.bones)}骨, 参考骨{len(refs)}根")

# 参考骨关键点位报告(对照用户标记点)
print("\n参考骨关键位置(世界坐标):")
mw = rig.matrix_world
for n in ["root_ref.x", "head_ref.x", "neck_ref.x", "arm_ref.l", "hand_ref.l",
          "thigh_ref.l", "foot_ref.l", "middle1_ref.l", "thumb1_ref.l"]:
    b = rig.data.bones.get(n)
    if b:
        h = mw @ b.head_local
        print(f"  {n}: head=({h.x:.3f},{h.y:.3f},{h.z:.3f})")

# 变形骨手位置(已知ARP对T-pose错位, 只记录不修复)
hd = rig.data.bones.get("hand.l")
if hd:
    h = mw @ hd.head_local
    print(f"\n[已知问题] 变形骨hand.l z={h.z:.3f} (T-pose错位预期, 步骤3会弃变形骨走参考骨提取)")

out2 = os.path.join(OUT, "02_go_detect骨架.blend")
bpy.ops.wm.save_mainfile(filepath=out2)
print(f"\n保存: {out2}")
print("========== STEP2_DONE ==========")
