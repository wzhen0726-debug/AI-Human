import bpy, os, json, numpy as np, bmesh, math
from mathutils import Vector
F=os.environ.get("CHK_BLEND"); J=os.environ.get("EYE_CONTOUR_JSON")
print("检查:", os.path.basename(F or ""))
bpy.ops.wm.open_mainfile(filepath=F)
Jd=json.load(open(J,encoding="utf-8"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.edges.ensure_lookup_table(); bm.normal_update()
for s in ("L","R"):
    c=Vector(tuple(float(x) for x in Jd[s]['center']))
    P=np.array([[float(p[0]),float(p[2])] for p in Jd[s]['rim_3d']])
    rows=[]
    for e in bm.edges:
        lf=e.link_faces
        if len(lf)!=2: continue
        mid=(e.verts[0].co+e.verts[1].co)*0.5
        if (mid-c).xz.length>0.030 or mid.y>c.y+0.02: continue
        d=float(np.sqrt((P[:,0]-mid.x)**2+(P[:,1]-mid.z)**2).min())
        a=math.degrees(lf[0].normal.angle(lf[1].normal))
        if a>60: rows.append((a,d,mid.copy()))
    rows.sort(key=lambda x:-x[0])
    print(f"{s}: >60° 锐折痕 {len(rows)} 条")
    for a,d,mid in rows[:8]:
        print(f"    {a:.0f}° 距轮廓{d*1000:.2f}mm @({mid.x*1000:.1f},{mid.y*1000:.1f},{mid.z*1000:.1f}) dx{(mid.x-c.x)*1000:+.1f} dz{(mid.z-c.z)*1000:+.1f}")
bm.free()
