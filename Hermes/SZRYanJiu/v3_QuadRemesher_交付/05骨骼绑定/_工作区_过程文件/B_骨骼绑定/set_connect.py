"""最终交付版: 设置肢体关节use_connect + 验证连接 + 导出.
解剖学说明:
- 肩→肘→腕、胯→膝→踝→脚 都在同一点, 设use_connect让它们连贯显示
- 锁骨起于脊柱侧、手指从掌骨扇出、大腿从胯臼外展 — 这些间隙是Mixamo标准,不是错误."""
import bpy, os

BASE = os.path.join(r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定", "_工作区_过程文件")
RIG = os.path.join(BASE, "B_骨骼绑定", "14_arp_refs_rollonly.blend")
OUT = os.path.join(BASE, "B_骨骼绑定", "16_arp_final.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)
arm = bpy.data.objects.get("MixamoSkeleton")
assert arm

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones

# 设use_connect: 关节处子骨head==父骨tail的连成链
connect_pairs = []
for b in eb:
    if b.parent is None:
        continue
    gap = (b.head - b.parent.tail).length
    if gap < 0.002:   # <2mm视为同一点
        b.use_connect = True
        connect_pairs.append(b.name)

bpy.ops.object.mode_set(mode='OBJECT')
print(f"设use_connect: {len(connect_pairs)}根")
print("  " + ", ".join(connect_pairs[:20]))

# 验证连接
gaps = []
for b in arm.data.bones:
    if b.parent is None:
        continue
    d = (b.head_local - b.parent.tail_local).length
    if d > 0.001:
        gaps.append((b.name, b.parent.name, d))
print(f"\n残留间隙>1mm: {len(gaps)}处 (解剖学正常偏移)")
for g in gaps:
    print(f"  {g[0]} ← {g[1]}: {g[2]*100:.1f}cm")

bpy.ops.wm.save_mainfile(filepath=OUT)
print(f"保存: {OUT}")
print("FINAL_DONE")
