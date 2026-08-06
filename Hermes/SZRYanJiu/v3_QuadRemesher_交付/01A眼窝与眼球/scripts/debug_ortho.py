
import bpy, numpy as np
from mathutils import Vector
IN = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_2_eyeball_placed.blend"
bpy.ops.wm.open_mainfile(filepath=IN)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x = 900; scene.render.resolution_y = 900
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'TEXTURE'
cL = Vector((-0.0358,-0.1145,1.6711)); cR = Vector((0.0326,-0.1145,1.6707))
fc = (cL+cR)/2
cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if not cam.users_scene: scene.collection.objects.link(cam)
scene.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 0.14  # 14cm视野, 正好双眼区
# 严格正面: 相机在脸正前方(-Y), 看向眼中心. 无仰视/俯视
cam.location = Vector((fc.x, fc.y - 0.30, fc.z))
look = fc - cam.location
cam.rotation_euler = look.to_track_quat('-Z','Y').to_euler()
scene.render.filepath = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\eye_ortho_front.png"
bpy.ops.render.render(write_still=True)
print("saved ortho front")
