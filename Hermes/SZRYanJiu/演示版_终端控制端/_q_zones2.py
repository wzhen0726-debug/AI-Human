import bpy, os, json, math, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_2_eyeball_placed.blend"))
scn=bpy.context.scene
scn.render.engine='BLENDER_WORKBENCH'
sh=scn.display.shading
sh.light='STUDIO'; sh.color_type='SINGLE'; sh.single_color=(0.72,0.72,0.74); sh.show_cavity=True; sh.cavity_type='BOTH'
scn.render.resolution_x=1100; scn.render.resolution_y=900
cam=bpy.data.objects.new("_c", bpy.data.cameras.new("_c")); scn.collection.objects.link(cam)
scn.camera=cam; cam.data.type='ORTHO'
# 每个眼: 内上 / 外上 两个机位(斜 20° 俯视, 抓凸起/穿插)
for side,cx in (("L",-1),("R",1)):
    c=Vector(tuple(float(x) for x in J[side]['center']))
    for tag,off in (("inup",(-0.010,0.008)),("outup",(0.012,0.008)),("mid",(0.0,0.0))):
        tgt=c+Vector((cx*off[0],0,off[1]))
        cam.location=tgt+Vector((0,-0.5,0.20)); cam.rotation_euler=(1.20,0,0)
        cam.data.ortho_scale=0.026
        scn.render.filepath=os.path.join(D,"logs",f"z2_{side}_{tag}.png"); bpy.ops.render.render(write_still=True)
print("zones done")
