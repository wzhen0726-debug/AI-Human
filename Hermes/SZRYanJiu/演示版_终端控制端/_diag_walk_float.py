# -*- coding: utf-8 -*-
"""实测04_动作测试(基于03B)的Standard Walk逐帧脚最低点, 与Mixamo参考并排对比.
参考帧10: 左15.1 右-6.7 min=-6.7(贴地) | 帧26: 左0.7 右28.1 min=0.7(贴地)
若我们同帧min>30mm → 脚没跟着Hips下降, 定位是整体偏移还是单脚/单轴问题."""
import bpy, os, math
import numpy as np

D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
P04 = os.path.join(D, "交付", "05骨骼绑定", "ARP新版测试_20260831", "04_动作测试.blend")

REF = {10: (15.1, -6.7), 26: (0.7, 28.1), 30: (-20.8, -0.1), 24: (0.5, 53.5), 7: (53.0, 4.4)}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=P04)
arm = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
body = max([x for x in bpy.data.objects if x.type == 'MESH' and x.name.startswith('tripo')],
           key=lambda x: len(x.data.vertices))
print(f"骨架'{arm.name}' {len(arm.data.bones)}骨 | body顶点={len(body.data.vertices):,}")

# Hips 骨当前rest z + 局部轴(判断z_axis探测结果)
aw = np.array(arm.matrix_world)
hb = next(b for b in arm.data.bones if b.name.endswith('Hips'))
hm = aw @ np.array(hb.matrix_local)
print(f"Hips rest世界z={hm[2,3]*1000:.1f}mm  局部轴(世界): x={np.round(hm[:3,0],3)} y={np.round(hm[:3,1],3)} z={np.round(hm[:3,2],3)}")
print(f"  → 垂直轴(世界+Z分量最大)={'x' if abs(hm[2,0])>abs(hm[2,1]) and abs(hm[2,0])>abs(hm[2,2]) else ('y' if abs(hm[2,1])>abs(hm[2,2]) else 'z')}")

# 腿长(判断leg_ratio)
leg_ours = sum(b.length for b in arm.data.bones if b.name.split(':')[-1] in ('LeftUpLeg','LeftLeg','LeftFoot'))
print(f"我们左腿骨长和={leg_ours*1000:.1f}mm (参考=984.2mm) → leg_ratio={leg_ours/0.9842:.4f}")

lf = {g.index for g in body.vertex_groups if 'LeftFoot' in g.name or 'LeftToe' in g.name}
rf = {g.index for g in body.vertex_groups if 'RightFoot' in g.name or 'RightToe' in g.name}
lfv = [v.index for v in body.data.vertices if any(g.group in lf and g.weight > 0.1 for g in v.groups)]
rfv = [v.index for v in body.data.vertices if any(g.group in rf and g.weight > 0.1 for g in v.groups)]
print(f"左脚权重顶点={len(lfv)} 右脚={len(rfv)}")

acts = {a.name: a for a in bpy.data.actions}
walk = acts.get('Standard Walk')
print(f"action 'Standard Walk' 存在={walk is not None}  帧范围={tuple(walk.frame_range) if walk else None}")
arm.animation_data.action = walk
for s in walk.slots:
    try:
        arm.animation_data.action_slot = s; break
    except RuntimeError: continue

scn = bpy.context.scene
f0, f1 = int(walk.frame_range[0]), int(walk.frame_range[1])
pbh = arm.pose.bones[[b.name for b in arm.pose.bones if b.name.endswith('Hips')][0]]

print(f"\n{'帧':>4}{'我们左z':>9}{'我们右z':>9}{'我们min':>9}{'参考min':>9}{'差mm':>8}{'Hips z':>9}{'Hips loc':>10}  腾空?")
floats = []
for f in range(f0, f1+1):
    scn.frame_set(f); bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg); vs = ev.data.vertices
    emw = np.array(ev.matrix_world); R3, t3 = emw[:3,:3], emw[:3,3]
    lz = min(float((R3 @ np.array(vs[i].co) + t3)[2]) for i in lfv) * 1000
    rz = min(float((R3 @ np.array(vs[i].co) + t3)[2]) for i in rfv) * 1000
    m = min(lz, rz)
    aev = arm.evaluated_get(dg)
    hbn = [b for b in aev.pose.bones if b.name.endswith('Hips')][0]
    hz = float((aw @ np.array(hbn.matrix))[:3,3][2]) * 1000
    loc = np.array(pbh.location) * 1000
    rmin = min(REF[f]) if f in REF else None
    fl = m > 30.0
    if fl: floats.append(f)
    rs = f"{rmin:>9.1f}{m-rmin:>8.1f}" if rmin is not None else f"{'':>9}{'':>8}"
    print(f"{f:>4}{lz:>9.1f}{rz:>9.1f}{m:>9.1f}{rs}{hz:>9.1f}{np.linalg.norm(loc):>10.1f}  {'✗腾空' if fl else ''}")
print(f"\n我们腾空帧={floats}  (参考=0帧, 参考min全程-20.8~+6.8mm)")
print("WALKCMP_DONE")
