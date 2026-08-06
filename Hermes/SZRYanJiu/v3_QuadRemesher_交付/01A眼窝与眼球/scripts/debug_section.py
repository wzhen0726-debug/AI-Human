
import bpy, numpy as np
IN = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_2_eyeball_placed.blend"
OUT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\eye_section.png"
bpy.ops.wm.open_mainfile(filepath=IN)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x = 900; scene.render.resolution_y = 700
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'TEXTURE'
# 侧面剖视: 相机在头的右侧(+X), 看向眼中心. 单看左眼x=-0.0358
from mathutils import Vector
eye_c = Vector((-0.0358, -0.1202, 1.6711))
cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if not cam.users_scene: scene.collection.objects.link(cam)
scene.camera = cam
# 侧面: 从+x看向左眼, 能看到眼球前后位置 vs 眼睑
cam.location = Vector((eye_c.x + 0.10, eye_c.y, eye_c.z))
look = eye_c - cam.location
cam.rotation_euler = look.to_track_quat('-Z','Y').to_euler()
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("saved", OUT)
