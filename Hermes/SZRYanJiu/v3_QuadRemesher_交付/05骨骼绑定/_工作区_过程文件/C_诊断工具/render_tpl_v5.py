"""渲染ARP模板v5验证图: 正面视图, 检查点可见性/配色/说明牌."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
SRC = os.path.join(BASE, "_工作区_过程文件", "A_半自动打点", "08_arp打点模板_AI预置.blend")
OUT = os.path.join(BASE, "_工作区_过程文件", "screenshots", "arp模板v5_0827.png")

bpy.ops.wm.open_mainfile(filepath=SRC)
scn = bpy.context.scene
scn.render.engine = 'BLENDER_WORKBENCH'
scn.display.shading.color_type = 'MATERIAL'
scn.display.shading.light = 'STUDIO'
scn.render.resolution_x = 900
scn.render.resolution_y = 1350

cam = bpy.data.cameras.new("v5cam")
cam.type = 'ORTHO'
cam.ortho_scale = 3.2
cam_obj = bpy.data.objects.new("v5cam", cam)
scn.collection.objects.link(cam_obj)
cam_obj.location = (0, -8, 0.95)
cam_obj.rotation_euler = (1.5708, 0, 0)   # 面朝+Y(从前面看)
scn.camera = cam_obj

os.makedirs(os.path.dirname(OUT), exist_ok=True)
scn.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("RENDER_DONE:", OUT)
print("对象统计: 主标记=%d 镜像=%d 说明牌=%d 身体=%d" % (
    len([o for o in bpy.data.objects if o.name.endswith("_loc")]),
    len([o for o in bpy.data.objects if o.name.endswith("_loc_sym")]),
    len([o for o in bpy.data.objects if o.type == "FONT"]),
    len([o for o in bpy.data.objects if "tripo" in o.name]),
))
