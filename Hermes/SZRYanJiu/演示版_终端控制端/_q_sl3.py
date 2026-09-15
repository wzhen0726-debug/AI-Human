import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
F=os.environ.get("CHK_BLEND"); J=os.environ.get("EYE_CONTOUR_JSON")
bpy.ops.wm.open_mainfile(filepath=F)
Jd=json.load(open(J,encoding="utf-8"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table()
EYE=[(Vector((float(Jd[s]['center'][0]),float(Jd[s]['center'][1]),float(Jd[s]['center'][2]))),
      np.array([[float(p[0]),float(p[2])] for p in Jd[s]['rim_3d']])) for s in ("L","R")]
cls={"<1mm":0,"1-2mm":0,">2mm":0}; mx=0; ng=0; ngd=[]
for f in bm.faces:
    c=f.calc_center_median()
    if min((c-cv).xz.length for cv,P in EYE)>0.030 or c.y>min(cv.y for cv,P in EYE)+0.02: continue
    d=min(float(np.sqrt((P[:,0]-c.x)**2+(P[:,1]-c.z)**2).min()) for cv,P in EYE)
    if d>0.008: continue
    if len(f.verts)>4: ng+=1; ngd.append((d,c.copy()))
    ls=sorted(e.calc_length() for e in f.edges)
    if ls[0]>1e-9 and ls[-1]/ls[0]>6:
        L=ls[-1]; mx=max(mx,L)
        cls["<1mm" if L<0.001 else ("1-2mm" if L<0.002 else ">2mm")]+=1
print(f"眼周8mm: 细长面(>6) 按长边分档 {cls} | 最长{mx*1000:.2f}mm | n-gon {ng}")
for d,c in ngd[:4]: print(f"   n-gon @({c.x*1000:.1f},{c.y*1000:.1f},{c.z*1000:.1f}) 距轮廓{d*1000:.2f}mm")
bm.free()
