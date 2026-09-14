import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
_d=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","iris_3ddfa.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
c=_d["L"]["center_3d"]; cv=Vector((float(c[0]),float(c[1]),float(c[2])))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
oe=[e for e in bm.edges if len(e.link_faces)==1 and (e.verts[0].co-cv).xz.length<0.030 and e.verts[0].co.y<cv.y+0.010]
vs=set()
for e in oe:
    vs.add(e.verts[0]); vs.add(e.verts[1])
ang=sorted(np.degrees(np.arctan2((v.co.z-cv.z)*1000,(v.co.x-cv.x)*1000)) for v in vs)
print(f"边界顶点 {len(vs)}, 角度范围 {ang[0]:.0f}..{ang[-1]:.0f}")
hist=np.histogram([a%360 for a in ang], bins=12, range=(0,360))[0]
print("按角度分12桶(0=右,90=上,180=左,270=下):", list(hist))
print("洞内是否有面: ", end="")
inner=[f for f in bm.faces if (f.calc_center_median()-cv).xz.length<0.010 and f.calc_center_median().y<cv.y]
print(len(inner))
bm.free()
