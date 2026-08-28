"""dump: 参考骨与变形骨(带权重的)的head/tail — 建立修正映射."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
RIG = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "07_arp_rig_v6.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
body = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices))
mw = arm.matrix_world

vg_names = set(vg.name for vg in body.vertex_groups)

def fmt(v):
    return f"({v.x:.3f},{v.y:.3f},{v.z:.3f})"

print("=== 带权重的变形骨 (权重骨=最终导出的骨) ===")
for b in arm.data.bones:
    if b.name in vg_names:
        h, t = mw @ b.head_local, mw @ b.tail_local
        parent = b.parent.name if b.parent else "-"
        print(f"{b.name}: head={fmt(h)} tail={fmt(t)} 父={parent}")

print("\n=== 参考骨 (_ref结尾) ===")
for b in arm.data.bones:
    if b.name.endswith('_ref') or '_ref.' in b.name:
        h, t = mw @ b.head_local, mw @ b.tail_local
        print(f"{b.name}: head={fmt(h)} tail={fmt(t)}")
print("DUMP_DONE")
