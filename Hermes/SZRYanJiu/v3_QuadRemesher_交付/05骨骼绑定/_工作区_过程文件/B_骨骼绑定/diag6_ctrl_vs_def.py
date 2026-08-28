"""诊断: 控制骨(arm.l/arm_fk) vs 变形骨(arm_stretch.l) 位置 — 判断断在哪层."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
RIG = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "07_arp_rig_v6.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mw = arm.matrix_world

def bh(name):
    b = arm.data.bones.get(name)
    return (mw @ b.head_local) if b else None

print("骨名 | head位置")
for bn in ["shoulder.l", "arm.l", "arm_fk.l", "c_arm_fk.l", "arm_stretch.l",
           "arm_ik.l", "forearm.l", "forearm_fk.l", "forearm_stretch.l",
           "hand_fk.l", "hand.l", "shoulder_ref.l", "arm_ref.l", "forearm_ref.l"]:
    h = bh(bn)
    if h:
        print(f"{bn}: ({h.x:.3f},{h.y:.3f},{h.z:.3f})")
    else:
        print(f"{bn}: 不存在")

# 肩→手的水平跨距对比 (T-pose应为0.49m: 0.229→0.715)
def span(head_name, tail_name):
    h, t = bh(head_name), bh(tail_name)
    if h and t:
        b = arm.data.bones.get(tail_name)
        te = mw @ b.tail_local
        return (te.x - h.x)
    return None
print(f"\n参考臂展(肩ref头→前臂ref尾): ", end="")
sr, fr = bh("shoulder_ref.l"), arm.data.bones.get("forearm_ref.l")
if sr and fr:
    print(f"{(mw@fr.tail_local).x - sr.x:.3f}m (标记要求≈0.49)")
print(f"变形臂展(肩.l头→hand.l尾): ", end="")
sh, ha = bh("shoulder.l"), arm.data.bones.get("hand.l")
if sh and ha:
    print(f"{(mw@ha.tail_local).x - sh.x:.3f}m")
print("DIAG6_DONE")
