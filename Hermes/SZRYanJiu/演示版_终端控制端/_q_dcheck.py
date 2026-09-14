import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
_d=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","iris_3ddfa.json"),encoding="utf-8"))
c=_d["L"]["center_3d"]; cv=Vector((float(c[0]),float(c[1]),float(c[2])))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
print("== 对象与材质 ==")
for o in bpy.data.objects:
    if o.type=='MESH':
        ms=[m.name if m else None for m in o.data.materials]
        print(f"  {o.name}: verts={len(o.data.vertices)} mats={ms}")
    else:
        print(f"  {o.name}: {o.type}")
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
eb=[x for x in bpy.data.objects if x.type=='MESH' and x is not head]
me=head.data
bm=bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
# 1) rim 环
ring=[v for v in bm.verts if any(len(e.link_faces)==1 for e in v.link_edges) and (v.co-cv).xz.length<0.030 and v.co.y<cv.y+0.010]
print(f"== 皮肤: rim 环顶点 {len(ring)} ==")
# 2) 眼周开放边(除 rim 环之外还有没有别的洞)
oe=[e for e in bm.edges if len(e.link_faces)==1 and (e.verts[0].co-cv).xz.length<0.030 and e.verts[0].co.y<cv.y+0.010]
print(f"   眼周开放边 {len(oe)}")
# 3) 补片区(dx -2..-10, dz -5..-8)的面数与法线方向
cnt=0; bad=0; nsum=Vector((0,0,0))
for f in bm.faces:
    cc=f.calc_center_median()
    dx=(cc.x-cv.x)*1000; dz=(cc.z-cv.z)*1000
    if -11<dx<-1 and -9<dz<-4 and abs(dx)>0:
        cnt+=1
        if f.normal.y>0.2: bad+=1
        nsum+=f.normal
print(f"== 补片区(dx-11..-1, dz-9..-4) 面数 {cnt}, 法线朝内(y>0.2) {bad} ==")
# 4) 眼球是否戳出 rim: 眼球顶点中, 位于 rim 的 XZ 多边形外且在这个区域内的
if eb:
    e=eb[0]
    poly=[]
    # 用 rim 环按角度排序近似多边形成 XZ
    pts=sorted([( (v.co.x-cv.x)*1000, (v.co.z-cv.z)*1000) for v in ring], key=lambda p: np.arctan2(p[1],p[0]))
    poly=np.array(pts)
    def inside(px,pz):
        x=px-cv.x*1000; z=pz-cv.z*1000
        return _pip(x,z,poly)
    def _pip(x,z,p):
        ins=False; n=len(p)
        for i in range(n):
            x1,z1=p[i]; x2,z2=p[(i+1)%n]
            if ((z1>z)!=(z2>z)) and (x < (x2-x1)*(z-z1)/(z2-z1+1e-12)+x1):
                ins=not ins
        return ins
    ev=[v.co for v in e.data.vertices]
    loc=[(v[0]-cv.x)*1000 for v in ev]; lz=[(v[2]-cv.z)*1000 for v in ev]; ly=[v[1] for v in ev]
    out=[(i,loc[i],lz[i],ly[i]) for i in range(len(ev)) if not inside(ev[i][0],ev[i][2])]
    reg=[o for o in out if -11<o[1]<-1 and -9<o[2]<-4]
    print(f"== 眼球: 顶点 {len(ev)}, 在 rim 外 {len(out)}, 其中左下补片区 {len(reg)} ==")
    if reg:
        ry=[r[3] for r in reg]
        print(f"   该区眼球顶点 y 范围 {min(ry)*1000:.1f}~{max(ry)*1000:.1f}mm (皮肤rim y ≈ {cv.y*1000:.1f})")
bm.free()
