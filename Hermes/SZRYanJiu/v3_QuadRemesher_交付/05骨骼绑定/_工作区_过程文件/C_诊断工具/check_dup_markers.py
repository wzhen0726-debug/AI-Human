"""检查标记点现状: 数量/命名/位置/重复/集合归属."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

print("=== 所有标记对象 ===")
for o in sorted(bpy.data.objects, key=lambda x: x.name):
    if o.type != 'EMPTY':
        continue
    colls = [c.name for c in o.users_collection]
    v = o.matrix_world.translation
    cons = [c.type for c in o.constraints]
    print(f"  {o.name} @ ({v.x:.3f},{v.y:.3f},{v.z:.3f}) 集合={colls} 约束={cons}")

print("=== 集合 ===")
for c in bpy.data.collections:
    print(f"  {c.name}: {len(c.objects)}个 [{', '.join(o.name for o in c.objects)}]")

print("=== 重复检查(名字去数字后缀) ===")
import re
names = [o.name for o in bpy.data.objects if o.type == 'EMPTY']
seen = {}
for n in names:
    base = re.sub(r'\.\d+$', '', n)
    seen.setdefault(base, []).append(n)
for base, lst in sorted(seen.items()):
    if len(lst) > 1:
        print(f"  重复: {lst}")
print("CHECK_DUP_DONE")
