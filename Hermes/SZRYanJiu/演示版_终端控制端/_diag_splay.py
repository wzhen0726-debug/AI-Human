# -*- coding: utf-8 -*-
"""内八/猫步诊断: 量化大腿外展角、脚掌yaw、踝部横向位置.
对比 我们的rest / 我们04动画 / Mixamo rest / Mixamo动画.
假设根因: retarget用绝对朝向匹配(C补偿)把我们岔开的腿扳成Mixamo垂直腿
→ 网格从岔开rest被扭 → 内八感 + 脚过中线(猫步)."""
import bpy, os, math
import numpy as np
from mathutils import Vector

B05 = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付\05骨骼绑定\ARP新版测试_20260831"
ANIM_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\原始文件\Mixamo动画文件"
P = "mixamorig:"
BONE_Y = Vector((0, 1, 0))   # 骨骼自身空间里 head→tail 恒为 +Y

def bind_slot(arm, act):
    arm.animation_data.action = act
    for s in act.slots:
        try:
            arm.animation_data.action_slot = s
            return True
        except RuntimeError:
            continue
    return False

def splay_forward(v, sg):
    """腿世界方向 → (外展角, 前摆角). 角色面朝-Y, 垂直向下=(0,0,-1).
    外展: 冠状面偏角, 向外为正(sg=+1左/-1右). 前摆: 向前(-Y)为正."""
    az = math.degrees(math.atan2(-sg * v.x, -v.z))
    fw = math.degrees(math.atan2(-v.y, math.hypot(v.x, v.z)))
    return az, fw

def foot_yaw(v, sg):
    """脚掌方向水平偏角: 0=正前, +=外八, -=内八"""
    return math.degrees(math.atan2(sg * v.x, -v.y))

def dir_rest(arm, bname):
    b = arm.data.bones.get(bname)
    if not b: return None, None
    r3 = arm.matrix_world.to_3x3()
    d = (r3 @ (b.tail_local - b.head_local)).normalized()
    head_w = arm.matrix_world @ b.head_local
    return d, head_w

def analyze_rest(arm, tag):
    print(f"  [{tag} rest]")
    res = {}
    for side, sg in (("Left", +1), ("Right", -1)):
        du, _ = dir_rest(arm, P+side+"UpLeg")
        df, hw = dir_rest(arm, P+side+"Foot")
        if du is None or df is None: continue
        az, fw = splay_forward(du, sg)
        yaw = foot_yaw(df, sg)
        res[side] = dict(az=az, fw=fw, yaw=yaw, ankle_x=hw.x*1000,
                         thigh_dir=tuple(round(c,4) for c in du),
                         foot_dir=tuple(round(c,4) for c in df))
        print(f"    {side}: 大腿外展={az:+7.2f}° 前摆={fw:+6.2f}° 脚yaw={yaw:+7.2f}° 踝x={hw.x*1000:+7.1f}mm")
        print(f"         大腿方向={res[side]['thigh_dir']} 脚方向={res[side]['foot_dir']}")
    return res

def act_frames(act):
    """action的真实帧范围: 优先用fcurve关键帧(use_frame_range未设frame_start/end时frame_range会退化)"""
    ks = []
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for kp in fc.keyframe_points:
                        ks.append(kp.co.x)
    if ks:
        return int(round(min(ks))), int(round(max(ks)))
    fr = act.frame_range
    return int(fr[0]), int(fr[1])

def analyze_anim(arm, act, frames, tag, measure_foot_x=True):
    mw3 = arm.matrix_world.to_3x3()
    mww = arm.matrix_world
    body = next((o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('tripo')), None)
    # 支撑相判定用: 该侧脚底最低顶点z
    if body:
        lf = {g.index for g in body.vertex_groups if 'LeftFoot' in g.name or 'LeftToe' in g.name}
        rf = {g.index for g in body.vertex_groups if 'RightFoot' in g.name or 'RightToe' in g.name}
        lverts = [v.index for v in body.data.vertices if any(g.group in lf and g.weight>0.1 for g in v.groups)]
        rverts = [v.index for v in body.data.vertices if any(g.group in rf and g.weight>0.1 for g in v.groups)]
    else:
        lverts = rverts = []
    rec = {"Left": [], "Right": []}
    stance = {"Left": [], "Right": []}
    for f in frames:
        bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        ev = arm.evaluated_get(dg)
        lowest = {}
        if body and (lverts or rverts):
            bev = body.evaluated_get(dg)
            vs = bev.data.vertices
            if lverts: lowest['Left'] = min(vs[i].co.z for i in lverts)
            if rverts: lowest['Right'] = min(vs[i].co.z for i in rverts)
        for side, sg in (("Left", +1), ("Right", -1)):
            ul = ev.pose.bones.get(P+side+"UpLeg")
            ft = ev.pose.bones.get(P+side+"Foot")
            if not ul or not ft: continue
            du = (mw3 @ (ul.matrix.to_3x3() @ BONE_Y)).normalized()
            df = (mw3 @ (ft.matrix.to_3x3() @ BONE_Y)).normalized()
            az, fw = splay_forward(du, sg)
            yaw = foot_yaw(df, sg)
            fx = (mww @ ft.head).x * 1000
            rec[side].append((az, fw, yaw, fx, f))
            if side in lowest:
                stance[side].append((f, lowest[side]))
    print(f"  [{tag} {act.name}] {len(frames)}帧")
    for side in ("Left", "Right"):
        if not rec[side]: continue
        a = np.array([r[:4] for r in rec[side]])
        az, fw, yaw, fx = a[:,0], a[:,1], a[:,2], a[:,3]
        # 支撑相子集(脚底最低<3cm)
        st = [f for f, z in stance.get(side, []) if z < 0.03]
        mask = np.array([r[4] in st for r in rec[side]]) if st else np.zeros(len(a), bool)
        print(f"    {side}大腿外展: 全周期 min={az.min():+.2f} avg={az.mean():+.2f} max={az.max():+.2f}°"
              + (f" | 支撑相({mask.sum()}帧) avg={az[mask].mean():+.2f}°" if mask.sum() else ""))
        print(f"    {side}大腿前摆: 全周期 min={fw.min():+.2f} avg={fw.mean():+.2f} max={fw.max():+.2f}°")
        print(f"    {side}脚掌yaw : 全周期 min={yaw.min():+.2f} avg={yaw.mean():+.2f} max={yaw.max():+.2f}°"
              + (f" | 支撑相 avg={yaw[mask].mean():+.2f}°" if mask.sum() else ""))
        verdict = '⚠内八' if (yaw[mask].mean() if mask.sum() else yaw.mean()) < -3 else (
                  '外八' if (yaw[mask].mean() if mask.sum() else yaw.mean()) > 3 else '接近正直')
        print(f"    {side}踝x位置 : min={fx.min():+.1f} max={fx.max():+.1f}mm |x|最小={np.abs(fx).min():.1f}mm "
              f"{verdict} {'⚠过中线' if np.abs(fx).min()<10 else ''}")
    return rec

print("\n" + "="*72 + "\n【我们】04_动作测试.blend")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(B05, "04_动作测试.blend"))
arm = bpy.data.objects['MixamoSkeleton']
analyze_rest(arm, "我们(04)")
for an in ('Standard Walk', 'Running', 'Jump'):
    act = bpy.data.actions.get(an)
    if act:
        bind_slot(arm, act)
        f0, f1 = act_frames(act)
        analyze_anim(arm, act, range(f0, f1+1), "我们")

print("\n" + "="*72 + "\n【我们rest原样】03_骨骼绑定.blend")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(B05, "03_骨骼绑定.blend"))
analyze_rest(bpy.data.objects['MixamoSkeleton'], "我们03")

print("\n" + "="*72 + "\n【Mixamo参考】Standard Walk.fbx")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=os.path.join(ANIM_DIR, "Standard Walk.fbx"))
ref = next(o for o in bpy.data.objects if o.type=='ARMATURE')
analyze_rest(ref, "Mixamo")
ract = ref.animation_data.action
bind_slot(ref, ract)
f0, f1 = act_frames(ract)
analyze_anim(ref, ract, range(f0, f1+1), "Mixamo")
print("\nSPLAY_DIAG_DONE")
