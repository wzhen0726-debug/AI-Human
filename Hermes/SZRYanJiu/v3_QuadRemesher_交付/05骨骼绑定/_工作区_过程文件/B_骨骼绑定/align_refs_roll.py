"""对齐提取骨架的朝向/roll到Mixamo标准 (复刻方案A已验证的做法).
位置不动(已验证对准用户标记), 只改: tail方向=Mixamo Y轴, roll=align_roll(Mixamo Z轴).
这是行走动画手臂举头顶的根因修复 — 与手写版方案A同一个已验证方案."""
import bpy, os, json
from mathutils import Vector

BASE = os.path.join(r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定", "_工作区_过程文件")
SPEC = os.path.join(BASE, "logs", "mixamo_rest_spec.json")
RIG = os.path.join(BASE, "B_骨骼绑定", "10_arp_from_refs.blend")
OUT = os.path.join(BASE, "B_骨骼绑定", "12_arp_refs_aligned.blend")

spec = json.load(open(SPEC, encoding="utf-8"))["bones"]
print(f"spec骨骼数: {len(spec)}")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)
arm = bpy.data.objects.get("MixamoSkeleton")
assert arm

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones

aligned, skipped = 0, []
for b in eb:
    sb = spec.get("mixamorig:" + b.name)
    if not sb:
        skipped.append(b.name)
        continue
    cur_len = b.length
    if cur_len < 0.005:
        cur_len = sb["length"] * 0.01   # spec长度是cm
    y_dir = Vector(sb["y"]).normalized()
    b.tail = b.head + y_dir * cur_len
    z_dir = Vector(sb["z"])
    if z_dir.length > 0.01:
        b.align_roll(z_dir)
    aligned += 1

bpy.ops.object.mode_set(mode='OBJECT')
print(f"朝向对齐: {aligned}骨, 跳过: {skipped}")

bpy.ops.wm.save_mainfile(filepath=OUT)
print(f"保存: {OUT}")
print("ALIGN_DONE")
