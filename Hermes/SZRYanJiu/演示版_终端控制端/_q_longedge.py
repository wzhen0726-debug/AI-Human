import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
F=os.environ.get("CHK_BLEND"); J=os.environ.get("EYE_CONTOUR_JSON")
bpy.ops.wm.open_mainfile(filepath=F)
Jd=json.load(open(J,encoding="utf-8"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.edges.ensure_lookup_table()
tot=0; inband=0; outband=0; mx=0
for s in ("L","R"):
    c=Vector((float(Jd[s]['center'][0]),float(Jd[s]['center'][1]),float(Jd[s]['center'][2])))
    P=np.array([[float(p[0]),float(p[2])] for p in Jd[s]['rim_3d']])
    for e in bm.edges:
        a,b=e.verts
        ca=(a.co+b.co)/2
        if (ca-c).xz.length>0.030 or ca.y>c.y+0.02: continue
        d=float(np.sqrt((P[:,0]-ca.x)**2+(P[:,1]-ca.z)**2).min())
        if d>0.008: continue
        L=e.calc_length()
        if L<0.003: continue
        tot+=1; mx=max(mx,L)
        # 该边两端点到轮廓的距离
        da=float(np.sqrt((P[:,0]-a.co.x)**2+(P[:,1]-a.co.z)**2).min())
        db=float(np.sqrt((P[:,0]-b.co.x)**2+(P[:,1]-b.co.z)**2).min())
        if max(da,db)<0.004: inband+=1
        else: outband+=1
print(f"{os.path.basename(F)}: 眼周>3mm边 {tot} (两端都贴轮廓 {inband} / 有远端 {outband}) 最长{mx*1000:.2f}mm")
bm.free()
