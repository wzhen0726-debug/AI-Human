# -*- coding: utf-8 -*-
"""决定性验证: 我的numpy LBS 是否忠实复现 Blender Armature修改器的变形.
方法: 改骨rest为新朝向 → pose保持identity → 用depsgraph evaluated mesh取Blender自己的变形结果
     → 与numpy LBS逐顶点对比.
若一致 → 边长变化是LBS固有(用户在pose模式摆同样姿势也会看到), ⑧判据需重新标定
若不一致 → 我的LBS实现有bug(roll/connect/层级累积), 必须修
⚠只读03, 不保存任何产物."""
import bpy, os, math, collections
import numpy as np
from mathutils import Vector, Matrix

D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
RIG03 = os.path.join(D, "交付", "05骨骼绑定", "ARP新版测试_20260831", "03_骨骼绑定.blend")
TP = os.path.join(D, "原始文件", "Mixamo动画文件", "T-Pose.fbx")

def R3(M):
    A = np.array(M.to_3x3(), dtype=np.float64) if hasattr(M, "to_3x3") else np.array(M, dtype=np.float64)[:3,:3]
    for i in range(3):
        n = np.linalg.norm(A[:, i])
        if n > 1e-12: A[:, i] /= n
    return A

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG03)
arm = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
mesh = max([x for x in bpy.data.objects if x.type == 'MESH'], key=lambda x: len(x.data.vertices))
me = mesh.data
AW = np.array(arm.matrix_world); MW = np.array(mesh.matrix_world)
co = np.empty(len(me.vertices)*3); me.vertices.foreach_get("co", co)
Vo = co.reshape(-1,3)
Vw = Vo @ np.array(MW[:3,:3]).T + MW[:3,3]

ours = {}
for b in arm.data.bones:
    m = AW @ np.array(b.matrix_local)
    ours[b.name] = dict(R=R3(m), head=np.array(m[:3,3]), length=float(b.length),
                        conn=bool(b.use_connect), parent=(b.parent.name if b.parent else None))
order, rem = [], set(ours)
while rem:
    prog=False
    for n in sorted(rem):
        p=ours[n]['parent']
        if p is None or p not in rem: order.append(n); rem.discard(n); prog=True
    if not prog: order.extend(sorted(rem)); break

bpy.ops.import_scene.fbx(filepath=TP, use_manual_orientation=False)
aref = max((x for x in bpy.data.objects if x.type=='ARMATURE' and x!=arm), key=lambda x: len(x.data.bones))
wmr = np.array(aref.matrix_world)
ref = {b.name.split(':')[-1]: R3(wmr @ np.array(b.matrix_local)) for b in aref.data.bones}
for o in list(bpy.data.objects):
    if o not in (arm, mesh): bpy.data.objects.remove(o, do_unlink=True)

head_new, R_new, tail_new = {}, {}, {}
for n in order:
    o=ours[n]; p=o['parent']
    if p is None: hn=o['head'].copy()
    elif o['conn']: hn=tail_new[p].copy()
    else:
        Rd=R_new[p]@ours[p]['R'].T
        hn=head_new[p]+Rd@(o['head']-ours[p]['head'])
    Rn=ref[n] if n in ref else o['R']
    head_new[n],R_new[n]=hn,Rn
    tail_new[n]=hn+Rn[:,1]*o['length']

# ---- numpy LBS (归一化权重) ----
vgi={vg.index:vg.name for vg in mesh.vertex_groups}
bidx={n:i for i,n in enumerate(order)}
vi_l,bi_l,w_l=[],[],[]
for v in me.vertices:
    for g in v.groups:
        nm=vgi.get(g.group)
        if nm in bidx and g.weight>1e-8:
            vi_l.append(v.index); bi_l.append(bidx[nm]); w_l.append(float(g.weight))
VI=np.array(vi_l); BI=np.array(bi_l); W=np.array(w_l)
H_old=np.array([ours[n]['head'] for n in order]); H_new=np.array([head_new[n] for n in order])
Rd_all=np.array([R_new[n]@ours[n]['R'].T for n in order])
Vn=np.zeros_like(Vw); Wsum=np.zeros(len(Vw))
for bi in range(len(order)):
    sel=(BI==bi)
    if not sel.any(): continue
    idx=VI[sel]; w=W[sel][:,None]
    np.add.at(Vn,idx,w*(H_new[bi]+(Vw[idx]-H_old[bi])@Rd_all[bi].T))
    np.add.at(Wsum,idx,W[sel])
Vn/=Wsum[:,None]
dz=Vw[:,2].min()-Vn[:,2].min(); Vn[:,2]+=dz
print(f"numpy LBS 完成. dz={dz*1000:.2f}mm")

# ---- 用Blender自己做: 改骨rest, pose=identity, 取evaluated mesh ----
AWi=np.linalg.inv(AW)
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True)
bpy.context.view_layer.objects.active=arm
bpy.ops.object.mode_set(mode='EDIT')
ebs=arm.data.edit_bones
for n in order:
    eb=ebs[n]
    hn=head_new[n].copy(); hn[2]+=dz; tn=tail_new[n].copy(); tn[2]+=dz
    eb.head=Vector((AWi@np.append(hn,1.0))[:3]); eb.tail=Vector((AWi@np.append(tn,1.0))[:3])
    eb.roll=0.0
    eb.align_roll(Vector((np.array(AWi[:3,:3])@R_new[n])[:,0]))
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT')
bpy.ops.pose.rot_clear(); bpy.ops.pose.loc_clear(); bpy.ops.pose.scale_clear()
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()

dg=bpy.context.evaluated_depsgraph_get()
ev=mesh.evaluated_get(dg)
evm=ev.to_mesh()
ec=np.empty(len(evm.vertices)*3); evm.vertices.foreach_get("co",ec)
EV=ec.reshape(-1,3)
# evaluated mesh在mesh的object空间; 转世界
EVw=EV@np.array(ev.matrix_world[:3,:3]).T+np.array(ev.matrix_world.translation)
ev.to_mesh_clear()
print(f"Blender evaluated mesh: {len(EVw):,}顶点")

# ---- 对比 ----
assert len(EVw)==len(Vn), f"顶点数不符 {len(EVw)} vs {len(Vn)}"
d=np.linalg.norm(EVw-Vn,axis=1)*1000
print(f"\n=== numpy LBS vs Blender Armature修改器 (逐顶点世界坐标差) ===")
print(f"  中位={np.median(d):.6f}mm  p95={np.percentile(d,95):.6f}mm  p99={np.percentile(d,99):.6f}mm  max={d.max():.6f}mm")
print(f"  >0.01mm的顶点={int((d>0.01).sum()):,}  >0.1mm={int((d>0.1).sum()):,}  >1mm={int((d>1.0).sum()):,}")
if d.max()<0.05:
    print(f"  → ✓ 一致: 我的LBS忠实复现Blender修改器 → 边长变化是LBS固有行为")
    print(f"     (等价于用户在pose模式把角色摆成标准T-Pose时看到的涂抹)")
else:
    print(f"  → ✗ 不一致: 我的LBS实现有bug")
    worst=np.argsort(-d)[:10]
    for i in worst:
        print(f"     v{i}: numpy=({Vn[i,0]*1000:.2f},{Vn[i,1]*1000:.2f},{Vn[i,2]*1000:.2f}) "
              f"blender=({EVw[i,0]*1000:.2f},{EVw[i,1]*1000:.2f},{EVw[i,2]*1000:.2f}) 差={d[i]:.3f}mm")

# ---- Blender自己输出的边长变化(权威基准) ----
ei=np.empty(len(me.edges)*2,dtype=np.int32); me.edges.foreach_get("vertices",ei); E=ei.reshape(-1,2)
# 原始(rest未改前)边长: 用Vw
Lo=np.linalg.norm(Vw[E[:,0]]-Vw[E[:,1]],axis=1)*1000
Lb=np.linalg.norm(EVw[E[:,0]]-EVw[E[:,1]],axis=1)*1000
relb=np.abs(Lb-Lo)/np.maximum(Lo,1e-9)
print(f"\n=== Blender自己变形的边长变化({len(E):,}条边) ===")
print(f"  中位={np.median(relb)*100:.4f}% p95={np.percentile(relb,95)*100:.4f}% max={relb.max()*100:.4f}%")
print(f"  >1%={int((relb>0.01).sum()):,} ({(relb>0.01).mean()*100:.2f}%)  >5%={int((relb>0.05).sum()):,}")
bx=np.ptp(EVw,axis=0)*1000
print(f"  bbox 前={np.ptp(Vw,axis=0).round(1)*1000 if False else (np.ptp(Vw,axis=0)*1000).round(1)}mm 后={bx.round(1)}mm")
print("CMP_BLENDER_DONE")
