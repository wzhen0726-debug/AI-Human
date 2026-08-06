
import bpy, numpy as np
from mathutils import Vector
IN = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_2_eyeball_placed.blend"
bpy.ops.wm.open_mainfile(filepath=IN)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x = 800; scene.render.resolution_y = 800
scene.display.shading.light = 'STUDIO'; scene.display.shading.color_type = 'TEXTURE'
cL=Vector((-0.0358,-0.1097,1.6711)); cR=Vector((0.0326,-0.1097,1.6707)); fc=(cL+cR)/2
cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if not cam.users_scene: scene.collection.objects.link(cam)
scene.camera = cam
SHOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots"
# 正面
cam.data.type='ORTHO'; cam.data.ortho_scale=0.15
cam.location = Vector((fc.x, fc.y-0.35, fc.z)); cam.rotation_euler=(fc-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath = SHOT+r"\check_front.png"; bpy.ops.render.render(write_still=True)
# 侧面(看眼球前后位置): 从左侧-X看向头
cam.data.ortho_scale=0.10
cam.location = Vector((cL.x-0.20, cL.y, cL.z)); cam.rotation_euler=(cL-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath = SHOT+r"\check_side.png"; bpy.ops.render.render(write_still=True)
print("saved check_front + check_side")
