# 穿插/自交检测: 眼区面片两两BVH重叠, 排除共顶点邻居 → 真正的"面互相穿过"
import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
F=os.environ.get("CHK_BLEND"); J=os.environ.get("EYE_CONTOUR_JSON")
print("检查:", os.path.basename(F or ""))
bpy.ops.wm.open_mainfile(filepath=F)
Jd=json.load(open(J,encoding="utf-8"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
for s in ("L","R"):
    c=Vector(tuple(float(x) for x in Jd[s]['center']))
    P=np.array([[float(p[0]),float(p[2])] for p in Jd[s]['rim_3d']])
    fs=[]
    for f in bm.faces:
        cc=f.calc_center_median()
        if (cc-c).xz.length>0.030 or cc.y>c.y+0.02: continue
        d=float(np.sqrt((P[:,0]-cc.x)**2+(P[:,1]-cc.z)**2).min())
        if d>0.010: continue
        fs.append(f)
    vmap={}; verts=[]; polys=[]
    for f in fs:
        idx=[]
        for v in f.verts:
            k=v.index
            if k not in vmap:
                vmap[k]=len(verts); verts.append(v.co[:])
            idx.append(vmap[k])
        polys.append(idx)
    tree=BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    pairs=tree.overlap(tree)
    # 面到顶点集合
    fv={i:set(p) for i,p in enumerate(polys)}
    real=set(); adj=0
    for i,j in pairs:
        if i==j: continue
        a,b=sorted((i,j))
        if (a,b) in real: continue
        if fv[a] & fv[b]:
            adj+=1
        else:
            real.add((a,b))
    print(f"{s}: 眼区10mm内 {len(polys)}面 | 真穿插面对 {len(real)} | 共顶点邻接对(正常) {adj//2}")
    if real:
        show=list(real)[:4]
        for a,b in show:
            ca=bm.faces[fs[a].index] if False else None
            va=np.mean([verts[i] for i in polys[a]],axis=0); vb=np.mean([verts[i] for i in polys[b]],axis=0)
            print(f"    穿插对 @({va[0]*1000:.1f},{va[1]*1000:.1f},{va[2]*1000:.1f}) ↔ ({vb[0]*1000:.1f},{vb[1]*1000:.1f},{vb[2]*1000:.1f})")
bm.free()
