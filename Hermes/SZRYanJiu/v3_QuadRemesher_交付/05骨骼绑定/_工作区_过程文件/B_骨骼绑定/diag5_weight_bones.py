"""诊断: rig的mesh权重组名指向哪类骨 + 变形骨是否就是权重骨."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
RIG = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "07_arp_rig_v6.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)

body = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices))
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')

print(f"mesh顶点组数: {len(body.vertex_groups)}")
# 顶点组名 = 权重骨名
vg_names = sorted([vg.name for vg in body.vertex_groups])
print("前20个顶点组名:", vg_names[:20])

# 分类: 这些组名指向哪类骨
deform_cnt = sum(1 for n in vg_names if 'stretch' in n or n.endswith(('.l','.r','.x')) and not n.startswith('c_'))
ctrl_cnt = sum(1 for n in vg_names if n.startswith('c_'))
print(f"\nstretch/变形类: {deform_cnt}, c_控制器类: {ctrl_cnt}")

# 检查关键: hand.l 等变形骨是否存在且被权重引用
key_bones = ['hand.l', 'forearm_stretch.l', 'arm_stretch.l', 'thigh_stretch.l', 'leg_stretch.l', 'foot.l', 'c_neck.x', 'c_root_master.x']
for bn in key_bones:
    in_bones = bn in arm.data.bones
    in_vg = bn in vg_names
    print(f"{bn}: 在骨架={in_bones}, 有权重组={in_vg}")
print("DIAG5_DONE")
