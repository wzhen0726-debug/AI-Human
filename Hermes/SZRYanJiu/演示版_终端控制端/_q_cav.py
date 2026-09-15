import bpy, os, json, math
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
scn=bpy.context.scene
scn.render.engine='BLENDER_WORKBENCH'
sh=scn.display.shading
sh.light='STUDIO'; sh.studio_light='Default'; sh.color_type='SINGLE'; sh.single_color=(0.75,0.75,0.77)
sh.show_cavity=True; sh.cavity_type='BOTH'; sh.cavity_ridge_factor=2.0; sh.cavity_valley_factor=2.0
scn.render.resolution_x=1400; scn.render.resolution_y=1100
cam=bpy.data.objects.new("_c", bpy.data.cameras.new("_c")); scn.collection.objects.link(cam)
scn.camera=cam; cam.data.type='ORTHO'
# 正视图 + 斜 25° 与 40°(抓曲率起伏)
for side in ("L","R"):
    c=Vector(tuple(float(x) for x in J[side]['center']))
    for ang,nm in ((0,"f"),(25,"a25"),(45,"a45")):
        a=math.radians(ang)
        cam.location=c+Vector((0.6*math.sin(a),-0.6*math.cos(a),0.01))
        cam.rotation_euler=(1.5707963,0,a)
        cam.data.ortho_scale=0.042
        scn.render.filepath=os.path.join(D,"logs",f"cav_{side}_{nm}.png"); bpy.ops.render.render(write_still=True)
print("cav shots done")
