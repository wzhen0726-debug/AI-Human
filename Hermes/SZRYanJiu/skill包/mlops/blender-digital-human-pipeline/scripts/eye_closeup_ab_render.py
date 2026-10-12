# -*- coding: utf-8 -*-
"""眼区固定正交特写 A/B 渲染 —— 用于“rim 环/眼窝形状是否真改好了”的可核对对照。

用法:
  blender -b --factory-startup -noaudio --python-exit-code 1 \\
    --python scripts/eye_closeup_ab_render.py -- <blend> <out.png> [ortho_scale_m] [eye_z_m]

约定(本管线): 模型面朝 -Y、上为 +Z、身高≈1.8m → 眼裂高度 z≈1.6645m，0.145m 视口宽覆盖双眼含眼角。

A/B 纪律: **只换 blend，相机/光照/分辨率一字不改**；两张图上下叠放后再看。
否则视角或曝光一换，“看起来平滑了”就没有可核对的前提。

判读要点:
  - 工作台引擎 + 单色 + 腔体/曲率：把表面起伏与折角放大出来，且不受贴图/材质干扰；
  - 环的边缘线应连续流畅；黑色缺口=真破面/未闭合，不要当阴影瞒过去；
  - 眼球等独立对象可能渲成黑块 —— 分清“眼球内部反射”与“网格缺口”再下结论。
"""
import bpy, sys, os

a = sys.argv[sys.argv.index("--") + 1:]
BLEND, OUT = a[0], a[1]
ORTHO = float(a[2]) if len(a) > 2 else 0.145      # 视口宽(米)
EYE_Z = float(a[3]) if len(a) > 3 else 1.6645     # 眼裂高度(米)

if not os.path.isabs(OUT):
    raise SystemExit("输出必须用绝对路径(原生 Blender 进程的相对路径会落到别处)")
if BLEND.lower().endswith(".fbx"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=BLEND)
else:
    bpy.ops.wm.open_mainfile(filepath=BLEND)

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'STUDIO'
sh.color_type = 'SINGLE'; sh.single_color = (0.62, 0.62, 0.66)
sh.show_cavity = True; sh.cavity_type = 'BOTH'
sh.curvature_ridge_factor = 1.6; sh.curvature_valley_factor = 1.6
sh.show_object_outline = False
sc.render.resolution_x = 1600; sc.render.resolution_y = 700

cd = bpy.data.cameras.new("AB_CAM"); cd.type = 'ORTHO'
cd.ortho_scale = ORTHO; cd.clip_start = 0.01; cd.clip_end = 3.0
cam = bpy.data.objects.new("AB_CAM", cd); sc.collection.objects.link(cam); sc.camera = cam
cam.location = (0.0, -0.60, EYE_Z)           # 正前方(-Y 一侧)
cam.rotation_euler = (1.5707963, 0.0, 0.0)   # 朝 +Y
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("RENDERED:", OUT)
