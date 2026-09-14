import bpy, os, json, numpy as np, bmesh, math
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
_d=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","iris_3ddfa.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
c=_d["L"]["center_3d"]; cv=Vector((float(c[0]),float(c[1]),float(c[2])))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
me=head.data
bpy.context.view_layer.objects.active=head
if bpy.context.mode!='OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
# 用顶点平均法线判定每面朝向 → 材质0=蓝(正面) 1=红(反面)
bm=bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
vn={}
for v in bm.verts:
    n=Vector((0,0,0))
    for f in v.link_faces: n+=f.normal
    vn[v.index]=n.normalized() if n.length>1e-12 else Vector((0,-1,0))
bad=0
for f in bm.faces:
    avg=Vector((0,0,0))
    for v in f.verts: avg+=vn[v.index]
    if avg.length<1e-12: continue
    avg.normalize()
    f.material_index = 1 if f.normal.dot(avg)<0 else 0
    if f.material_index==1: bad+=1
bm.to_mesh(me); bm.free()
print("反面向(全头)", bad)
for m,nm,col in ((0,"front",(0.2,0.4,1,1)),(1,"back",(1,0.1,0.1,1))):
    if len(me.materials)<=m: me.materials.append(bpy.data.materials.new(f"M{m}"))
    me.materials[m].diffuse_color=col
scn=bpy.context.scene
scn.render.engine='BLENDER_WORKBENCH'
scn.display.shading.light='FLAT'; scn.display.shading.color_type='MATERIAL'
cam=bpy.data.objects.get("_focam") or bpy.data.objects.new("_focam", bpy.data.cameras.new("_focam"))
try: scn.collection.objects.link(cam)
except Exception: pass
scn.camera=cam; cam.data.type='ORTHO'
cR=_d["R"]["center_3d"]; cvR=Vector((float(cR[0]),float(cR[1]),float(cR[2])))
mid=(cv+cvR)*0.5
for nm,ax,az,sc_,cen in (("fo_both_front.png",0.0,0.0,0.13,mid),("fo_both_low.png",-0.25,0.0,0.13,mid),("fo_Llow_zoom.png",-0.30,-0.35,0.030,cv)):
    scn.render.resolution_x=900; scn.render.resolution_y=700; cam.data.ortho_scale=sc_
    cam.location=(cen.x+math.sin(az)*0.25, cen.y-math.cos(az)*math.cos(ax)*0.25, cen.z+math.sin(ax)*0.25)
    d=Vector((cen.x,cen.y,cen.z))-Vector(cam.location)
    cam.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
    scn.render.filepath=os.path.join(D,"logs",nm); bpy.ops.render.render(write_still=True)
print("渲染完成")
