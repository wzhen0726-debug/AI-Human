# -*- coding: utf-8 -*-
"""最终自查: 全链材质槽无EyeSocket红槽残留 + 04烘焙贴图不发红.
红材质只该存在于 01_1_eye_socket_qr.blend / 02_qr_150k_材质分区检查.blend(QR引导+用户检查用),
下游 02_qr_150k.blend / 03 / 04 必须已合并回单材质, 否则渲染/烘焙眼窝发红."""
import bpy, os, collections
import numpy as np

D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
DOWN = [   # 下游产物: 必须单槽且无红色EyeSocket
    ("02主产物", os.path.join(D, "交付", "02QuadRemesher拓扑", "02_qr_150k.blend")),
    ("03UV",     os.path.join(D, "交付", "03自动UV", "03_auto_uv.blend")),
    ("04烘焙",   os.path.join(D, "交付", "04纹理烘焙", "04_bake.blend")),
]
CHK = [    # 检查用文件: 允许保留EyeSocket分区
    ("02分区检查副本", os.path.join(D, "交付", "02QuadRemesher拓扑", "02_qr_150k_材质分区检查.blend")),
]

def slots(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    o = max([x for x in bpy.data.objects if x.type == 'MESH'], key=lambda x: len(x.data.vertices))
    me = o.data
    names = [m.name if m else None for m in me.materials]
    reds = []
    for m in me.materials:
        if m is None: continue
        bs = None
        if m.use_nodes and m.node_tree:
            bs = m.node_tree.nodes.get("Principled BSDF")
        if bs:
            c = bs.inputs['Base Color'].default_value
            if c[0] > 0.5 and c[1] < 0.35 and c[2] < 0.35:
                reds.append((m.name, tuple(round(v, 2) for v in c)))
    mi = [0]*len(me.polygons); me.polygons.foreach_get("material_index", mi)
    return names, dict(collections.Counter(mi)), reds

print("=== 下游产物(必须单槽, 无红EyeSocket) ===")
allok = True
for name, p in DOWN:
    if not os.path.exists(p):
        print(f"[{name}] ✗ 文件缺失"); allok = False; continue
    names, dist, reds = slots(p)
    bad = (len(names) != 1) or bool(reds)
    print(f"[{name}] 槽数={len(names)} 面分布={dist} 红槽={reds}")
    print(f"          → {'✗ 有红材质残留!' if bad else '✓ 单材质, 无红槽'}")
    if bad: allok = False

print("\n=== 检查用文件(允许保留EyeSocket分区) ===")
for name, p in CHK:
    if not os.path.exists(p):
        print(f"[{name}] ✗ 文件缺失"); continue
    names, dist, reds = slots(p)
    print(f"[{name}] 槽数={len(names)} 面分布={dist} 红槽={reds}")

# 04烘焙diffuse贴图不发红(EyeSocket饱和红=0.8,0.15,0.15)
print("\n=== 04烘焙Diffuse贴图像素检查(饱和红判据) ===")
img = bpy.data.images.load(os.path.join(D, "交付", "04纹理烘焙", "04_diffuse_4k.png"))
img.colorspace_settings.name = 'sRGB'
px = np.array(img.pixels).reshape(img.size[1], img.size[0], 4)[:, :, :3]
r, g, b = px[:,:,0], px[:,:,1], px[:,:,2]
nonblack = (px.sum(axis=2) > 0.06)
red = nonblack & (r > 0.6) & (g < 0.25) & (b < 0.25)
print(f"  非黑像素={int(nonblack.sum()):,}  饱和红像素={int(red.sum()):,} ({red.sum()/max(nonblack.sum(),1)*100:.3f}%)")
print(f"  均值 R={r[nonblack].mean():.3f} G={g[nonblack].mean():.3f} B={b[nonblack].mean():.3f} (肤色R>G>B正常)")
if red.sum() > 0:
    allok = False
    print("  ✗ 贴图存在饱和红 → 材质泄漏到烘焙!")
else:
    print("  ✓ 无饱和红 → 眼窝未烘红")

print(f"\n{'ALL PASS ✓' if allok else 'FAIL ✗ 见上'}")
print("MATECHECK_DONE")
