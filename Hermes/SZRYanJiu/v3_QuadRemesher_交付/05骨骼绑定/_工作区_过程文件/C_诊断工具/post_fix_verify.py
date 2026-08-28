"""修复后全面验证: 眼珠/手骨/行走姿态. 对比修复前数据."""
import bpy, os
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
OUT = os.path.join(BASE, "logs", "post_fix_verify.txt")
out = []
def sec(t): out.append(""); out.append(f"===== {t} =====")

# ============ 1. 绑定文件: 眼珠 + 手骨 + 骨骼朝向 ============
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(BASE, "B_骨骼绑定", "06_rig_final.blend"))
rig = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)

sec("1 眼珠朝向(修复前: (0,-0.13,-0.99)朝下)")
ok_eye = True
for o in bpy.data.objects:
    if o.type == 'MESH' and 'Eye' in o.name:
        iris = (o.matrix_world.to_3x3() @ Vector((0,-1,0))).normalized()
        good = abs(iris.x) < 0.1 and abs(iris.z) < 0.1 and iris.y < -0.9
        out.append(f"{o.name}: 虹膜={tuple(round(c,2) for c in iris)} {'✓朝前' if good else '✗仍错'}")
        if not good: ok_eye = False

sec("2 右手(+X=模型左)指骨位置(修复前: 指根全挤y0.012~0.017)")
# 修复后+X侧应为Left命名
fbs = []
for b in rig.data.bones:
    if any(k in b.name for k in ('Thumb1','Index1','Middle1','Ring1','Pinky1')) and 'Left' in b.name:
        fbs.append(f"{b.name}: y={b.head_local.y:.3f} (掌宽方向)")
out.extend(sorted(fbs))
ys = [b.head_local.y for b in rig.data.bones if 'Left' in b.name and any(k in b.name for k in ('Thumb1','Index1','Middle1','Ring1','Pinky1'))]
out.append(f"指根y跨度: {max(ys)-min(ys):.3f}m (修复前≈0.010, 应≈0.08手掌宽度)")

sec("3 拇指朝向(修复前: 朝上+0.26, Mixamo=朝前下)")
tb = rig.data.bones.get("mixamorig:LeftHandThumb1") or rig.data.bones.get("LeftHandThumb1")
if tb:
    M = rig.matrix_world @ tb.matrix_local
    ydir = (M.to_3x3() @ Vector((0,1,0))).normalized()
    out.append(f"拇指骨Y向={tuple(round(c,2) for c in ydir)} (前分量y应<-0.3表朝前)")

sec("4 脚骨朝向(修复前: Foot朝后, 应朝前)")
ft = rig.data.bones.get("mixamorig:LeftFoot") or rig.data.bones.get("LeftFoot")
if ft:
    M = rig.matrix_world @ ft.matrix_local
    ydir = (M.to_3x3() @ Vector((0,1,0))).normalized()
    out.append(f"LeftFoot Y向={tuple(round(c,2) for c in ydir)} (y分量应<-0.7表朝前)")

sec("5 左右验证: Left臂应在+X(用户右肩标记侧)")
la = rig.data.bones.get("mixamorig:LeftArm") or rig.data.bones.get("LeftArm")
ra = rig.data.bones.get("mixamorig:RightArm") or rig.data.bones.get("RightArm")
if la and ra:
    out.append(f"LeftArm head.x={la.head_local.x:+.3f} (应>0) | RightArm head.x={ra.head_local.x:+.3f} (应<0)")

# ============ 2. 行走测试: 帧18姿态 ============
sec("6 行走帧18姿态(修复前: 手举头顶z≈1.97)")
bpy.ops.wm.open_mainfile(filepath=os.path.join(BASE, "B_骨骼绑定", "walk_test_手写版.blend"))
rig2 = next((o for o in bpy.data.objects if o.type == 'ARMATURE' and 'Mixamo' in o.name), None)
scn = bpy.context.scene
scn.frame_set(18)
bpy.context.view_layer.update()
for bn in ['mixamorig:LeftHand', 'mixamorig:RightHand', 'mixamorig:LeftFoot', 'mixamorig:RightFoot']:
    pb = rig2.pose.bones.get(bn)
    if pb:
        w = (rig2.matrix_world @ pb.matrix).translation
        out.append(f"{bn}: ({w.x:.3f},{w.y:.3f},{w.z:.3f})")
        out.append(f"    [手应在腰胯z≈1.0-1.3不举头; 脚z应0.0-0.3贴地]")

out.append(""); out.append("POST_FIX_DONE")
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out))