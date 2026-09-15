import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
me=head.data
print("mesh 属性:", [a.name+":"+a.domain+"/"+a.data_type for a in me.attributes][:10])
print("has_custom_normal:", "custom_normal" in me.attributes, "| 顶点数", len(me.vertices), "| 面", len(me.polygons))
c=J["R"]["center"]; cv=Vector((float(c[0]),float(c[1]),float(c[2])))
P=np.array([[float(p[0]),float(p[2])] for p in J["R"]["rim_3d"]])
# 取 R 眼 rim 0.3~1.5mm 的面, 比较 面法线(绕序) vs 环法线(显示用)
if bpy.context.mode!='OBJECT':
    bpy.context.view_layer.objects.active=head; bpy.ops.object.mode_set(mode='OBJECT')
me.calc_loop_triangles()
cnt=0; wind_back=0; loop_back=0
for p in me.polygons:
    cc=p.center
    if abs(cc.y-(-0.106))>0.06: continue
    d=np.sqrt((P[:,0]-cc.x)**2+(P[:,1]-cc.z)**2).min()
    if not (0.0003<=d<0.0015): continue
    cnt+=1
    if p.normal.y>0.0: wind_back+=1
    # 环法线均值(即显示/着应用的)
    ln=Vector((0,0,0))
    for li in p.loop_indices:
        ln+=me.loops[li].normal
    if ln.length>1e-9 and ln.normalized().y>0.0: loop_back+=1
print(f"R rim 0.3~1.5mm 面 {cnt}: 绕序法线朝后 {wind_back}, 环法线(custom,显示用)朝后 {loop_back}")
