# -*- coding: utf-8 -*-
"""正确验证QR材质分区: 
①眼窝材质面(槽1)是否全在眼部区域(XZ包围盒内) — 查204mm离群面
②材质0/1边界边是否沿rim轮廓 — 这才是"QR沿材质边界布线"的真判据
③碗内部面距rim远是正常的(径向+深度), 用XZ平面距离判区域归属"""
import bpy, os, json, collections
import numpy as np

D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
CHK = os.path.join(D, "交付", "02QuadRemesher拓扑", "02_qr_150k_材质分区检查.blend")
cont = json.load(open(os.path.join(D, "交付", "01A眼窝与眼球", "screenshots", "3ddfa",
                                   "eyelid_contour_manual.json"), encoding="utf-8"))
rim_pts = np.vstack([np.array(cont[s]["rim_3d"], dtype=np.float64) for s in ("L", "R")])
# 眼区XZ包围盒(rim范围+余量)
xr = (rim_pts[:,0].min()-0.005, rim_pts[:,0].max()+0.005)
zr = (rim_pts[:,2].min()-0.005, rim_pts[:,2].max()+0.005)
print(f"眼区XZ包围盒: x[{xr[0]*1000:.1f},{xr[1]*1000:.1f}]mm z[{zr[0]*1000:.1f},{zr[1]*1000:.1f}]mm")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=CHK)
o = next(x for x in bpy.data.objects if x.type == 'MESH')
mw = o.matrix_world; me = o.data
mats = [m.name if m else None for m in me.materials]
mi = [0]*len(me.polygons); me.polygons.foreach_get("material_index", mi)
print(f"材质槽={mats} 面分布={dict(collections.Counter(mi))}")

co = np.empty(len(me.vertices)*3); me.vertices.foreach_get("co", co)
V = co.reshape(-1,3) @ np.array(mw.to_3x3()).T + np.array(mw.translation)
def fcenter(i): return V[list(me.polygons[i].vertices)].mean(axis=0)

# rim折线(3D)
segs=[]
for s in ("L","R"):
    p=np.array(cont[s]["rim_3d"],dtype=np.float64)
    for i in range(len(p)): segs.append((p[i],p[(i+1)%len(p)]))
S0=np.array([x[0] for x in segs]); S1=np.array([x[1] for x in segs])
SD=S1-S0; SDl2=np.einsum('ij,ij->i',SD,SD)+1e-12
def rim_dist3d(p):
    t=np.clip(np.einsum('ij,ij->i',p-S0,SD)/SDl2,0,1)
    return np.linalg.norm(S0+t[:,None]*SD-p[None,:],axis=1).min()

# ① 眼窝材质面区域归属 + 定位离群
eye=[i for i in range(len(me.polygons)) if mi[i]==1]
fc=np.array([fcenter(i) for i in eye])
in_box=(fc[:,0]>=xr[0])&(fc[:,0]<=xr[1])&(fc[:,2]>=zr[0])&(fc[:,2]<=zr[1])
print(f"\n① 眼窝材质面(槽1)={len(eye)}个")
print(f"   在眼区XZ盒内: {int(in_box.sum())}  盒外(离群): {int((~in_box).sum())}")
out_idx=np.where(~in_box)[0]
if len(out_idx):
    print(f"   ⚠离群面位置(XZ):")
    for j in out_idx[:10]:
        c=fc[j]
        print(f"     face{eye[j]}: x={c[0]*1000:.1f} z={c[2]*1000:.1f} y={c[1]*1000:.1f}mm 距rim3d={rim_dist3d(c)*1000:.1f}mm")

# ② 材质0/1边界边 是否沿rim (统一用V世界坐标, 与①同源, 避免坐标系不一致)
# ⚠bmesh陷阱: 访问 e.verts[i].index 前必须 ensure_lookup_table(), 否则读到过期索引取错顶点
#   (本脚本曾因此漏掉verts的ensure, 报出假的"距rim189mm", 实测应为1.6-5.7mm)
import bmesh
bm=bmesh.new(); bm.from_mesh(me)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
bound=[]
for e in bm.edges:
    if len(e.link_faces)==2:
        if e.link_faces[0].material_index != e.link_faces[1].material_index:
            c=(V[e.verts[0].index]+V[e.verts[1].index])/2   # 世界坐标, 与①同源
            bound.append((c, rim_dist3d(c)))
bm.free()
bd=np.array([b[1] for b in bound]) if bound else np.array([9.9])
print(f"\n② 材质0/1边界边={len(bound)}条 (这是QR沿材质分区布的边环)")
print(f"   距rim轮廓: 中位={np.median(bd)*1000:.2f}mm max={bd.max()*1000:.2f}mm")
print(f"   <2mm(贴rim): {int((bd<0.002).sum())}/{len(bd)}  <5mm: {int((bd<0.005).sum())}")
# 边界边连通分量(是否成环)
bm2=bmesh.new(); bm2.from_mesh(me)
bm2.verts.ensure_lookup_table(); bm2.edges.ensure_lookup_table()
par={}
def find(a):
    while par.get(a,a)!=a: a=par[a]
    return a
be=[e.index for e in bm2.edges if len(e.link_faces)==2 and e.link_faces[0].material_index!=e.link_faces[1].material_index]
for ei in be:
    e=bm2.edges[ei]; a,b=e.verts[0].index,e.verts[1].index
    par.setdefault(a,a); par.setdefault(b,b)
    ra,rb=find(a),find(b)
    if ra!=rb: par[ra]=rb
comp={}
for ei in be: comp[find(bm2.edges[ei].verts[0].index)]=comp.get(find(bm2.edges[ei].verts[0].index),0)+1
bm2.free()
print(f"   边界边连通分量={sorted(comp.values(),reverse=True)[:6]} (2个环=L/R眼各一圈为理想)")

ok = (len(out_idx)==0) and np.median(bd)<0.003 and len(comp)<=4
print(f"\n判定: 眼窝面离群={len(out_idx)} 边界边距rim中位={np.median(bd)*1000:.2f}mm 分量数={len(comp)}")
print(f"→ {'✓QR沿材质边界(rim)布线, 分区干净' if ok else '⚠有离群/分区偏离, 见上'}")
print("VERIFY2_DONE")
