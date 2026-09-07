# -*- coding: utf-8 -*-
"""自查: rim_bevel后 ①选中边都紧贴rim(<1.2mm) ②周围碎边(2~3mm)权重全0 ③旋转=0 ④连通性."""
import bpy, os, json
import numpy as np

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付"
cont = json.load(open(os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json"), encoding="utf-8"))
rim_all = np.vstack([np.array(cont[s]["rim_3d"], dtype=np.float64) for s in ("L","R")])

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_rim_bevel.blend"))
o = max([x for x in bpy.data.objects if x.type=='MESH'], key=lambda x: len(x.data.vertices))
fail=[]
# 旋转
rot = tuple(round(x,10) for x in o.rotation_euler)
print(f"rotation_euler={rot}")
if any(abs(r)>1e-9 for r in o.rotation_euler): fail.append(f"旋转未归零{rot}")
me = o.data
bw = me.attributes.get("bevel_weight_edge")
if bw is None: fail.append("无bevel属性")
else:
    mw=o.matrix_world
    co=np.empty(len(me.vertices)*3); me.vertices.foreach_get("co",co)
    V=co.reshape(-1,3)@np.array(mw.to_3x3()).T+np.array(mw.translation)
    evi=np.empty(len(me.edges)*2,dtype=np.int32); me.edges.foreach_get("vertices",evi)
    EV=evi.reshape(-1,2); E0=V[EV[:,0]]; E1=V[EV[:,1]]; Emid=(E0+E1)/2
    vals=np.array([d.value for d in bw.data])
    sel=np.where(vals>0)[0]
    print(f"选中边={len(sel)}")
    # 每条选中边到rim最近距离(中点+端点)
    d_mid=np.linalg.norm(Emid[sel][:,None,:]-rim_all[None,:,:],axis=2).min(axis=1)
    print(f"选中边中点距rim: min={d_mid.min()*1000:.2f} max={d_mid.max()*1000:.2f}mm")
    if d_mid.max()>0.002: fail.append(f"有选中边距rim>{2}mm(max={d_mid.max()*1000:.2f})")
    # 碎边检查: 距rim 2~3mm的边, 权重应全0
    d_all=np.linalg.norm(Emid[:,None,:]-rim_all[None,:,:],axis=2).min(axis=1)
    stray=np.where((d_all>=0.002)&(d_all<0.003))[0]
    stray_w=vals[stray]
    n_bad=int((stray_w>0).sum())
    print(f"碎边(距rim2~3mm): {len(stray)}条, 其中带权重={n_bad}")
    if n_bad>0: fail.append(f"{n_bad}条碎边仍有倒角权重")
    # 连通分量
    parent={}
    def find(a):
        while parent.get(a,a)!=a:a=parent[a]
        return a
    def union(a,b):
        ra,rb=find(a),find(b)
        if ra!=rb:parent[ra]=rb
    import bmesh
    bm=bmesh.new();bm.from_mesh(me);bm.edges.ensure_lookup_table()
    for i in sel:
        e=bm.edges[i];a,b=e.verts[0].index,e.verts[1].index
        parent.setdefault(a,a);parent.setdefault(b,b);union(a,b)
    comp={}
    for i in sel:
        e=bm.edges[i];comp.setdefault(find(e.verts[0].index),0)
        comp[find(e.verts[0].index)]+=1
    sizes=sorted(comp.values(),reverse=True)
    bm.free()
    print(f"选中边连通分量(边数): {sizes}  (L眼一环+R眼一环=2个分量为正常)")
print("FAIL:" + "; ".join(fail) if fail else "RIM_CHECK ALL PASS")
