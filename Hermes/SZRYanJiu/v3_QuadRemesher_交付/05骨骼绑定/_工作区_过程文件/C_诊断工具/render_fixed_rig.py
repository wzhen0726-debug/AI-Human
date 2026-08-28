"""渲染修复版骨架正面图 — 验证关节连接和手指形态."""
import bpy, os, math

BASE = os.path.join(r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定", "_工作区_过程文件")
SRC = os.path.join(BASE, "B_骨骼绑定", "14_arp_refs_rollonly.blend")
OUT = os.path.join(BASE, "screenshots", "骨架修复版_0828.png")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=SRC)

# 显示所有对象
for o in bpy.data.objects:
    o.hide_viewport = False
    o.hide_set(False)

arm = bpy.data.objects.get("MixamoSkeleton")
# 让网格线框化+半透明, 骨架清晰可见
body.display_type = 'WIRE'
body.show_transparent = True
for mat in body.data.materials:
    if mat:
        mat.blend_method = 'BLEND' if hasattr(mat, 'blend_method') else None

# 骨架显示设置
arm.show_in_front = True
arm.display_type = 'WIRE'

# 相机: 正面正交
cam_data = bpy.data.cameras.new("cam")
cam_data.type = 'ORTHO'
cam_data.ortho_scale = 2.6
cam = bpy.data.objects.new("cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location = (0, -5, 1.0)
cam.rotation_euler = (math.pi/2, 0, 0)
bpy.context.scene.camera = cam

# 渲染设置 — Workbench引擎才能渲染出骨架线框
scn = bpy.context.scene
scn.render.engine = 'BLENDER_WORKBENCH'
scn.display.shading.color_type = 'OBJECT'
scn.display.shading.show_xray = True
scn.display.shading.light = 'FLAT'
scn.render.resolution_x = 900
scn.render.resolution_y = 1100
scn.render.film_transparent = True

scn.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print(f"渲染: {OUT}")
print("RENDER_DONE")
