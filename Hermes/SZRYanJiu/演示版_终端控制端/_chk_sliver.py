# 细长面/非流形/远距开放边 的"归属"诊断: 可对任意 blend 跑
import bpy, os, json, numpy as np, bmesh
F=os.environ.get("CHK_BLEND"); J=os.environ.get("EYE_CONTOUR_JSON")
print("检查:", os.path.basename(F or ""))
bpy.ops.wm.open_mainfile(filepath=F)
Jd=json.load(open(J,encoding="utf-8"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
EYE={s:(float(Jd[s]['center'][0]), np.array([[float(p[0]),float(p[2])] for p in Jd[s]['rim_3d']])) for s in ("L","R")}
sl=[]
for f in bm.faces:
    c=f.calc_center_median()
    if min(np.sqrt((P[:,0]-c.x)**2+(P[:,1]-c.z)**2).min() for _,(_,P) in EYE.items())>0.008: continue
    ls=sorted(e.calc_length() for e in f.edges)
    if ls[0]>1e-9 and ls[-1]/ls[0]>6: sl.append((ls[-1]/ls[0], ls[0], ls[-1], c.copy(), len(f.verts)))
nm=[e for e in bm.edges if len(e.link_faces)>2]
oe=[e for e in bm.edges if len(e.link_faces)==1]
farn=0
for e in oe:
    v=e.verts[0].co
    if min(np.sqrt((P[:,0]-v.x)**2+(P[:,1]-v.z)**2).min() for _,(_,P) in EYE.items())>0.006: farn+=1
print(f"细长面(>6): {len(sl)} | 非流形边: {len(nm)} | 开放边: {len(oe)} (远离眼 {farn})")
for r,s0,s1,c,nv in sorted(sl,reverse=True)[:5]:
    ds=' '.join(f"{s}:dx{(c.x-EYE[s][0])*1000:+.1f},dy{(c.y-float(Jd[s]['center'][1]))*1000:+.1f}" for s in EYE)
    print(f"   比{r:.1f} 短{s0*1000:.4f}长{s1*1000:.3f}mm {nv}边 [{ds}]")
for e in nm[:5]:
    c=(e.verts[0].co+e.verts[1].co)/2
    print(f"   非流形 @({c.x*1000:.0f},{c.y*1000:.0f},{c.z*1000:.0f}) 面数{len(e.link_faces)} 距轮廓{min(np.sqrt((P[:,0]-c.x)**2+(P[:,1]-c.z)**2).min() for _,(_,P) in EYE.items())*1000:.1f}mm")
bm.free()
