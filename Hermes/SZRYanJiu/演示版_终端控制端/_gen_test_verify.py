# 通用验收: 读环境变量 EYE_OUT_BLEND / EYE_CONTOUR_JSON, 输出全部关键判据
import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
F=os.environ.get("EYE_OUT_BLEND"); J=os.environ.get("EYE_CONTOUR_JSON")
print("验收文件:", os.path.basename(F or ""), "| 轮廓:", os.path.basename(J or ""))
bpy.ops.wm.open_mainfile(filepath=F)
Jd=json.load(open(J,encoding="utf-8"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table(); bm.normal_update()
for side in ("L","R"):
    d=Jd[side]; c=d["center"]; cv=Vector((float(c[0]),float(c[1]),float(c[2])))
    P=np.array([[float(p[0]),float(p[2])] for p in d["rim_3d"]])
    # rim 环(眼周开放边闭环)
    oe=[e for e in bm.edges if len(e.link_faces)==1 and (e.verts[0].co-cv).xz.length<0.05 and e.verts[0].co.y<cv.y+0.02]
    deg={}
    for e in oe:
        for a,b in ((e.verts[0],e.verts[1]),(e.verts[1],e.verts[0])):
            deg.setdefault(a.index,[]).append(b.index)
    d1=sum(1 for k in deg if len(deg[k])==1)
    # 沿环走一圈
    st=[k for k in deg if len(deg[k])==2]
    ring=[]; 
    if st:
        ring=[st[0]]; prev,cur=-1,st[0]
        while cur in deg:
            cand=[n for n in deg[cur] if n!=prev]
            if not cand: break
            nx=cand[0]
            if nx==ring[0]: break
            ring.append(nx); prev,cur=cur,nx
            if len(ring)>100000: break
    vmap={v.index:v for v in bm.verts}
    Q=np.array([[vmap[k].co.x,vmap[k].co.z] for k in ring]) if ring else np.zeros((0,2))
    # 折返
    folded=0
    if len(Q)>3:
        for i in range(len(Q)):
            a1,a2=Q[i],Q[(i+1)%len(Q)]
            for j in range(i+2,len(Q)):
                if (j+1)%len(Q)==i or j==(i+1)%len(Q): continue
                d1v=a2-a1; d2v=Q[(j+1)%len(Q)]-Q[j]
                den=d1v[0]*d2v[1]-d1v[1]*d2v[0]
                if abs(den)<1e-14: continue
                t=((Q[j][0]-a1[0])*d2v[1]-(Q[j][1]-a1[1])*d2v[0])/den
                u=((Q[j][0]-a1[0])*d1v[1]-(Q[j][1]-a1[1])*d1v[0])/den
                if 1e-9<t<1-1e-9 and 1e-9<u<1-1e-9: folded+=1
    # 转角/间距/轮廓偏差
    mx=0; sp=[]
    if len(ring)>3:
        pts=np.array([vmap[k].co[:] for k in ring])
        for i in range(len(pts)):
            a=pts[(i-1)%len(pts)]; b=pts[i]; cc=pts[(i+1)%len(pts)]
            v1=b-a; v2=cc-b
            if np.linalg.norm(v1)>1e-9 and np.linalg.norm(v2)>1e-9:
                ang=np.degrees(np.arccos(np.clip(np.dot(v1,v2)/(np.linalg.norm(v1)*np.linalg.norm(v2)),-1,1)))
                mx=max(mx,ang)
            sp.append(np.linalg.norm(v2)*1000)
        dv=[np.sqrt(((P[:,0]-vmap[k].co.x)**2+(P[:,1]-vmap[k].co.z)**2).min()) for k in ring]
    else:
        dv=[0]
    # 眼周反向面
    back=0; cnt=0
    for f in bm.faces:
        ccz=f.calc_center_median()
        if abs(ccz.y-float(c[1]))>0.09: continue
        dd=np.sqrt((P[:,0]-ccz.x)**2+(P[:,1]-ccz.z)**2).min()
        if dd>0.0025: continue
        cnt+=1
        if f.normal.y>0.05: back+=1
    print(f"  {side}: 环{len(ring)}顶点 1度顶点{d1} | 折返{folded} | 转角max{mx:.1f}° | "
          f"间距中位{np.median(sp):.3f}mm | 轮廓偏差中位{np.median(dv)*1000:.3f}/max{max(dv)*1000:.3f}mm | 眼周反面 {back}/{cnt}")
bm.free()
