# -*- coding: utf-8 -*-
"""03B后 内八/猫步终验(用户最关心项).
旧v3判据: 大腿外展全程同号不跨0 + 踝离中线≥77mm. 但03B把rest改成直腿(外展8.14°→0.35°),
所以"外展角"必须以**动画期间的绝对值**衡量, 不能再用"相对自身rest的差".
测: ①逐帧大腿骨向的世界外展角(x分量) ②踝世界x离中线 ③脚尖朝向(yaw) ④与Mixamo参考同帧对比"""
import bpy, os, math
import numpy as np

D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
W = os.path.join(D, "交付", "05骨骼绑定", "ARP新版测试_20260831")
P04 = os.path.join(W, "04_动作测试.blend")
REFW = os.path.join(D, "原始文件", "Mixamo动画文件", "Standard Walk.fbx")

def splay_and_ankle(path, actname, tag):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.endswith('.fbx'):
        bpy.ops.import_scene.fbx(filepath=path, use_manual_orientation=False)
        arm = max((x for x in bpy.data.objects if x.type=='ARMATURE'), key=lambda x: len(x.data.bones))
        body = max((x for x in bpy.data.objects if x.type=='MESH'), key=lambda x: len(x.data.vertices))
    else:
        bpy.ops.wm.open_mainfile(filepath=path)
        arm = next(x for x in bpy.data.objects if x.type=='ARMATURE')
        body = next((x for x in bpy.data.objects if x.type=='MESH' and x.name.startswith('tripo')), None)
        if body is None:
            body = max((x for x in bpy.data.objects if x.type=='MESH'), key=lambda x: len(x.data.vertices))
    bn = {b.name.split(':')[-1]: b.name for b in arm.pose.bones}
    acts = {a.name: a for a in bpy.data.actions}
    act = acts.get(actname) or list(acts.values())[0]
    arm.animation_data.action = act
    for s in act.slots:
        try: arm.animation_data.action_slot = s; break
        except RuntimeError: continue
    aw = np.array(arm.matrix_world); bw = np.array(body.matrix_world)
    scn = bpy.context.scene
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    rows = []
    for f in range(f0, f1+1):
        scn.frame_set(f); bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        aev = arm.evaluated_get(dg)
        out = {}
        for k in ('LeftUpLeg','RightUpLeg','LeftFoot','RightFoot','LeftToeBase','RightToeBase'):
            if k not in bn: continue
            pb = aev.pose.bones[bn[k]]
            M = aw @ np.array(pb.matrix)
            R = M[:3,:3]
            # 去scale
            for i in range(3):
                n = np.linalg.norm(R[:,i])
                if n>1e-12: R[:,i]/=n
            out[k] = dict(dir=R[:,1], head=M[:3,3])
        # 踝世界位置(从骨骼head, 比顶点更稳定)
        res = dict(frame=f)
        for side in ('Left','Right'):
            up = out.get(side+'UpLeg'); ft = out.get(side+'Foot'); toe = out.get(side+'ToeBase')
            if up:
                d = up['dir']
                # 外展: 骨向在世界XZ平面的x分量角(腿朝-Z下为正下)
                res[side+'_splay'] = math.degrees(math.atan2(d[0], -d[2]))
                # 前后pitch
                res[side+'_pitch'] = math.degrees(math.atan2(d[1], math.hypot(d[0], d[2])))
            if ft:
                res[side+'_ankle_x'] = ft['head'][0]*1000
                res[side+'_ankle_z'] = ft['head'][2]*1000
            if toe and ft:
                # 脚尖yaw: toe骨向在XY平面的朝向
                td = toe['dir']
                res[side+'_toe_yaw'] = math.degrees(math.atan2(td[0], -td[1]))
        rows.append(res)
    return rows

def summarize(rows, tag, ref_rows=None):
    print(f"\n{'='*66}\n[{tag}] {len(rows)}帧")
    for side in ('Left','Right'):
        sp = [r[side+'_splay'] for r in rows if side+'_splay' in r]
        ax = [abs(r[side+'_ankle_x']) for r in rows if side+'_ankle_x' in r]
        ty = [r[side+'_toe_yaw'] for r in rows if side+'_toe_yaw' in r]
        if not sp: continue
        sp = np.array(sp); ax = np.array(ax); ty = np.array(ty)
        cross0 = int(((sp[:-1]*sp[1:]) < 0).sum())     # 跨0次数(符号翻转)
        print(f"  {side}腿:")
        print(f"    大腿外展角: min={sp.min():+.2f}° max={sp.max():+.2f}° 均值={sp.mean():+.2f}° "
              f"全程同号={'✓' if cross0==0 else '✗跨0'+str(cross0)+'次'}")
        print(f"    踝离中线|x|: min={ax.min():.1f} max={ax.max():.1f} 均值={ax.mean():.1f}mm")
        print(f"    脚尖yaw: min={ty.min():+.2f}° max={ty.max():+.2f}° 均值={ty.mean():+.2f}° "
              f"({'外八✓' if ty.mean()>0 and side=='Left' else ('外八✓' if ty.mean()<0 and side=='Right' else '⚠内八?')})")
    if ref_rows:
        print(f"\n  与Mixamo参考同帧对比:")
        for side in ('Left','Right'):
            a = np.array([r[side+'_splay'] for r in rows]); b = np.array([r[side+'_splay'] for r in ref_rows])
            n = min(len(a), len(b))
            print(f"    {side}大腿外展: 我们均值={a[:n].mean():+.2f}° 参考均值={b[:n].mean():+.2f}° "
                  f"逐帧差 中位={np.median(np.abs(a[:n]-b[:n])):.2f}° max={np.max(np.abs(a[:n]-b[:n])):.2f}°")

ours_rows = splay_and_ankle(P04, 'Standard Walk', 'ours')
ref_rows = splay_and_ankle(REFW, 'Standard Walk', 'ref')
summarize(ours_rows, '我们04(03B标准rest) Standard Walk — 含Mixamo参考对比', ref_rows)
summarize(ref_rows, 'Mixamo参考 Standard Walk')
print("SPLAY_DONE")
