import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.edges.ensure_lookup_table(); bm.verts.ensure_lookup_table(); bm.normal_update()
for s in ("L","R"):
    c=Vector(tuple(float(x) for x in J[s]['center']))
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
    P=np.array([vm[k].co[:] for k in ring])
    n=len(P)
    # 弧长 + 转角 + 位移到弦的"凸起度"
    d=np.linalg.norm(np.roll(P,-1,axis=0)-P,axis=1); spt=np.concatenate([[0],np.cumsum(d)[:-1]])
    turn=np.zeros(n)
    for i in range(n):
        a=P[(i-1)%n]; b=P[i]; cc=P[(i+1)%n]
        v1=b-a; v2=cc-b
        if np.linalg.norm(v1)>1e-9 and np.linalg.norm(v2)>1e-9:
            turn[i]=np.degrees(np.arccos(np.clip(np.dot(v1,v2)/(np.linalg.norm(v1)*np.linalg.norm(v2)),-1,1)))
    # 平滑参考: 对 XZ 做低频重建(波长>=4mm), 看每个点偏离多少
    def smooth_prof(arr, win_mm=4.0):
        out=np.zeros_like(arr)
        for i in range(n):
            ds=np.abs(spt - spt[i]); ds=np.minimum(ds, spt[-1]-ds)
            w=np.exp(-0.5*(ds/ (win_mm/1000.0))**2)
            out[i]=(arr*w).sum()/w.sum()
        return out
    SX=smooth_prof(P[:,0]); SZ=smooth_prof(P[:,2]); SY=smooth_prof(P[:,1])
    dev=np.sqrt((P[:,0]-SX)**2+(P[:,2]-SZ)**2)
    dev3=np.sqrt((P[:,0]-SX)**2+(P[:,1]-SY)**2+(P[:,2]-SZ)**2)
    top=np.argsort(-dev3)[:6]
    print(f"{s}: 环{n}点 周长{spt[-1]*1000:.1f}mm | 转角 mean{turn.mean():.1f}/max{turn.max():.1f} | 偏离平滑基线(4mm) mean{dev3.mean()*1000:.3f} max{dev3.max()*1000:.3f}mm")
    # 突刺成分: XZ 平面内偏移 vs 深度(Y)偏移
    devY=np.abs(P[:,1]-SY)
    k=int(np.argmax(dev3))
    print(f"    最大突刺分解: XZ偏{dev[k]*1000:.3f}mm | 深度Y偏{devY[k]*1000:.3f}mm | 位置x=( {P[k,0]*1000:.1f},{P[k,2]*1000:.1f}) y={P[k,1]*1000:.1f}")
    hi=[i for i in range(n) if turn[i]>28]
    print(f"    转角>28° 的点数: {len(hi)}", " ".join(f"[{spt[i]*1000:.1f}mm:{turn[i]:.0f}°:xz({P[i,0]*1000:.1f},{P[i,2]*1000:.1f}):Y{P[i,1]*1000:.0f}:XZ偏{dev[i]*1000:.2f}]" for i in hi[:8]))
    for i in top:
        print(f"    凸起@弧长{spt[i]*1000:.1f}mm 3D偏{dev3[i]*1000:.3f}mm 转角{turn[i]:.0f}° xz=({P[i,0]*1000:.1f},{P[i,2]*1000:.1f}) y={P[i,1]*1000:.1f}")
bm.free()
