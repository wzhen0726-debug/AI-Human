# rim 折痕强度: 环上每条边两侧面的二面角(>阈值=看得见的台阶/折痕)
import bpy, os, json, numpy as np, bmesh, math
from mathutils import Vector
F=os.environ.get("CHK_BLEND"); J=os.environ.get("EYE_CONTOUR_JSON")
print("检查:", os.path.basename(F or ""))
bpy.ops.wm.open_mainfile(filepath=F)
Jd=json.load(open(J,encoding="utf-8"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.edges.ensure_lookup_table(); bm.verts.ensure_lookup_table(); bm.normal_update()
for s in ("L","R"):
    c=Vector(tuple(float(x) for x in Jd[s]['center']))
    P=np.array([[float(p[0]),float(p[2])] for p in Jd[s]['rim_3d']])
    # 眼区所有面的折痕: 相邻两面夹角
    angs=[]
    for e in bm.edges:
        lf=e.link_faces
        if len(lf)!=2: continue
        mid=(e.verts[0].co+e.verts[1].co)*0.5
        if (mid-c).xz.length>0.020 or mid.y>c.y+0.02: continue
        d=float(np.sqrt((P[:,0]-mid.x)**2+(P[:,1]-mid.z)**2).min())
        if d>0.008: continue
        a=math.degrees(lf[0].normal.angle(lf[1].normal))
        angs.append((a, mid.copy(), e.calc_length()*1000))
    angs.sort(key=lambda x:-x[0])
    arr=np.array([a for a,_,_ in angs])
    if len(arr):
        print(f"{s}: 眼周8mm内双边 {len(arr)} | 折痕角 mean{arr.mean():.1f}° p90{np.percentile(arr,90):.1f}° p99{np.percentile(arr,99):.1f}° max{arr.max():.1f}°")
        for a,mid,el in angs[:5]:
            print(f"    {a:.0f}° @({mid.x*1000:.1f},{mid.y*1000:.1f},{mid.z*1000:.1f}) 边长{el:.2f}mm  相对眼中心 dx{(mid.x-c.x)*1000:+.1f} dz{(mid.z-c.z)*1000:+.1f}")
bm.free()
