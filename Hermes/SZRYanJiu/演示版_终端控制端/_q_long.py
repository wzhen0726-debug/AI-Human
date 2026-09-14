import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
from collections import defaultdict
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
_d=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","iris_3ddfa.json"),encoding="utf-8"))
c=_d["L"]["center_3d"]; cv=Vector((float(c[0]),float(c[1]),float(c[2])))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
o=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
ring=[v for v in bm.verts if any(len(e.link_faces)==1 for e in v.link_edges) and (v.co-cv).xz.length<0.030 and v.co.y<cv.y+0.010]
print(f"环顶点 {len(ring)}")
seg=[]
for v in ring:
    for e in v.link_edges:
        if len(e.link_faces)==1 and (e.other_vert(v).co-cv).xz.length<0.030:
            a=v.co; b=e.other_vert(v).co
            seg.append(((a-b).length*1000, (a.x-cv.x)*1000, (a.z-cv.z)*1000, (b.x-cv.x)*1000, (b.z-cv.z)*1000))
seg.sort(reverse=True)
for s in seg[:6]:
    print(f"  边长{s[0]:.3f}mm  {s[1]:+.2f},{s[2]:+.2f} -> {s[3]:+.2f},{s[4]:+.2f}")
bm.free()
