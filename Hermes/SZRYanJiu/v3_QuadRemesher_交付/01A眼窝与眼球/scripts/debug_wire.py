
import bpy
from mathutils import Vector
SOCKET = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_1_eye_socket.blend"
bpy.ops.wm.open_mainfile(filepath=SOCKET)
scene = bpy.context.scene
scene.render.engine='BLENDER_WORKBENCH'; scene.render.resolution_x=900; scene.render.resolution_y=900
scene.display.shading.light='STUDIO'; scene.display.shading.show_xray_wireframe=True
scene.display.shading.show_cavity=True
c = Vector((-0.0358,-0.10,1.6711))
cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if not cam.users_scene: scene.collection.objects.link(cam)
scene.camera=cam; cam.data.type='ORTHO'; cam.data.ortho_scale=0.05
cam.location=Vector((c.x, c.y-0.12, c.z)); cam.rotation_euler=(c-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\socket_wire.png"
bpy.ops.render.render(write_still=True)
print("saved wire")
