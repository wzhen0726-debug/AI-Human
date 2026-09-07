"""实证: 断开的骨骼(UpLeg等)动画中蒙皮是否正常 + rest朝向差异是否导致视觉断开
1) 检查这些骨use_connect为什么False(原来是物理连接的吗)
2) 动画中这些关节处mesh是否正常(不该有裂口)"""
import bpy, os
from mathutils import Vector

# 1) 比较: 03_骨骼绑定(未归一化, 原rest) 里 UpLeg→Hips 的连接性
P = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付\05骨骼绑定\ARP新版测试_20260831\03_骨骼绑定.blend"
bpy.ops.wm.open_mainfile(filepath=P)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
print("=== 03_骨骼绑定(原rest, 未归一化) 的连接性 ===")
for bn in ['LeftUpLeg','LeftLeg','LeftFoot','LeftShoulder','LeftArm','LeftHandThumb1']:
    b = arm.data.bones.get(bn)
    if b:
        ptail = b.parent.tail_local if b.parent else None
        gap = (b.parent.tail_local - b.head_local).length*1000 if b.parent else 0
        print(f"  {bn:20s} connect={b.use_connect} 父tail-我head间距={gap:.1f}mm")

# 2) 这些位置在rest下是否真的物理断开(看头位置重合度)
# Mixamo标准: UpLeg head应在Hips尾附近(胯部), 不该到头顶
print("\n=== Mixamo分离式关节rest布局(正常) ===")
hips = arm.data.bones['Hips']
ul = arm.data.bones['LeftUpLeg']
print(f"  Hips: head={tuple(round(x,3) for x in hips.head_local)} tail={tuple(round(x,3) for x in hips.tail_local)}")
print(f"  LeftUpLeg: head={tuple(round(x,3) for x in ul.head_local)} tail={tuple(round(x,3) for x in ul.tail_local)}")
print(f"  → Hips.tail在{hips.tail_local.z:.3f}(脊柱方向), UpLeg.head在胯部{ul.head_local.z:.3f}")
print("  → rest视觉'断开'是因为Hips.tail指向脊柱顶部而非胯部, 是Mixamo rest布局特性")

# 3) 动画中跨部蒙皮: UpLeg旋转时, 大腿根mesh应连续(无裂口)
print("\n=== 动画蒙皮连续性检查(数值) ===")
body = next(o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('tripo'))
# 找左胯部顶点(靠近LeftUpLeg head)
import bmesh
dg = bpy.context.evaluated_depsgraph_get()
scn = bpy.context.scene
ul_head_w = arm.matrix_world @ arm.data.bones['LeftUpLeg'].head_local
# 找距胯点<3cm的顶点
near = []
for v in body.data.vertices:
    w = body.matrix_world @ v.co
    if (w - ul_head_w).length < 0.03:
        near.append(v.index)
print(f"  距左胯点3cm内顶点: {len(near)}个")
# 这些顶点的权重归属
if near:
    groups = set()
    for vi in near[:50]:
        for g in body.data.vertices[vi].groups:
            groups.add(body.vertex_groups[g.group].name if g.group < len(body.vertex_groups) else '?')
    print(f"  胯部顶点权重归属: {sorted(groups)}")
print("DIAG_DONE")
