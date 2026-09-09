# -*- coding: utf-8 -*-
"""渲染04走路动画关键帧(正面+背面), 视觉终验不猫步/不内八.
选着地相帧(踝z最低时) — 这是猫步最容易暴露的相位."""
import bpy, os, math
import numpy as np

D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
P04 = os.path.join(D, "交付", "05骨骼绑定", "ARP新版测试_20260831", "04_动作测试.blend")
OUTD = os.path.join(D, "logs")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=P04)
arm = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
body = next(x for x in bpy.data.objects if x.type == 'MESH' and x.name.startswith('tripo'))
acts = {a.name: a for a in bpy.data.actions}
walk = acts['Standard Walk']
arm.animation_data.action = walk
for s in walk.slots:
    try: arm.animation_data.action_slot = s; break
    except RuntimeError: continue
f0, f1 = int(walk.frame_range[0]), int(walk.frame_range[1])

# 找着地相帧(两脚都接近地面 = 双支撑相, 猫步最明显)
scn = bpy.context.scene
lf_i = {g.index for g in body.vertex_groups if 'LeftFoot' in g.name or 'LeftToe' in g.name}
rf_i = {g.index for g in body.vertex_groups if 'RightFoot' in g.name or 'RightToe' in g.name}
lfv = [v.index for v in body.data.vertices if any(g.group in lf_i and g.weight>0.1 for g in v.groups)]
rfv = [v.index for v in body.data.vertices if any(g.group in rf_i and g.weight>0.1 for g in v.groups)]
scores = []
for f in range(f0, f1+1):
    scn.frame_set(f); bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg); vs = ev.data.vertices
    emw = np.array(ev.matrix_world); R3, t3 = emw[:3,:3], emw[:3,3]
    lz = min(float((R3@np.array(vs[i].co)+t3)[2]) for i in lfv)
    rz = min(float((R3@np.array(vs[i].co)+t3)[2]) for i in rfv)
    scores.append((max(lz, rz), f))     # max越小=双脚都越接近地面
scores.sort()
KEYF = sorted(set([scores[0][1], scores[1][1], scores[2][1], scores[len(scores)//2][1]]))
print(f"双支撑相帧(猫步最明显): {KEYF}")

arm.hide_set(True); arm.hide_render = True
for o in bpy.data.objects:
    if o.type == 'MESH' and (o.name.startswith('cs_') or o.name.startswith('WGT')):
        o.hide_render = True
scn.render.engine = 'BLENDER_WORKBENCH'
scn.display.shading.light = 'STUDIO'
scn.display.shading.color_type = 'SINGLE'
scn.display.shading.single_color = (0.75, 0.75, 0.78)
scn.display.shading.show_cavity = True
scn.display.shading.cavity_type = 'BOTH'
scn.world.color = (0.13, 0.13, 0.15)
scn.render.resolution_x = 760; scn.render.resolution_y = 1150
cam_d = bpy.data.cameras.new("c"); cam = bpy.data.objects.new("c", cam_d)
scn.collection.objects.link(cam); scn.camera = cam
cam_d.lens = 70

made = []
for f in KEYF:
    scn.frame_set(f); bpy.context.view_layer.update()
    for tag, loc, rot in [("front", (0.0, -3.30, 0.95), (1.5708, 0, 0)),
                          ("back",  (0.0,  3.30, 0.95), (1.5708, 0, 3.14159))]:
        cam.location = loc; cam.rotation_euler = rot
        p = os.path.join(OUTD, f"walk_f{f}_{tag}.png")
        scn.render.filepath = p
        bpy.ops.render.render(write_still=True)
        made.append(p)
        print(f"渲染: {p}")
print("RENDER_WALK_DONE")
