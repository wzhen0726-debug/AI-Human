import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
_d=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","iris_3ddfa.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
for side in ("L","R"):
    c=_d[side]["center_3d"]; cv=Vector((float(c[0]),float(c[1]),float(c[2])))
    oe=[e for e in bm.edges if len(e.link_faces)==1 and (e.verts[0].co-cv).xz.length<0.030 and e.verts[0].co.y<cv.y+0.010]
    deg={}
    for e in oe:
        for a,b in ((e.verts[0],e.verts[1]),(e.verts[1],e.verts[0])):
            deg.setdefault(a.index,[]).append(b.index)
    d1=[k for k in deg if len(deg[k])==1]
    d3=[k for k in deg if len(deg[k])>=3]
    print(f"{side}: 开放边 {len(oe)}, 1度顶点 {len(d1)}, >=3度 {len(d3)}")
    for k in d1[:6]:
        v=bm.verts[k]
        print(f"   1度 @ dx{(v.co.x-cv.x)*1000:+.2f} dz{(v.co.z-cv.z)*1000:+.2f} y{v.co.y*1000:.1f} 距{(v.co-cv).xz.length*1000:.2f}mm")
    for k in d3[:4]:
        v=bm.verts[k]
        print(f"   {len(deg[k])}度 @ dx{(v.co.x-cv.x)*1000:+.2f} dz{(v.co.z-cv.z)*1000:+.2f} y{v.co.y*1000:.1f}")
    # 每条1度顶点连出去的边另一端
    for k in d1[:6]:
        o=deg[k][0]; v=bm.verts[k]; w=bm.verts[o]
        print(f"     边: dx{(v.co.x-cv.x)*1000:+.2f},{(v.co.z-cv.z)*1000:+.2f} -> dx{(w.co.x-cv.x)*1000:+.2f},{(w.co.z-cv.z)*1000:+.2f} 长{(v.co-w.co).length*1000:.3f}mm")
bm.free()
