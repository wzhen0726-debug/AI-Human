import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table(); bm.normal_update()
# 与 _q_faceo 同判据: 顶点平均法线 → 面法线与之一致性
vn={}
for v in bm.verts:
    n=Vector((0,0,0))
    for f in v.link_faces: n+=f.normal
    vn[v.index]=n.normalized() if n.length>1e-12 else Vector((0,-1,0))
tot=0; bad=0; bad_in=0; bad_out=0
for s in ("L","R"):
    c=Vector(tuple(float(x) for x in J[s]['center']))
    P=np.array([[float(p[0]),float(p[2])] for p in J[s]['rim_3d']])
    bad=0; tot=0
    for f in bm.faces:
        cc=f.calc_center_median()
        if (cc-c).xz.length>0.030 or abs(cc.y-c.y)>0.06: continue
        d=float(np.sqrt((P[:,0]-cc.x)**2+(P[:,1]-cc.z)**2).min())
        if d>0.008: continue
        tot+=1
        avg=Vector((0,0,0))
        for v in f.verts: avg+=vn[v.index]
        if avg.length<1e-12: continue
        avg.normalize()
        if f.normal.dot(avg)<0: bad+=1
    print(f"{s}: 眼周8mm内 面法线与顶点平均法线相反(=错乱面) {bad}/{tot}")
bm.free()
