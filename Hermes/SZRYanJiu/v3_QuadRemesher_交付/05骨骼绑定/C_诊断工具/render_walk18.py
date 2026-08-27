"""渲染行走帧18验证图: 正面+侧面, 验证手臂/腿姿态正常."""
import bpy, os
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(BASE, "B_骨骼绑定", "walk_test_手写版.blend"))

scn = bpy.context.scene
scn.frame_set(18)
bpy.context.view_layer.update()

for view, cam_pos in [("正面", (0, -4, 1.0)), ("侧面", (4, 0, 1.0))]:
    cam_data = bpy.data.cameras.new(f"cam_{view}")
    cam = bpy.data.objects.new(f"cam_{view}", cam_data)
    cam.location = Vector(cam_pos)
    d = (Vector((0, 0, 1.0)) - Vector(cam_pos)).normalized()
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    scn.collection.objects.link(cam)
    scn.camera = cam
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 2.6

    scn.render.engine = 'BLENDER_WORKBENCH'
    scn.render.resolution_x = 700
    scn.render.resolution_y = 900
    scn.display.shading.light = 'FLAT'
    scn.display.shading.color_type = 'MATERIAL'
    out = os.path.join(BASE, "screenshots", f"walk18_{view}_0827.png")
    scn.render.filepath = out
    scn.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    print(f"渲染: {view} -> {out}")