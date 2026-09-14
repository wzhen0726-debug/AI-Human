# 查: 眼周(rim 外侧 6mm 内)有多少面是"反面"(法线与邻面朝外方向相反) + 退化/扭曲面
import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
_d=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","iris_3ddfa.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
for side in ("L","R"):
    c=_d[side]["center_3d"]; cv=Vector((float(c[0]),float(c[1]),float(c[2])))
    ring=[v for v in bm.verts if any(len(e.link_faces)==1 for e in v.link_edges) and (v.co-cv).xz.length<0.030 and v.co.y<cv.y+0.010]
    # 顶点平均法线(用周围面)
    def vnorm(v):
        n=Vector((0,0,0))
        for f in v.link_faces: n+=f.normal
        return n.normalized() if n.length>1e-12 else Vector((0,-1,0))
    # 以顶点法线(朝外)为基准: 面法线与顶点平均法线夹角 >90° = 反面
    bad=[]; degen=0; big=0
    for f in bm.faces:
        cc=f.calc_center_median()
        d=(cc-cv).xz.length
        if d>0.030 or cc.y>cv.y+0.010: continue
        vs=[vnorm(v) for v in f.verts]
        avg=Vector((0,0,0))
        for v in vs: avg+=v
        if avg.length<1e-12: continue
        avg.normalize()
        if f.normal.dot(avg)<0.0: bad.append((f, d*1000))
        a=f.calc_area()
        if a<1e-14: degen+=1
        if a>1e-7: big+=1
    # 按距眼中心距离统计反面面
    dists=[b[1] for b in bad]
    print(f"{side}: 眼周面 反面向 {len(bad)} 个; 距离眼中心 min{min(dists) if dists else 0:.1f}/max{max(dists) if dists else 0:.1f}mm")
    if bad:
        bad.sort(key=lambda t:t[1])
        for f,dd in bad[:8]:
            cc=f.calc_center_median()
            print(f"    反面 @ dx{(cc.x-cv.x)*1000:+.2f} dz{(cc.z-cv.z)*1000:+.2f} y{cc.y*1000:.1f} 距{dd:.2f}mm")
    print(f"   退化面(面积≈0) {degen}, 面积>1e-7(可疑大面) {big}")
bm.free()
