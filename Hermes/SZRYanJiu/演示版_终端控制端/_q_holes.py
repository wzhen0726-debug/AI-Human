import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
F=os.environ.get("CHK_BLEND"); J=os.environ.get("EYE_CONTOUR_JSON")
print("检查:", os.path.basename(F or ""))
bpy.ops.wm.open_mainfile(filepath=F)
Jd=json.load(open(J,encoding="utf-8"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.edges.ensure_lookup_table(); bm.verts.ensure_lookup_table()
oe=[e for e in bm.edges if len(e.link_faces)==1]
print(f"总开放边 {len(oe)}")
EYE={s:(Vector(tuple(float(x) for x in Jd[s]['center'])),
        np.array([[float(p[0]),float(p[2])] for p in Jd[s]['rim_3d']])) for s in ("L","R")}
inner=0; mid=0; far=0
for e in oe:
    v=e.verts[0].co
    dmin=min(float(np.sqrt((P[:,0]-v.x)**2+(P[:,1]-v.z)**2).min()) for _,(_,P) in EYE.items())
    if dmin<0.006: inner+=1
    elif dmin<0.030: mid+=1
    else: far+=1
print(f"开放边分布: 贴环(<6mm) {inner} | 中间(6~30mm) {mid} | 远处(>30mm) {far}")
bm.free()
