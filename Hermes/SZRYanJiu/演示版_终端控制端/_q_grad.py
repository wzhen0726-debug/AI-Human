import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table()
for s in ("L","R"):
    c=Vector(tuple(float(x) for x in J[s]['center']))
    P=np.array([[float(p[0]),float(p[2])] for p in J[s]['rim_3d']])
    bands={}
    for f in bm.faces:
        cc=f.calc_center_median()
        if (cc-c).xz.length>0.030 or cc.y>c.y+0.02: continue
        d=float(np.sqrt((P[:,0]-cc.x)**2+(P[:,1]-cc.z)**2).min())
        if d>0.006: continue
        key = "0~0.8mm" if d<0.0008 else ("0.8~1.6mm" if d<0.0016 else ("1.6~3mm" if d<0.003 else "3~6mm"))
        ls=sorted(e.calc_length() for e in f.edges)
        if ls[0]<=0: continue
        bands.setdefault(key,[]).append((np.median(ls), ls[-1]/ls[0], len(f.verts)))
    print(f"{s}: 距轮廓分档 (面数 / 中位边长mm / 长宽比中位)")
    for k in ("0~0.8mm","0.8~1.6mm","1.6~3mm","3~6mm"):
        v=bands.get(k,[])
        if not v: continue
        arr=np.array([x[0] for x in v]); asp=np.array([x[1] for x in v]); nq=sum(1 for x in v if x[2]>4)
        print(f"   {k}: {len(v)}面 | 中位边长{np.median(arr)*1000:.3f}mm | 长宽比中位{np.median(asp):.1f} p90={np.percentile(asp,90):.1f} max={asp.max():.1f} | >4边{nq}")
bm.free()
