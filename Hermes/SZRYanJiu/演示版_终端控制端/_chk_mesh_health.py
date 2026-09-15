# 网格健康检查(QR 前置): 洞的位置 / n-gon / 细长面 / 重复顶点 / 非流形
import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
F=os.environ.get("EYE_OUT_BLEND"); J=os.environ.get("EYE_CONTOUR_JSON")
print("检查:", os.path.basename(F or ""))
bpy.ops.wm.open_mainfile(filepath=F)
Jd=json.load(open(J,encoding="utf-8"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
me=head.data
bm=bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table(); bm.normal_update()
EYE={}
for side in ("L","R"):
    c=Jd[side]["center"]; EYE[side]=(Vector((float(c[0]),float(c[1]),float(c[2]))),
        np.array([[float(p[0]),float(p[2])] for p in Jd[side]["rim_3d"]]))
# ① 开放边: 按"离最近轮廓的距离"分布
oe=[e for e in bm.edges if len(e.link_faces)==1]
near=0; far=[]
for e in oe:
    v=e.verts[0].co
    dmin=1e9
    for side,(cv,P) in EYE.items():
        d=np.sqrt((P[:,0]-v.x)**2+(P[:,1]-v.z)**2).min()
        dmin=min(dmin,float(d))
    if dmin<0.006: near+=1
    else: far.append((v.copy(),dmin))
print(f"开放边 {len(oe)}: 眼周(<6mm) {near}, 远离眼 {len(far)}")
for v,d in far[:6]: print(f"   远离眼的开放边 @({v.x*1000:.1f},{v.y*1000:.1f},{v.z*1000:.1f}) 距轮廓{d*1000:.1f}mm")
# ② n-gon / ③ 细长面 / ⑤ 非流形
ng=0; el=0; ely=[]
for f in bm.faces:
    c=f.calc_center_median()
    dmin=min(float(np.sqrt((P[:,0]-c.x)**2+(P[:,1]-c.z)**2).min()) for cv,P in EYE.values())
    if dmin>0.008: continue
    if len(f.verts)>4: ng+=1
    ls=sorted([e.calc_length() for e in f.edges])
    if len(ls)>=2 and ls[-1]>1e-9 and ls[0]>1e-9 and ls[-1]/ls[0]>6: el+=1; ely.append((ls[-1]/ls[0],c))
nm=sum(1 for e in bm.edges if len(e.link_faces)>2)
print(f"眼周8mm内: n-gon(>4边) {ng} | 细长面(长宽比>6) {el} | 全局非流形边 {nm}")
for r,c in sorted(ely,reverse=True)[:4]: print(f"   细长面 长宽比{r:.1f} @dx{(c.x-float(Jd['L']['center'][0]))*1000:+.1f}")
# ④ 重复顶点(眼周)
import mathutils
for side,(cv,P) in EYE.items():
    vs=[v for v in bm.verts if np.sqrt((P[:,0]-v.co.x)**2+(P[:,1]-v.co.z)**2).min()<0.004]
    if not vs: continue
    from mathutils.kdtree import KDTree
    kd=KDTree(len(vs))
    for i,v in enumerate(vs): kd.insert(v.co,i)
    kd.balance()
    dup=0
    for i,v in enumerate(vs):
        for co,idx,dist in kd.find_range(v.co,0.00002):
            if idx!=i: dup+=1
    print(f"{side}: 眼周4mm内顶点 {len(vs)}, 距离<0.02mm 的重复对 {dup//2}")
bm.free()
