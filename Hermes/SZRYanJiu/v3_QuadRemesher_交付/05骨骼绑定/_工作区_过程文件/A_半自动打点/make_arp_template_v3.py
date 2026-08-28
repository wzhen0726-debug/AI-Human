"""ARP打点模板v3 (2026-08-27, 按用户要求从0到有自己摆).
内容: 只有身体模型 + 正视视口 + 一块说明牌(怎么打开打点工具).
无预置标记 — 用户在N面板按钮逐个放置, 位置全由用户光标决定.
对称点自动镜像(驱动实时同步), 用户只摆主侧."""
import bpy, os
from mathutils import Quaternion

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
SRC = os.path.join(BASE, "A_半自动打点", "06_rig_markers.blend")
OUT = os.path.join(BASE, "A_半自动打点", "07_arp_markers.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=SRC)

# ===== 删除一切标记/旧工具痕迹, 只留模型 =====
to_remove = [o for o in bpy.data.objects if o.name.startswith("LM_")
             or o.name.startswith("ARP_")
             or o.type == 'FONT'
             or o.get("arp_name") is not None]
for o in to_remove:
    bpy.data.objects.remove(o, do_unlink=True)
for c in list(bpy.data.collections):
    if c.name in ("LM_M", "LM_R", "LM_L", "ARP_Markers"):
        bpy.data.collections.remove(c)
print(f"已清空旧内容: {len(to_remove)}个对象")

# 文本块嵌入打点工具代码(用户无需找外部py文件)
if "arp_marker_tool" in bpy.data.texts:
    bpy.data.texts.remove(bpy.data.texts["arp_marker_tool"])
tool_path = os.path.join(BASE, "A_半自动打点", "arp_marker_tool.py")
with open(tool_path, encoding="utf-8") as f:
    txt = bpy.data.texts.new("arp_marker_tool")
    txt.write(f.read())

# ===== 说明牌(左侧, 竖立面向相机) =====
cu = bpy.data.curves.new("arp_hint", type='FONT')
cu.body = ("ARP打点 (从零开始)\n"
           "1. 顶部切到 Scripting 标签页\n"
           "2. 打开文本 arp_marker_tool → 点 ▶ 运行一次\n"
           "3. 回 Layout 按 N → ARP打点 面板\n"
           "4. 先把3D光标移到位(Shift+右键)\n"
           "   再点对应部位按钮\n"
           "5. 对称点自动出对侧镜像球\n"
           "6. 十个点摆完 Ctrl+S 保存")
cu.size = 0.055
txt_obj = bpy.data.objects.new("ARP打点说明", cu)
txt_obj.location = (-1.45, -1.2, 1.55)
txt_obj.rotation_euler = (1.5708, 0, 0)
bpy.context.scene.collection.objects.link(txt_obj)

# ===== 视口: 正视全身 =====
scn = bpy.context.scene
scn.cursor.location = (0, 0, 1.0)   # 光标先放身体中段(Blender 5.x: scene.cursor.location)
for ws in bpy.data.workspaces:
    for scr in ws.screens:
        for area in scr.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        sp = space.region_3d
                        sp.view_perspective = 'ORTHO'
                        sp.view_distance = 3.0
                        sp.view_location = (0.0, 0.0, 0.9)
                        sp.view_rotation = Quaternion((0.7071, 0.7071, 0.0, 0.0))
                        space.shading.type = 'MATERIAL'

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"保存: {OUT}")
print("ARP_TEMPLATE_V3_DONE")
