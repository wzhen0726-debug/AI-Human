import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
F=os.environ.get("CHK_BLEND"); J=os.environ.get("EYE_CONTOUR_JSON")
print("检查:", os.path.basename(F or ""))
bpy.ops.wm.open_mainfile(filepath=F)
Jd=json.load(open(J,encoding="utf-8"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table()
for s in ("L","R"):
    c=Vector(tuple(float(x) for x in Jd[s]['center']))
    P=np.array([[float(p[0]),float(p[2])] for p in Jd[s]['rim_3d']])
    tiny=0; zero=0; tot=0; sm=1e9
    for f in bm.faces:
        cc=f.calc_center_median()
        if (cc-c).xz.length>0.030 or cc.y>c.y+0.02: continue
        d=float(np.sqrt((P[:,0]-cc.x)**2+(P[:,1]-cc.z)**2).min())
        if d>0.010: continue
        tot+=1
        a=f.calc_area()*1e6
        sm=min(sm,a)
        if a<1e-6: zero+=1
        elif a<1e-3: tiny+=1
    print(f"{s}: 眼区10mm {tot}面 | 零面积(<1e-6 mm2) {zero} | 极小(<1e-3 mm2) {tiny} | 最小面积 {sm:.2e} mm2")
bm.free()
