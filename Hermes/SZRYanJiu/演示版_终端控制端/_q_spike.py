import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.edges.ensure_lookup_table(); bm.verts.ensure_lookup_table()
s="L"
c=Vector(tuple(float(x) for x in J[s]['center']))
P=np.array([[float(p[0]),float(p[2])] for p in J[s]['rim_3d']])
oe=[e for e in bm.edges if len(e.link_faces)==1 and (e.verts[0].co-c).xz.length<0.05 and e.verts[0].co.y<c.y+0.02]
deg={}
for e in oe:
    a,b=e.verts
    for x,y in ((a,b),(b,a)): deg.setdefault(x.index,[]).append(y.index)
st=[k for k in deg if len(deg[k])==2]
ring=[st[0]]; prev,cur=-1,st[0]
while True:
    cand=[n for n in deg[cur] if n!=prev]
    if not cand or cand[0]==ring[0]: break
    ring.append(cand[0]); prev,cur=cur,cand[0]
vm={v.index:v for v in bm.verts}
Q=np.array([vm[k].co[:] for k in ring])
# 找到最大 XZ 偏离点(相对 4mm 平滑基线)
d=np.linalg.norm(np.roll(Q,-1,axis=0)-Q,axis=1); spt=np.concatenate([[0],np.cumsum(d)[:-1]])
n=len(Q)
def sp(arr,win=0.004):
    out=np.zeros_like(arr)
    for i in range(n):
        ds=np.abs(spt-spt[i]); ds=np.minimum(ds,spt[-1]-ds)
        w=np.exp(-0.5*(ds/win)**2); out[i]=(arr*w).sum()/w.sum()
    return out
SX=sp(Q[:,0]); SZ=sp(Q[:,2])
dev=np.sqrt((Q[:,0]-SX)**2+(Q[:,2]-SZ)**2)
k=int(np.argmax(dev))
print(f"突刺点 idx{k} 弧长{spt[k]*1000:.1f}mm 位置({Q[k,0]*1000:.1f},{Q[k,1]*1000:.1f},{Q[k,2]*1000:.1f}) XZ偏离基线{dev[k]*1000:.3f}mm")
print("--- 该点与邻域(±6点) 到手描轮廓(XZ)距离 / 相对平滑基线 ---")
for j in range(k-6,k+7):
    i=j%n
    d2=float(np.sqrt((P[:,0]-Q[i,0])**2+(P[:,1]-Q[i,2])**2).min())
    dd=float(np.sqrt((Q[i,0]-SX[i])**2+(Q[i,2]-SZ[i])**2))
    mark="  <== 突刺" if i==k else ""
    print(f"   idx{i:3d} 弧长{spt[i]*1000:6.2f}mm 手描距{d2*1000:6.3f}mm 基线偏{dd*1000:6.3f}mm y={Q[i,1]*1000:.1f}{mark}")
bm.free()
