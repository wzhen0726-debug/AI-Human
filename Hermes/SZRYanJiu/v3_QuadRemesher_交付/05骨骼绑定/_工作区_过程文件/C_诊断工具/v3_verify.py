"""验证v3: ①链条连接(父tail==子head) ②手骨位置形态 ③脚踝衔接 ④关键点吻合."""
import bpy, os, json
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
SRC = os.path.join(BASE, "ARP版交付", "02_ARP绑定.blend")
OUT = os.path.join(BASE, "_工作区_过程文件", "logs", "v3_verify.txt")
UP = json.load(open(os.path.join(BASE, "_工作区_过程文件", "logs", "user_pts_actual.json"), encoding="utf-8"))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=SRC)
a = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mw = a.matrix_world
out = []

# ===== ① 连接性: 每根有父的骨, 父tail应==该骨head (容差1mm) =====
broken = []
for b in a.data.bones:
    if b.parent:
        pt_ = mw @ b.parent.tail_local
        ch = mw @ b.head_local
        d = (pt_ - ch).length * 1000
        if d > 2.0:
            broken.append(f"{b.name}←{b.parent.name}: {d:.1f}mm")
out.append(f"[连接] 断裂处={len(broken)}" + (": " + "; ".join(broken[:8]) if broken else " ✓全部相连"))

# ===== ② 手骨: 位置分布 + 排列方向 =====
h_l = mw @ a.data.bones["LeftHand"].head_local
finger_tips = []
for f in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
    b3 = a.data.bones.get(f"LeftHand{f}3")
    if b3:
        t = mw @ b3.tail_local
        finger_tips.append((f, t))
    else:
        finger_tips.append((f, None))
out.append(f"[左手] Hand head=({h_l.x:.3f},{h_l.y:.3f},{h_l.z:.3f})")
for f, t in finger_tips:
    if t:
        spread_y = t.y - h_l.y
        ext = (t - h_l).length
        out.append(f"  {f}3尾: 距腕{ext*100:.1f}cm, 前后向{spread_y*100:+.1f}cm")

# ===== ③ 脚踝衔接 =====
for S in ("Left", "Right"):
    leg_tail = mw @ a.data.bones[f"{S}Leg"].tail_local
    foot_head = mw @ a.data.bones[f"{S}Foot"].head_local
    d = (leg_tail - foot_head).length * 1000
    out.append(f"[{S}踝] Leg尾→Foot头: {d:.1f}mm {'✓' if d < 2 else '❌'}")

# ===== ④ 关键点 vs 用户点 =====
chk = [("Hips", UP["1骨盆中心"]), ("LeftArm", UP["4肩"]),
       ("LeftForeArm", UP["5肘"]), ("LeftHand", UP["6手腕"]),
       ("LeftLeg", UP["9膝"]), ("LeftFoot", UP["10脚踝"])]
out.append("[点位] 骨骼head vs 用户点:")
allok = True
for bn, up in chk:
    h = mw @ a.data.bones[bn].head_local
    d = ((Vector(h) - Vector(up)).length) * 100
    ok = d < 0.5
    allok &= ok
    out.append(f"  {bn}: 差{d*10:.1f}mm {'✓' if ok else '❌'}")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("V3VERIFY_DONE")
