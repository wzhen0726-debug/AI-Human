# 查 rim 环在 XZ 上是否自交(折返小尖) + 用 3D 判据查自交
import bpy, os, json
import numpy as np, bmesh
from mathutils import Vector
from collections import defaultdict
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
_d=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","iris_3ddfa.json"),encoding="utf-8"))
C={k:np.array(_d[k]["center_3d"],dtype=float) for k in ("L","R")}
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
o=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
for side,c in C.items():
    cv=Vector((float(c[0]),float(c[1]),float(c[2])))
    adj=defaultdict(list)
    for e in bm.edges:
        if len(e.link_faces)==1 and (e.verts[0].co-cv).xz.length<0.030 and e.verts[0].co.y<cv.y+0.010:
            adj[e.verts[0].index].append(e.verts[1].index); adj[e.verts[1].index].append(e.verts[0].index)
    st=[k for k in adj if len(adj[k])==2]
    ring=[st[0]]; prev,cur=-1,st[0]
    while True:
        cand=[n for n in adj[cur] if n!=prev]
        if not cand: break
        n=cand[0]
        if n==ring[0]: break
        ring.append(n); prev,cur=cur,n
        if len(ring)>100000: break
    Q=np.array([[bm.verts[i].co.x,bm.verts[i].co.z] for i in ring])*1000
    N=len(Q)
    def seg_int(p1,p2,p3,p4):
        d1=p2-p1; d2=p4-p3
        den=d1[0]*d2[1]-d1[1]*d2[0]
        if abs(den)<1e-12: return None
        t=((p3[0]-p1[0])*d2[1]-(p3[1]-p1[1])*d2[0])/den
        u=((p3[0]-p1[0])*d1[1]-(p3[1]-p1[1])*d1[0])/den
        if -1e-9<=t<=1+1e-9 and -1e-9<=u<=1+1e-9: return (t,u)
        return None
    hits=[]
    for i in range(N):
        a1,a2=Q[i],Q[(i+1)%N]
        for j in range(i+2,N):
            if (j+1)%N==i or j==(i+1)%N: continue
            b1,b2=Q[j],Q[(j+1)%N]
            r=seg_int(a1,a2,b1,b2)
            if r: hits.append((i,j,r))
    print(f"{side}: 环{N}顶点 XZ自交对数 {len(hits)}")
    for i,j,r in hits[:5]:
        pt=Q[i]+(Q[(i+1)%N]-Q[i])*r[0]
        print(f"   边{i}-{i+1} × 边{j}-{j+1} 交点({pt[0]-c[0]*1000:+.2f},{pt[1]-c[2]*1000:+.2f})mm 相对眼中心; 环上间隔{j-i}个顶点")
bm.free()
