"""渲染打点模板正面视图, 验证文字牌朝向+中线点位置(视觉证据)."""
import bpy, math

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
OUT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\screenshots\模板正面验证_0825.png"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

scn = bpy.context.scene
# 相机: 与模板视口一致, 从−Y看向+Y(正视)
cam_data = bpy.data.cameras.get("_验证相机") or bpy.data.cameras.new("_验证相机")
cam = bpy.data.objects.get("_验证相机")
if not cam:
    cam = bpy.data.objects.new("_验证相机", cam_data)
    scn.collection.objects.link(cam)
cam.location = (0, -3.2, 0.95)
cam.rotation_euler = (math.pi / 2, 0, 0)   # 看向+Y
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 3.2
scn.camera = cam

scn.render.engine = 'BLENDER_EEVEE'
scn.render.resolution_x = 900
scn.render.resolution_y = 900
scn.render.image_settings.file_format = 'PNG'
scn.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("RENDER_DONE", OUT)
