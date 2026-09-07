# -*- coding: utf-8 -*-
"""诊断05: 对比 03_骨骼绑定.blend 与 04_动作测试.blend 的骨架结构:
use_connect / parent关系 / head位置是否对齐上一根tail / 编辑模式联动性(结构上)."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
B05 = os.path.join(BASE, "交付", "05骨骼绑定", "ARP新版测试_20260831")

def inspect(blend, tag):
    print(f"\n{'='*70}\n[{tag}] {os.path.basename(blend)}")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=blend)
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    print(f"骨架对象数: {len(arms)}")
    for arm in arms:
        bones = arm.data.bones
        print(f"\n  骨架 '{arm.name}': {len(bones)}骨")
        # 检查我们要的变形骨链
        chain = ["Hips","Spine","Spine1","Spine2","Neck","Head",
                 "LeftUpLeg","LeftLeg","LeftFoot","RightUpLeg","RightLeg","RightFoot",
                 "LeftArm","LeftForeArm","LeftHand","RightArm","RightForeArm","RightHand"]
        found = {c: bones.get(c) for c in chain}
        missing = [c for c,v in found.items() if v is None]
        if missing: print(f"  缺骨: {missing}")
        n_conn = sum(1 for b in bones if b.use_connect)
        print(f"  use_connect=True骨数: {n_conn}/{len(bones)}")
        # 关键链: parent连接性 + head与parent tail距离
        print(f"  {'骨名':<14} {'parent':<12} {'conn':<5} head距parent_tail(mm)")
        for c in chain:
            b = found.get(c)
            if b is None: continue
            p = b.parent
            pn = p.name if p else "-"
            if p:
                d = (b.head_local - p.tail_local).length * 1000
                print(f"  {c:<14} {pn:<12} {str(b.use_connect):<5} {d:.3f}")
            else:
                print(f"  {c:<14} {pn:<12} {str(b.use_connect):<5} (根)")
        # 全局: 有多少骨的head与parent tail不重合
        bad = 0; bad_list = []
        for b in bones:
            if b.parent:
                d = (b.head_local - b.parent.tail_local).length
                if d > 1e-5:
                    bad += 1
                    bad_list.append((b.name, b.parent.name, d*1000))
        print(f"\n  head≠parent_tail的骨: {bad}/{len(bones)}")
        for nm, pn, d in sorted(bad_list, key=lambda x:-x[2])[:15]:
            print(f"    {nm} <- {pn}: {d:.3f}mm")

inspect(os.path.join(B05, "03_骨骼绑定.blend"), "03骨骼绑定(用户说正常)")
inspect(os.path.join(B05, "04_动作测试.blend"), "04动作测试(用户说出问题)")
print("\nDIAG05_DONE")
