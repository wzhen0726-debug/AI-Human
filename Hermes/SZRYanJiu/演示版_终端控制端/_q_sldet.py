import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table(); bm.edges.ensure_lookup_table()
s="L"
c=Vector(tuple(float(x) for x in J[s]['center']))
P=np.array([[float(p[0]),float(p[2])] for p in J[s]['rim_3d']])
n=0
for f in bm.faces:
    cc=f.calc_center_median()
    if (cc-c).xz.length>0.030 or cc.y>c.y+0.02: continue
    d=float(np.sqrt((P[:,0]-cc.x)**2+(P[:,1]-cc.z)**2).min())
    if d>0.010: continue
    ls=sorted(e.calc_length() for e in f.edges)
    if ls[0]<=1e-9 or ls[-1]/ls[0]<=6: continue
    n+=1
    if n>3: break
    print(f"--- 细长面#{n}: {len(f.verts)}边 面积{f.calc_area()*1e6:.4f}mm2 长宽比{ls[-1]/ls[0]:.1f}")
    for i,v in enumerate(f.verts):
        dd=float(np.sqrt((P[:,0]-v.co.x)**2+(P[:,1]-v.co.z)**2).min())
        print(f"    v{i} ({v.co.x*1000:.2f},{v.co.y*1000:.2f},{v.co.z*1000:.2f}) 距轮廓{dd*1000:.3f}mm 面数{len(v.link_faces)} 度{len(v.link_edges)}")
    for e in f.edges:
        print(f"    边长{e.calc_length()*1000:.4f}mm")
bm.free()
