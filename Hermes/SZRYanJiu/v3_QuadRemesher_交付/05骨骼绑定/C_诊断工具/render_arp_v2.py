"""渲染ARP模板v2验证图: 确认画面干净(只有模型+17球+1提示牌)."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(BASE, "A_半自动打点", "07_arp_markers.blend"))

# 统计场景对象
n_arp = sum(1 for o in bpy.data.objects if o.name.startswith("ARP_"))
n_lm = sum(1 for o in bpy.data.objects if o.name.startswith("LM_"))
n_font = sum(1 for o in bpy.data.objects if o.type == 'FONT')
n_mesh = sum(1 for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith("ARP_"))
print(f"对象统计: ARP球={n_arp}, 旧LM标记={n_lm}, 文字牌={n_font}, 模型网格={n_mesh}")

# 临时相机渲染正面图
scn = bpy.context.scene
scn.render.engine = 'BLENDER_WORKBENCH'
scn.display.shading.color_type = 'MATERIAL'  # Workbench按材质色渲染(否则全灰)
scn.display.shading.light = 'STUDIO'
scn.render.resolution_x = 900
scn.render.resolution_y = 1200
scn.render.film_transparent = True

cam_data = bpy.data.cameras.new("verify_cam")
cam = bpy.data.objects.new("verify_cam", cam_data)
cam.location = (0, -4.5, 1.0)
cam.rotation_euler = (1.5708, 0, 0)
scn.collection.objects.link(cam)
scn.camera = cam

out_png = os.path.join(BASE, "screenshots", "arp模板v2验证_0827.png")
scn.render.filepath = out_png
bpy.ops.render.render(write_still=True)
print(f"渲染: {out_png}")
print("RENDER_ARP_V2_DONE")
