# 用户同倍率特写: 内眼角 + 下睑缘 (线框 + 实体)
import bpy, os, json, math
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
TAG=os.environ.get("SHOT_TAG","cur")
bpy.ops.wm.open_mainfile(filepath=os.environ.get("CHK_BLEND"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
scn=bpy.context.scene
scn.render.engine='BLENDER_WORKBENCH'
sh=scn.display.shading
sh.light='STUDIO'; sh.color_type='SINGLE'; sh.single_color=(0.72,0.72,0.74); sh.show_cavity=True
cam=bpy.data.objects.new("_c", bpy.data.cameras.new("_c")); scn.collection.objects.link(cam)
scn.camera=cam; cam.data.type='ORTHO'
wf=None
def shots(prefix, res=(1500,1100)):
    scn.render.resolution_x, scn.render.resolution_y = res
    for side,cx in (("L",-1),("R",1)):
        c=Vector(tuple(float(x) for x in J[side]['center']))
        for tag,off in (("incorner",(-0.014,0.000)),("lowlid",(-0.004,-0.006))):
            tgt=c+Vector((cx*off[0],0,off[1]))
            cam.location=tgt+Vector((0,-0.6,0.02)); cam.rotation_euler=(1.52,0,0)
            cam.data.ortho_scale=0.016
            scn.render.filepath=os.path.join(D,"logs",f"cz_{prefix}_{side}_{tag}.png"); bpy.ops.render.render(write_still=True)
shots(f"{TAG}_solid")
# 线框
wf=head.copy(); wf.data=head.data.copy(); bpy.context.collection.objects.link(wf)
wf.modifiers.new("W","WIREFRAME"); wf.modifiers["W"].thickness=0.00006; wf.modifiers["W"].use_replace=True
head.hide_render=True; scn.display.shading.single_color=(0.95,0.95,0.95)
shots(f"{TAG}_wire")
print("close shots done")
