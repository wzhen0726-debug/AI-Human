"""dump完整参考骨: 名称/父子关系/局部轴向 — 规划提取为最终骨架."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
RIG = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "07_arp_rig_v6.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mw = arm.matrix_world

refs = [b for b in arm.data.bones if b.name.endswith('_ref') or '_ref.' in b.name]
print(f"参考骨总数: {len(refs)}\n")

# 按名称排序打印: 名称 | 父参考骨 | head | tail
print("名称 | 父骨 | head | tail")
for b in sorted(refs, key=lambda x: x.name):
    parent = b.parent.name if b.parent else "无"
    h, t = mw @ b.head_local, mw @ b.tail_local
    print(f"{b.name} | {parent} | ({h.x:.3f},{h.y:.3f},{h.z:.3f}) | ({t.x:.3f},{t.y:.3f},{t.z:.3f})")
print("\nDUMP_REFS_DONE")
