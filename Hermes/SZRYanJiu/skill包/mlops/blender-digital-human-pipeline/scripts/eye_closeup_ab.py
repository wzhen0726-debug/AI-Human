#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""眼区固定相机正交特写 A/B 渲染（geometry 质量对照专用）

用法（每个 blend 渲一张，同一相机/光照，再拼图）:
  blender -b --factory-startup -noaudio --python-exit-code 1 --python eye_closeup_ab.py -- \
      <blend|fbx> <out.png> [z_m=1.6645] [ortho_scale_m=0.145] [res_x=1600] [res_y=700]

拼两张成带标注的上下对照图（需 PIL）:
  python eye_closeup_ab.py --compose out_stack.png "上:旧" "下:新" a.png b.png

WHY 这样渲:
- 正交 + 固定相机: 两版对比才有意义（透视/距离一变，形状差异分不出）。正前方相机朝 +Y，
  旋转 (pi/2,0,0)，位置 (0,-0.6,z)；眼裂高度 z≈1.66m（按模型 bbox 折算，别写死）。
- Workbench + SINGLE 颜色 + cavity(BOTH, ridge/valley 1.6): 去坪材质干扰，暴露面型/折角/锯齿；
  STUDIO 光比 matcap 更容易看出 rim 环的凹凸。
- 渲染前先存好被比较的旧版（下游步骤会覆盖同名产物）: 备份到 _备份/<用途>_<日期>/。
关于读数: 分辨率/ortho_scale 决定 mm/px（1600px / 145mm ≈ 0.09mm/px），要看清 0.2mm 级起伏就调细。
"""
import os
import sys


def render(blend, out, z=1.6645, scale=0.145, rx=1600, ry=700):
    import bpy
    if blend.lower().endswith(('.fbx', '.glb')):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=blend)
    else:
        bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'SINGLE'
    sh.single_color = (0.62, 0.62, 0.66)
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.curvature_ridge_factor = 1.6
    sh.curvature_valley_factor = 1.6
    sh.show_object_outline = False
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    cd = bpy.data.cameras.new('C')
    cd.type = 'ORTHO'
    cd.ortho_scale = scale            # 145mm 宽: 含两眼 + 眼角; 要单眼就减到 ~0.06
    cd.clip_start, cd.clip_end = 0.01, 3.0
    cam = bpy.data.objects.new('C', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (0.0, -0.60, z)
    cam.rotation_euler = (1.5707963, 0.0, 0.0)   # 正前方: 朝 +Y
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print('RENDERED:', out)


def compose(out, titles, paths):
    from PIL import Image, ImageDraw
    ims = [Image.open(p).convert('RGB') for p in paths]
    W, H = ims[0].size
    pad = 28
    img = Image.new('RGB', (W, (H + pad) * len(ims)), (24, 24, 26))
    d = ImageDraw.Draw(img)
    cols = [(255, 160, 120), (140, 235, 150), (150, 200, 255)]
    y = 0
    for im, t, i in zip(ims, titles, range(len(ims))):
        d.text((10, y + 6), t, fill=cols[i % len(cols)])
        img.paste(im, (0, y + pad))
        y += H + pad
    img.save(out)
    print('COMPOSED:', out, img.size)


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]
    if a and a[0] == '--compose':
        compose(a[1], a[2:2 + len(a[2:]) - 2], a[3:] if len(a) > 3 else a[2:])
    else:
        render(a[0], a[1], *([float(x) for x in a[2:6]] if len(a) > 2 else []))
