import bpy, os, json, math, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
scn=bpy.context.scene
scn.render.engine='BLENDER_WORKBENCH'
sh=scn.display.shading
sh.light='STUDIO'; sh.color_type='SINGLE'; sh.single_color=(0.62,0.62,0.64); sh.show_cavity=True; sh.cavity_type='BOTH'
scn.render.resolution_x=1200; scn.render.resolution_y=900
cam=bpy.data.objects.new("_c", bpy.data.cameras.new("_c")); scn.collection.objects.link(cam)
scn.camera=cam; cam.data.type='ORTHO'
def shot(loc, rot, scale, path, res=(1200,900)):
    scn.render.resolution_x, scn.render.resolution_y = res
    cam.location=loc; cam.rotation_euler=rot; cam.data.ortho_scale=scale
    scn.render.filepath=path; bpy.ops.render.render(write_still=True)
fz=(1.5707963,0,0)   # 前视
bz=(1.5707963,0,3.14159265)  # 后视
for side in ("L","R"):
    c=Vector(tuple(float(x) for x in J[side]['center']))
    shot(c+Vector((0,-0.6,0)), fz, 0.055, os.path.join(D,"logs",f"fin_{side}_solid.png"))
# 线框: 复制 + Wireframe 修改器
wf=head.copy(); wf.data=head.data.copy(); bpy.context.collection.objects.link(wf)
wf.modifiers.new("W","WIREFRAME"); wf.modifiers["W"].thickness=0.00008; wf.modifiers["W"].use_replace=True
head.hide_render=True
scn.display.shading.single_color=(0.9,0.9,0.9)
for side in ("L","R"):
    c=Vector(tuple(float(x) for x in J[side]['center']))
    shot(c+Vector((0,-0.6,0)), fz, 0.045, os.path.join(D,"logs",f"fin_{side}_wire.png"), (1400,1000))
head.hide_render=False; wf.hide_render=True
# 全头正视 + 后视(查后脑完整)
hz=(1.67,0,1.71)
shot(Vector((0,-1.2,hz[2])), fz, 0.42, os.path.join(D,"logs","fin_head_front.png"))
shot(Vector((0,1.2,hz[2])), bz, 0.42, os.path.join(D,"logs","fin_head_back.png"))
print("shots done")
