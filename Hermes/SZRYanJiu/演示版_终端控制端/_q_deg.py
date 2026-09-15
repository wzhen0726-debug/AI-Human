import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
F=os.environ.get("CHK_BLEND"); J=os.environ.get("EYE_CONTOUR_JSON")
bpy.ops.wm.open_mainfile(filepath=F)
Jd=json.load(open(J,encoding="utf-8"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.edges.ensure_lookup_table(); bm.verts.ensure_lookup_table()
for s in ("L","R"):
    c=Vector(tuple(float(x) for x in Jd[s]['center']))
    P=np.array([[float(p[0]),float(p[2])] for p in Jd[s]['rim_3d']])
    oe=[e for e in bm.edges if len(e.link_faces)==1 and (e.verts[0].co-c).xz.length<0.05 and e.verts[0].co.y<c.y+0.02]
    deg={}
    for e in oe:
        a,b=e.verts
        for x,y in ((a,b),(b,a)):
            deg.setdefault((x.co.x,x.co.y,x.co.z),[]).append((y.co.x,y.co.y,y.co.z))
    n1=sum(1 for k in deg if len(deg[k])==1)
    n3=sum(1 for k in deg if len(deg[k])>=3)
    # 是否单一闭环
    closed = (n1==0)
    print(f"{s}: 边界边{len(oe)} 端点{len(deg)} | 1度(断开){n1} | >=3度(分叉){n3} | {'单一闭环 ✓' if closed and n3==0 else '有开口/分叉 ✗'}")
    if n1:
        for k in deg:
            if len(deg[k])==1:
                print(f"   断点 @({k[0]*1000:.1f},{k[1]*1000:.1f},{k[2]*1000:.1f})")
                break
bm.free()
