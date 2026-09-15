import bpy, os, json, numpy as np
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01高模修复","输出","01_highpoly_repair.blend"))
obj=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
me=obj.data; nv=len(me.vertices); ne=len(me.edges)
co=np.empty(nv*3); me.vertices.foreach_get("co",co); co=co.reshape(nv,3)
ev=np.empty(ne*2,dtype=np.int32); me.edges.foreach_get("vertices",ev); ev=ev.reshape(ne,2)
for side in ("L","R"):
    c=J[side]["center"]; cy=float(c[1])
    rp=np.array([[float(p[0]),float(p[2])] for p in J[side]["rim_3d"]])
    L=np.linalg.norm(co[ev[:,0]]-co[ev[:,1]],axis=1)
    px=co[ev[:,0],0][:,None]-rp[None,:,0]; pz=co[ev[:,0],2][:,None]-rp[None,:,1]
    d=np.sqrt(px**2+pz**2).min(axis=1)
    front=co[ev[:,0],1] < cy+0.010
    print(f"{side} 输入网格({nv//1000}k顶点):")
    for lo,hi,nm in ((0,0.001,"0~1mm"),(0.001,0.003,"1~3mm"),(0.003,0.008,"3~8mm"),(0.008,0.02,"8~20mm")):
        m=front&(d>=lo)&(d<hi)
        if m.sum()>20:
            print(f"   {nm}: {int(m.sum())} 边, 中位 {np.median(L[m])*1000:.3f}mm, p10 {np.percentile(L[m],10)*1000:.3f}, p90 {np.percentile(L[m],90)*1000:.3f}")
