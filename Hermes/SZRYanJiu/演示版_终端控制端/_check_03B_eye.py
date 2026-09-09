# -*- coding: utf-8 -*-
"""验证03B: ①眼球与头部网格的相对位置保持(不凸出/不塌陷) ②渲染正面侧面供用户核验."""
import bpy, os
import numpy as np
from mathutils.kdtree import KDTree

D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
W = os.path.join(D, "交付", "05骨骼绑定", "ARP新版测试_20260831")
F03 = os.path.join(W, "03_骨骼绑定.blend")
F03B = os.path.join(W, "03B_骨骼标准化.blend")
OUTD = os.path.join(D, "logs")

def wverts(o):
    mw = np.array(o.matrix_world); c = np.empty(len(o.data.vertices)*3)
    o.data.vertices.foreach_get("co", c)
    return c.reshape(-1,3) @ mw[:3,:3].T + mw[:3,3]

def gather(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    d = {}
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name in ("Eye002_L","Eye002_R") or \
           (o.type=='MESH' and o.name.startswith('tripo')):
            d[o.name] = wverts(o)
    arm = next((x for x in bpy.data.objects if x.type=='ARMATURE'), None)
    if arm:
        hb = next((b for b in arm.data.bones if b.name.split(':')[-1]=='Head'), None)
        if hb: d['Head骨head'] = np.array((arm.matrix_world @ hb.head_local))
    d['_nobj'] = len(bpy.data.objects)
    d['_nbone'] = len(arm.data.bones) if arm else 0
    return d

A = gather(F03); B = gather(F03B)
print(f"=== 对象/骨骼数 ===\n  03: 对象={A['_nobj']} 骨={A['_nbone']}   03B: 对象={B['_nobj']} 骨={B['_nbone']}")
print(f"  03B保留对象: {'✓' if B['_nobj']==A['_nobj'] else '✗ 丢了'+str(A['_nobj']-B['_nobj'])+'个'}")

print(f"\n=== 眼球 ↔ 头部网格 相对位置(眼球须仍嵌在眼窝内) ===")
ok = True
for en in ["Eye002_L", "Eye002_R"]:
    if en not in A or en not in B:
        print(f"  {en}: ✗ 缺失(03={en in A} 03B={en in B})"); ok = False; continue
    body_k = [k for k in A if k.startswith('tripo')][0]
    for tag, dd in (("03 ", A), ("03B", B)):
        kd = KDTree(len(dd[body_k]))
        for i, v in enumerate(dd[body_k]): kd.insert(v, i)
        kd.balance()
        ds = np.array([kd.find(v)[2] for v in dd[en]])
        print(f"  {en} {tag}: 眼球顶点→头部网格最近距离 中位={np.median(ds)*1000:.3f} "
              f"min={ds.min()*1000:.3f} max={ds.max()*1000:.3f}mm")
    # 相对性: 03与03B的中位距离应一致(眼球跟随头部一起移动)
    kdA = KDTree(len(A[body_k]))
    for i,v in enumerate(A[body_k]): kdA.insert(v,i)
    kdA.balance()
    dA = np.array([kdA.find(v)[2] for v in A[en]])
    kdB = KDTree(len(B[body_k]))
    for i,v in enumerate(B[body_k]): kdB.insert(v,i)
    kdB.balance()
    dB = np.array([kdB.find(v)[2] for v in B[en]])
    dev = abs(np.median(dB)-np.median(dA))*1000
    flag = "✓" if dev < 0.5 else "✗ 眼球相对头部错位!"
    if dev >= 0.5: ok = False
    print(f"    → 中位距离变化={dev:.4f}mm {flag}")

print(f"\n=== 眼球中心位移 vs Head骨位移(须一致) ===")
if 'Head骨head' in A and 'Head骨head' in B:
    hd = B['Head骨head'] - A['Head骨head']
    print(f"  Head骨位移=({hd[0]*1000:.2f},{hd[1]*1000:.2f},{hd[2]*1000:.2f})mm |位移|={np.linalg.norm(hd)*1000:.2f}mm")
    for en in ["Eye002_L","Eye002_R"]:
        if en in A and en in B:
            ed = B[en].mean(axis=0) - A[en].mean(axis=0)
            dev = np.linalg.norm(ed-hd)*1000
            print(f"  {en}中心位移=({ed[0]*1000:.2f},{ed[1]*1000:.2f},{ed[2]*1000:.2f})mm 与Head骨差={dev:.3f}mm {'✓' if dev<0.6 else '✗'}")
            if dev >= 0.6: ok = False

# ---- 渲染 ----
print(f"\n=== 渲染03B(眼球可见, 供核验外观) ===")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=F03B)
arm = next((x for x in bpy.data.objects if x.type=='ARMATURE'), None)
if arm: arm.hide_set(True); arm.hide_render=True
# 隐藏ARP cs_*自定义形状
for o in bpy.data.objects:
    if o.type=='MESH' and (o.name.startswith('cs_') or o.name.startswith('WGT')):
        o.hide_render = True
scn = bpy.context.scene
scn.render.engine='BLENDER_WORKBENCH'
scn.display.shading.light='STUDIO'
scn.display.shading.color_type='MATERIAL'
scn.display.shading.show_cavity=True
scn.display.shading.cavity_type='BOTH'
scn.world.color=(0.12,0.12,0.14)
scn.render.resolution_x=800; scn.render.resolution_y=1250
cam_d=bpy.data.cameras.new("c"); cam=bpy.data.objects.new("c",cam_d)
scn.collection.objects.link(cam); scn.camera=cam; cam_d.lens=65
for tag,loc,rot,lens in [("front",(0.0,-3.40,0.92),(1.5708,0,0),65),
                          ("side",(3.40,0.0,0.92),(1.5708,0,1.5708),65),
                          ("face",(0.0,-0.75,1.690),(1.5708,0,0),90)]:
    cam.location=loc; cam.rotation_euler=rot; cam_d.lens=lens
    p=os.path.join(OUTD,f"03B_{tag}.png"); scn.render.filepath=p
    bpy.ops.render.render(write_still=True)
    print(f"  {p}")
print(f"\n{'EYE_CHECK PASS' if ok else 'EYE_CHECK FAIL'}")
print("EYECHECK_DONE")
