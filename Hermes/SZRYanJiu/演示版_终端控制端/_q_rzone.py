import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
me=head.data
bm=bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.normal_update()
# 红=法线朝后(normal.y>0, 与用户正视口面朝向显示同判据), 蓝=正常
for f in bm.faces: f.material_index = 1 if f.normal.y > 0.0 else 0
# 标记两簇(放大观察): 把它们涂绿
for side,pt in (("L",(-21.0,-118.1,1676.0)),("R",(52.2,-99.0,1667.0))):
    pv=Vector(pt)
    for f in bm.faces:
        if (f.calc_center_median()-pv).length<0.004: f.material_index=2
bm.to_mesh(me); bm.free()
for i,(nm,col) in enumerate((("front",(0.25,0.45,1,1)),("back",(1,0.12,0.12,1)),("mark",(0,1,0,1)))):
    if len(me.materials)<=i: me.materials.append(bpy.data.materials.new(f"m{i}"))
    me.materials[i].use_nodes=False; me.materials[i].diffuse_color=col
scn=bpy.context.scene
scn.render.engine='BLENDER_WORKBENCH'
scn.display.shading.color_type='MATERIAL'
scn.display.shading.light='FLAT'
scn.render.resolution_x=1000; scn.render.resolution_y=800
cam=bpy.data.objects.get("_fc") or bpy.data.objects.new("_fc", bpy.data.cameras.new("_fc"))
if cam.name not in scn.collection.objects: scn.collection.objects.link(cam)
scn.camera=cam; cam.data.type='ORTHO'
scn.render.film_transparent=False
for side in ("L","R"):
    c=Vector(tuple(float(x) for x in J[side]['center']))
    cam.data.ortho_scale=0.055
    cam.location=c+Vector((0,-0.5,0)); cam.rotation_euler=(1.5707963,0,0)
    scn.render.filepath=os.path.join(D,"logs",f"zone_{side}_front.png"); bpy.ops.render.render(write_still=True)
    # 斜 30° 看深度
    import math
    a=math.radians(35)
    cam.location=c+Vector((0.5*math.sin(a),-0.5*math.cos(a),0.02)); cam.rotation_euler=(1.5707963,0,a)
    scn.render.filepath=os.path.join(D,"logs",f"zone_{side}_side.png"); bpy.ops.render.render(write_still=True)
print("done")
