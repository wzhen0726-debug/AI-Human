# 缝合带宽度诊断: 每个"细长面"的两侧(到轮廓/到外边界)距离
import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table(); bm.edges.ensure_lookup_table()
for s in ("L","R"):
    c=Vector(tuple(float(x) for x in J[s]['center']))
    P=np.array([[float(p[0]),float(p[2])] for p in J[s]['rim_3d']])
    # 环上顶点
    oe=[e for e in bm.edges if len(e.link_faces)==1 and (e.verts[0].co-c).xz.length<0.05 and e.verts[0].co.y<c.y+0.02]
    ring_v=set()
    for e in oe: ring_v.add(e.verts[0].index); ring_v.add(e.verts[1].index)
    # 细长面: 统计其"贴环边"到环上最近非共边顶点的距离 = 带宽度
    widths=[]
    for f in bm.faces:
        cc=f.calc_center_median()
        if (cc-c).xz.length>0.030 or cc.y>c.y+0.02: continue
        d=float(np.sqrt((P[:,0]-cc.x)**2+(P[:,1]-cc.z)**2).min())
        if d>0.010: continue
        ls=sorted(e.calc_length() for e in f.edges)
        if ls[0]<=1e-9 or ls[-1]/ls[0]<=6: continue
        # 该面有几条贴环边(两端都在环上)
        on=[]
        for e in f.edges:
            if e.verts[0].index in ring_v and e.verts[1].index in ring_v: on.append(e)
        if not on: continue
        e0=on[0]
        # 到环上"非本边端点"的最近距离 = 带宽
        dvmin=1e9
        for v in bm.verts:
            if v.index not in ring_v: continue
            if v.index in (e0.verts[0].index, e0.verts[1].index): continue
            _ec=(e0.verts[0].co+e0.verts[1].co)*0.5
            dd=(v.co-_ec).length
            if dd<dvmin: dvmin=dd
        widths.append(dvmin*1000)
    widths=np.array(widths)
    if len(widths):
        print(f"{s}: 细长面 {len(widths)} 个 | 带宽(到环上其它点) 中位{np.median(widths):.3f}mm p10={np.percentile(widths,10):.3f} p90={np.percentile(widths,90):.3f} max={widths.max():.3f}")
    else:
        print(f"{s}: 无细长面")
bm.free()
