# -*- coding: utf-8 -*-
"""同机位对照两个 blend(跨阶段产物): 渲染 + 面部标志点定量。

场景: 用户/读图工具声称"当前产物 vs 上游产物五官变形/全变了"时, 用同机位同光照
同分辨率渲染 + 标志点数值来 settle(跨版本对比读图结论会翻转, 数值不会)。

用法:
  blender -b --factory-startup --python stage_render_compare.py -- A.blend B.blend OUTDIR [ORTHO_MM] [CENTER_Z_MM] [RES]
  ORTHO_MM 正交视宽mm(默认380), CENTER_Z_MM 画面中心高度mm(默认1635=平视面部), RES 分辨率(默认1600)。
输出: OUTDIR/cmp_A.png, OUTDIR/cmp_B.png; stdout 打印两图标志点(轮廓行宽/嘴带/眼区最暗点)与 px→mm 换算。
后续: 用系统 python + PIL 左右拼接成对照图即可(本脚本只用 numpy, 不依赖 PIL/scipy)。
"""
import bpy, os, sys, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 3:
    print("用法: ... -- A.blend B.blend OUTDIR [ORTHO_MM] [CENTER_Z_MM] [RES]")
    sys.exit(1)
A, B, OUT = argv[0], argv[1], argv[2]
ORTHO = (float(argv[3]) if len(argv) > 3 else 380.0) / 1000.0
CENTER_Z = (float(argv[4]) if len(argv) > 4 else 1635.0) / 1000.0
RES = int(argv[5]) if len(argv) > 5 else 1600
os.makedirs(OUT, exist_ok=True)

shots = []
for tag, bp in (("A", A), ("B", B)):
    bpy.ops.wm.open_mainfile(filepath=bp)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x = sc.render.resolution_y = RES
    if sc.world is None:
        sc.world = bpy.data.worlds.new("_w")
    sc.world.use_nodes = True
    try:
        bg = sc.world.node_tree.nodes["Background"]
        bg.inputs[0].default_value = (0.72, 0.72, 0.75, 1)
        bg.inputs[1].default_value = 0.8
    except Exception:
        pass
    sun = bpy.data.objects.new("_sun", bpy.data.lights.new("_sun", 'SUN'))
    sc.collection.objects.link(sun)
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(58), 0, math.radians(-28))
    cam = bpy.data.objects.new("_cam", bpy.data.cameras.new("_cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = ORTHO
    cam.rotation_euler = (math.radians(90), 0, 0)
    cam.location = Vector((0.0, -0.5, CENTER_Z))
    fp = os.path.join(OUT, f"cmp_{tag}.png")
    sc.render.filepath = fp
    bpy.ops.render.render(write_still=True)
    shots.append(fp)
    print("SHOT", tag, fp, flush=True)


def load(path):
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[:, :, :3]
    a = a[::-1]  # bpy 像素 row0 在下 → 翻转成图像行序(row0=顶)
    bpy.data.images.remove(im)
    return a

mmpp = ORTHO * 1000.0 / RES
print(f"1px ≈ {mmpp:.3f} mm (ortho={ORTHO*1000:.0f}mm / {RES}px)", flush=True)
for tag, fp in zip(("A", "B"), shots):
    a = load(fp)
    H, W = a.shape[:2]
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    lum = 0.30 * r + 0.59 * g + 0.11 * b
    skin = (r > 95) & (g > 60) & (b > 40) & (r > g) & (g >= b)
    print(f"[{tag}] 轮廓行宽(px):", flush=True)
    for yq in (0.30, 0.40, 0.50, 0.60, 0.70):
        yy = int(H * yq)
        xs = np.where(skin[yy])[0]
        if len(xs) > 20:
            wid = int(xs.max() - xs.min())
            print(f"   y{int(yq*100)}%: 左{int(xs.min())} 右{int(xs.max())} 宽{wid}px ({wid*mmpp:.0f}mm)")
    # 嘴部暗带(下半脸, 与渲染光照同源的启发式; 两侧同口径对比)
    y0b, y1b = int(H * 0.55), int(H * 0.80)
    bb, rr, gg, bl = lum[y0b:y1b], r[y0b:y1b], g[y0b:y1b], b[y0b:y1b]
    m = (bb < 118) & (rr > gg) & (gg >= bl)
    if m.sum() > 50:
        ys = np.where(m)[0]
        my0 = y0b + int(np.percentile(ys, 5))
        my1 = y0b + int(np.percentile(ys, 95))
        print(f"   嘴部暗带 y: [{my0},{my1}]")
    # 眼区左右半最暗点(虹膜/瞳孔)
    ey0, ey1 = int(H * 0.28), int(H * 0.45)
    eb = a[ey0:ey1]
    el = 0.30 * eb[:, :, 0] + 0.59 * eb[:, :, 1] + 0.11 * eb[:, :, 2]
    for half, name in ((slice(0, W // 2), "L"), (slice(W // 2, W), "R")):
        sub = el[:, half]
        yy, xx = np.unravel_index(np.argmin(sub), sub.shape)
        xx = xx + (0 if name == "L" else W // 2)
        c = eb[yy, xx]
        print(f"   眼区最暗点({name}) @({xx},{ey0 + yy}) RGB=({c[0]:.0f},{c[1]:.0f},{c[2]:.0f})")
print("STAGE_CMP_DONE", flush=True)
