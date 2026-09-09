# -*- coding: utf-8 -*-
"""决定性诊断: Mixamo原版Standard Walk自身在第10/26帧是否也双脚腾空?
若是 → 我们的retarget是忠实复现, 3cm阈值/判据需重新标定(不是bug)
若否 → 03B破坏了动画, 是真bug必须修
同时测参考的腿长/髋高比例, 对照我们的leg_ratio."""
import bpy, os, math
import numpy as np

ANIM = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\原始文件\Mixamo动画文件\Standard Walk.fbx"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=ANIM, use_manual_orientation=False)

arm = max((x for x in bpy.data.objects if x.type == 'ARMATURE'), key=lambda x: len(x.data.bones))
meshes = [x for x in bpy.data.objects if x.type == 'MESH']
body = max(meshes, key=lambda x: len(x.data.vertices)) if meshes else None
print(f"参考骨架 '{arm.name}' {len(arm.data.bones)}骨  obj.scale={tuple(round(v,4) for v in arm.scale)}")
print(f"参考网格 {[m.name for m in meshes]} body顶点={len(body.data.vertices) if body else 0:,}")

# 参考腿长(骨长)
bl = {}
for b in arm.data.bones:
    nm = b.name.split(':')[-1]
    bl[nm] = b.length * float(np.linalg.norm(np.array(arm.matrix_world.to_3x3())[:, 0]))
leg = sum(bl.get(n, 0) for n in ('LeftUpLeg','LeftLeg','LeftFoot'))
print(f"\n参考左腿骨长和(UpLeg+Leg+Foot)={leg*1000:.1f}mm")
for n in ('LeftUpLeg','LeftLeg','LeftFoot','LeftToeBase'):
    print(f"  {n}={bl.get(n,0)*1000:.1f}mm")

# rest髋高
hb = next((b for b in arm.data.bones if b.name.split(':')[-1]=='Hips'), None)
hips_rest_z = float((arm.matrix_world @ hb.head_local).z)
print(f"参考Hips rest世界z={hips_rest_z*1000:.1f}mm")

# 逐帧测脚最低点
act = arm.animation_data.action if arm.animation_data else None
print(f"参考action='{act.name if act else None}' 帧范围={tuple(act.frame_range) if act else None}")

lf = {g.index for g in body.vertex_groups if 'LeftFoot' in g.name or 'LeftToe' in g.name}
rf = {g.index for g in body.vertex_groups if 'RightFoot' in g.name or 'RightToe' in g.name}
lfv = [v.index for v in body.data.vertices if any(g.group in lf and g.weight > 0.1 for g in v.groups)]
rfv = [v.index for v in body.data.vertices if any(g.group in rf and g.weight > 0.1 for g in v.groups)]
print(f"参考左脚权重顶点={len(lfv)} 右脚={len(rfv)}")

scn = bpy.context.scene
f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
mw = np.array(body.matrix_world)
print(f"\n=== 参考Mixamo walk 逐帧脚最低点(世界z, mm) ===")
print(f"{'帧':>4}{'左脚z':>10}{'右脚z':>9}{'min':>9}{'Hips z':>10}  腾空(>30mm)?")
floats = []
rows = []
for f in range(f0, f1+1):
    scn.frame_set(f); bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    vs = ev.data.vertices
    # ⚠evaluated mesh的co是**对象空间**(已过修改器); Mixamo FBX对象带90°X旋转+0.01缩放,
    #   对象空间z≠世界z, 必须用matrix_world转换, 否则腾空判定全错.
    emw = np.array(ev.matrix_world)
    R3, t3 = emw[:3, :3], emw[:3, 3]
    lz = min(float((R3 @ np.array(vs[i].co) + t3)[2]) for i in lfv)
    rz = min(float((R3 @ np.array(vs[i].co) + t3)[2]) for i in rfv)
    aev = arm.evaluated_get(dg)
    hz = float((np.array(arm.matrix_world) @ np.array(aev.pose.bones['mixamorig:Hips'].matrix))[:3, 3][2])
    m = min(lz, rz)
    fl = m > 0.03
    if fl: floats.append(f)
    rows.append((f, lz, rz, m, hz))
    print(f"{f:>4}{lz*1000:>10.1f}{rz*1000:>9.1f}{m*1000:>9.1f}{hz*1000:>10.1f}  {'✗腾空' if fl else ''}")

print(f"\n参考自身腾空帧(min>30mm)={floats}")
print(f"参考腾空帧数={len(floats)}/{len(rows)}")
print(f"参考min脚z全程: min={min(r[3] for r in rows)*1000:.1f}mm max={max(r[3] for r in rows)*1000:.1f}mm")
print(f"参考Hips起伏={((max(r[4] for r in rows)-min(r[4] for r in rows))*100):.1f}cm")
print("REFWALK_DONE")
