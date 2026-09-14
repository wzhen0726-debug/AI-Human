import bpy, os, json, numpy as np, bmesh, math
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
_d=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","iris_3ddfa.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
c=_d["L"]["center_3d"]; cv=Vector((float(c[0]),float(c[1]),float(c[2])))
_cR=_d["R"]["center_3d"]; cvR=Vector((float(_cR[0]),float(_cR[1]),float(_cR[2])))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
me=head.data
if bpy.context.mode!='OBJECT':
    bpy.context.view_layer.objects.active=head; bpy.ops.object.mode_set(mode='OBJECT')
# 面朝向材质
bm=bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
vn={}
for v in bm.verts:
    n=Vector((0,0,0))
    for f in v.link_faces: n+=f.normal
    vn[v.index]=n.normalized() if n.length>1e-12 else Vector((0,-1,0))
for f in bm.faces:
    avg=Vector((0,0,0))
    for v in f.verts: avg+=vn[v.index]
    f.material_index = 1 if (avg.length>1e-12 and f.normal.dot(avg.normalized())<0) else 0
bm.to_mesh(me); bm.free()
for m,col in ((0,(0.25,0.45,1,1)),(1,(1,0.05,0.05,1))):
    if len(me.materials)<=m: me.materials.append(bpy.data.materials.new(f"FO{m}"))
    me.materials[m].diffuse_color=col
scn=bpy.context.scene
scn.render.engine='BLENDER_WORKBENCH'
cam=bpy.data.objects.get("_fcam2") or bpy.data.objects.new("_fcam2", bpy.data.cameras.new("_fcam2"))
try: scn.collection.objects.link(cam)
except Exception: pass
scn.camera=cam; cam.data.type='ORTHO'
def shoot(nm,ax,az,sc_=0.045,cen=None):
    cen = cen or cv
    scn.render.resolution_x=1000; scn.render.resolution_y=760; cam.data.ortho_scale=sc_
    cam.location=(cen.x+math.sin(az)*0.25, cen.y-math.cos(az)*math.cos(ax)*0.25, cen.z+math.sin(ax)*0.25)
    d=Vector((cen.x,cen.y,cen.z))-Vector(cam.location)
    cam.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
    scn.render.filepath=os.path.join(D,"logs",nm); bpy.ops.render.render(write_still=True)
# ① 面朝向
scn.display.shading.light='FLAT'; scn.display.shading.color_type='MATERIAL'
shoot("fin_fo_front.png",0.0,0.0)
shoot("fin_fo_low.png",-0.32,-0.25)
# ② 材质着色(看形状)
scn.display.shading.light='STUDIO'; scn.display.shading.color_type='SINGLE'
scn.display.shading.single_color=(0.72,0.72,0.72)
try: scn.display.shading.show_cavity=True
except Exception: pass
shoot("fin_sh_front.png",0.0,0.0)
shoot("fin_sh_low.png",-0.32,-0.25)
shoot("fin_sh_zoom.png",-0.25,-0.30,0.020)
shoot("fin_fo_R.png",0.0,0.0,0.045,cvR)
shoot("fin_fo_R_low.png",-0.30,0.30,0.045,cvR)
shoot("fin_sh_R.png",0.0,0.0,0.045,cvR)
print("渲染完成")
