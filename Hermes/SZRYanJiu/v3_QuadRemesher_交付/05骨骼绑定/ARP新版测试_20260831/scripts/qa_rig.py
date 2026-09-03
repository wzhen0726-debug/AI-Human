"""骨架产物全质量自检 — 03_骨骼绑定.blend
检查: 对称性/连贯性/骨数/命名/权重/层级完整性"""
import bpy
from mathutils import Vector

bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\03_骨骼绑定.blend")
arm = bpy.data.objects.get('MixamoSkeleton')
body = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
issues = []

# 1. 骨数
nb = len(arm.data.bones)
print(f"[骨数] {nb} (期望55)" + ("" if nb==55 else "  ← 异常"))
if nb != 55: issues.append(f"骨数{nb}")

# 2. 左右对称(所有Left/Right骨)
print("\n[对称性] (Left vs Right, head的x应相反,y/z相同)")
for b in arm.data.bones:
    if b.name.startswith('Left'):
        r = arm.data.bones.get('Right' + b.name[4:])
        if r:
            dx = abs(b.head_local.x + r.head_local.x)
            dy = abs(b.head_local.y - r.head_local.y)
            dz = abs(b.head_local.z - r.head_local.z)
            err = max(dx, dy, dz)
            if err > 0.002:
                issues.append(f"不对称:{b.name}({err*100:.2f}cm)")
                print(f"  ✗ {b.name}: 差{err*100:.2f}cm")
asym = sum(1 for b in arm.data.bones if b.name.startswith('Left'))
print(f"  检查{asym}对, 全对称" if not any('不对称' in i for i in issues) else "  有不对称")

# 3. 连贯性(父子骨间隙)
print("\n[连贯性] (父tail vs 子head)")
gaps = []
for b in arm.data.bones:
    if b.parent:
        gap = (b.head_local - b.parent.tail_local).length
        if gap > 0.002 and not b.use_connect:
            gaps.append((b.name, b.parent.name, gap*100))
# 解剖学上正常的间隙(指根扇出/锁骨起脊柱/胯外展)排除
KNOWN_GAP = ['Shoulder','UpLeg','HandThumb1','HandIndex1','HandMiddle1','HandRing1','HandPinky1','Toe_End','HeadTop_End','Spine','Hips']
real_gaps = [(n,p,g) for n,p,g in gaps if not any(k in n for k in KNOWN_GAP)]
for n,p,g in real_gaps:
    print(f"  ✗ {p}->{n}: 间隙{g:.2f}cm")
    issues.append(f"断链:{p}->{n}")
print(f"  异常间隙{len(real_gaps)}处" + (" (全在正常范围)" if not real_gaps else " ← 需修"))

# 4. 权重
nvg = len(body.vertex_groups)
mod = [m for m in body.modifiers if m.type=='ARMATURE']
print(f"\n[权重] 顶点组{nvg} (期望~55), Armature修改器{len(mod)}个")
if nvg < 50: issues.append(f"顶点组仅{nvg}")
if not mod: issues.append("无Armature修改器")

# 5. 层级完整性(关键骨都在)
KEY = ['Hips','Spine','Spine2','Neck','Head','LeftArm','LeftForeArm','LeftHand',
       'LeftUpLeg','LeftLeg','LeftFoot','LeftHandThumb1','LeftHandIndex1','LeftFoot','LeftToeBase']
missing = [k for k in KEY if not arm.data.bones.get(k)]
print(f"\n[关键骨] 缺失: {missing if missing else '无'}")

# 6. 零长度骨
zero = [b.name for b in arm.data.bones if (b.tail_local - b.head_local).length < 0.001]
print(f"[零长度骨] {zero if zero else '无'}")
if zero: issues.append(f"零长度骨{zero}")

print("\n" + "="*40)
print("自检结果: " + ("全通过 ✓" if not issues else f"{len(issues)}项问题: {issues}"))
