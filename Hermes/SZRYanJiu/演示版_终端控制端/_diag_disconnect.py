"""诊断骨骼断开: 检查骨架中 父骨tail vs 子骨head 的世界距离
对比 演示版产物 vs 正式版产物, 定位断开来源"""
import bpy, sys
from mathutils import Vector

FILES = [
    ("演示版_03_骨骼绑定", r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付\05骨骼绑定\ARP新版测试_20260831\03_骨骼绑定.blend"),
    ("演示版_03_mixamo_rest", r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付\05骨骼绑定\ARP新版测试_20260831\03_mixamo_rest.blend"),
    ("演示版_04_动作测试", r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付\05骨骼绑定\ARP新版测试_20260831\04_动作测试.blend"),
    ("正式版_03_骨骼绑定", r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\03_骨骼绑定.blend"),
    ("正式版_03_mixamo_rest", r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\03_mixamo_rest.blend"),
]

for label, path in FILES:
    import os
    if not os.path.exists(path):
        print(f"\n### {label}: 文件不存在, 跳过")
        continue
    bpy.ops.wm.open_mainfile(filepath=path)
    arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
    if not arm:
        print(f"\n### {label}: 无骨架, 跳过")
        continue
    mw = arm.matrix_world
    gaps = []
    for b in arm.data.bones:
        if not b.parent:
            continue
        ptail = (mw @ b.parent.matrix_local).translation + ((mw @ b.parent.matrix_local).to_quaternion() @ Vector((0, b.parent.length, 0)))
        # 更直接: tail_local
        ptail = (mw @ b.parent.tail_local)
        chead = (mw @ b.head_local)
        d = (ptail - chead).length
        gaps.append((d * 1000, b.name, b.parent.name, b.use_connect))
    gaps.sort(reverse=True)
    n_2mm = sum(1 for g in gaps if g[0] > 2)
    n_10mm = sum(1 for g in gaps if g[0] > 10)
    n_50mm = sum(1 for g in gaps if g[0] > 50)
    n_conn = sum(1 for g in gaps if g[3])
    print(f"\n### {label}: {len(arm.data.bones)}骨, use_connect={n_conn}根")
    print(f"    tail-head间距: >2mm {n_2mm}根, >10mm {n_10mm}根, >50mm {n_50mm}根")
    print(f"    最大断开TOP10:")
    for d, n, p, c in gaps[:10]:
        print(f"      {n:32s} 父={p:28s} 断{d:8.1f}mm connect={c}")
print("\nDIAG_DONE")
