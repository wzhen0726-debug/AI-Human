# 眼球 vs 头部 穿插检测(此前只查了头自身)
import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
F=os.environ.get("CHK_BLEND") or os.path.join(D,"01a眼窝眼球","输出","01_2_eyeball_placed.blend")
print("检查:", os.path.basename(F))
bpy.ops.wm.open_mainfile(filepath=F)
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
objs=[o for o in bpy.data.objects if o.type=='MESH']
head=max(objs,key=lambda x:len(x.data.vertices))
eyes=[o for o in objs if o is not head]
print("对象:", [(o.name,len(o.data.vertices)) for o in objs])
# 头: 眼区面
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table()
hv=[]; hp=[]; vm={}
EYE={s:Vector(tuple(float(x) for x in J[s]['center'])) for s in ("L","R")}
for f in bm.faces:
    c=f.calc_center_median()
    if min((c-cv0).xz.length for cv0 in EYE.values())>0.035 or c.y>max(cv0.y for cv0 in EYE.values())+0.03: continue
    idx=[]
    for v in f.verts:
        if v.index not in vm:
            vm[v.index]=len(hv); hv.append(v.co[:])
        idx.append(vm[v.index])
    hp.append(idx)
tree=BVHTree.FromPolygons(hv,hp,all_triangles=False,epsilon=0.0)
print(f"头部眼区面 {len(hp)}")
for eo in eyes:
    ev=[]; ep=[]
    for p in eo.data.polygons:
        idx=[]
        for vi in p.vertices:
            idx.append(len(ev)); ev.append(eo.data.vertices[vi].co[:])
        ep.append(idx)
    tree2=BVHTree.FromPolygons(ev,ep,all_triangles=False,epsilon=0.0)
    ov=tree.overlap(tree2)
    # 位置聚类
    if ov:
        pts=[]
        for i,j in ov:
            c=np.mean([ev[k] for k in ep[j]],axis=0)
            pts.append(c)
        pts=np.array(pts)
        # 简单聚类
        used=np.zeros(len(pts),bool); cl=0; info=[]
        for i in range(len(pts)):
            if used[i]: continue
            m=np.linalg.norm(pts-pts[i],axis=1)<0.004
            used|=m; cl+=1
            cc=pts[m].mean(axis=0)
            L=np.linalg.norm(cc-np.array(EYE['L'][:]),axis=0); R=np.linalg.norm(cc-np.array(EYE['R'][:]),axis=0)
            info.append((int(m.sum()),cc,'L' if L<R else 'R'))
        print(f"{eo.name}: 与头部眼区穿插 {len(ov)} 对 → {cl} 簇")
        for n,cc,sd in sorted(info,reverse=True)[:5]:
            print(f"    {sd}眼 {n}对 @({cc[0]*1000:.1f},{cc[1]*1000:.1f},{cc[2]*1000:.1f})")
    else:
        print(f"{eo.name}: 无穿插")
bm.free()
