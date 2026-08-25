"""验证ARP版骨骼与Mixamo标准的对齐度."""
import bpy, os, json

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
RIG = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.blend")
REF = os.path.join(DELIVERY, "05骨骼绑定", "A_半自动打点", "mixamo_reference.json")

bpy.ops.wm.open_mainfile(filepath=RIG)
mixamo = json.load(open(REF, encoding="utf-8"))
mixamo_names = set(k.replace("mixamorig:", "") for k in mixamo.keys())

arm = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        arm = o
arp_names = set(b.name for b in arm.data.bones)

matched = sorted(arp_names & mixamo_names)
missing = sorted(mixamo_names - arp_names)
extra = sorted(arp_names - mixamo_names)

print(f"Mixamo标准: {len(mixamo_names)} 根")
print(f"ARP版实际: {len(arp_names)} 根")
print(f"完全对齐: {len(matched)} 根")
print(f"\n缺失的Mixamo骨骼 ({len(missing)}):")
for n in missing:
    print(f"  - {n}")
print(f"\n多余的骨骼 ({len(extra)}):")
for n in extra:
    print(f"  + {n}")
print("\nALIGN_CHECK_DONE")
