"""修复: 只对齐roll, 保持标记点tail不动 (连接不断).
根因: align_refs_roll.py的 b.tail=head+spec_y×len 把尾部改成Mixamo参考模型方向,
      比例不同→尾部偏离子骨head→关节断开; 手指乱飞.
修复: 从10_arp_from_refs.blend(标记tail完好)出发, 只做align_roll.
附带: 全链条连接性定量验证."""
import bpy, os, json
from mathutils import Vector

BASE = os.path.join(r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定", "_工作区_过程文件")
SPEC = os.path.join(BASE, "logs", "mixamo_rest_spec.json")
RIG = os.path.join(BASE, "B_骨骼绑定", "10_arp_from_refs.blend")
OUT = os.path.join(BASE, "B_骨骼绑定", "14_arp_refs_rollonly.blend")

spec = json.load(open(SPEC, encoding="utf-8"))["bones"]
print(f"spec骨骼数: {len(spec)}")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)
arm = bpy.data.objects.get("MixamoSkeleton")
assert arm, "找不到MixamoSkeleton"

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones

# ===== 0) 先验证提取状态(10文件)的连接性 =====
print("\n=== 提取态连接性(应全连接) ===")
pre_gaps = []
for b in eb:
    if b.parent is None:
        continue
    d = (b.head - b.parent.tail).length
    if d > 0.001:
        pre_gaps.append((b.name, b.parent.name, d))
if pre_gaps:
    print(f"提取态就有{len(pre_gaps)}处间隙>1mm:")
    for g in pre_gaps[:15]:
        print(f"  {g[0]} ← {g[1]}: {g[2]*100:.2f}cm")
else:
    print("提取态全连接 ✓")

# ===== 1) 只对齐roll =====
aligned, skipped = 0, []
for b in eb:
    sb = spec.get("mixamorig:" + b.name)
    if not sb:
        skipped.append(b.name)
        continue
    z = Vector(sb["z"])
    if z.length > 0.01:
        b.align_roll(z)   # 只改roll, head/tail不动
    aligned += 1
print(f"\nroll对齐: {aligned}骨, 跳过: {skipped}")

# ===== 2) 对齐后再验连接性 =====
post_gaps = []
for b in eb:
    if b.parent is None:
        continue
    d = (b.head - b.parent.tail).length
    if d > 0.001:
        post_gaps.append((b.name, b.parent.name, d))
if post_gaps:
    print(f"对齐后间隙>1mm: {len(post_gaps)}处")
    for g in post_gaps[:15]:
        print(f"  {g[0]} ← {g[1]}: {g[2]*100:.2f}cm")
else:
    print("对齐后全连接 ✓")

bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.wm.save_mainfile(filepath=OUT)
print(f"保存: {OUT}")
print("ROLLONLY_DONE")
