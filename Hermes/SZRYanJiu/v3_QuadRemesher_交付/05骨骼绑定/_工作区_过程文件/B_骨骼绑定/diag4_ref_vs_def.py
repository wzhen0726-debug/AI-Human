"""诊断: 最终rig里 参考骨(ref) vs 变形骨 位置对比 — 确定匹配在哪步断的."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
RIG = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "07_arp_rig_v6.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mw = arm.matrix_world

def bh(name):
    b = arm.data.bones.get(name)
    if not b: return None
    return mw @ b.head_local

pairs = [
    ("shoulder_ref.l", "shoulder.l",   "肩"),
    ("arm_ref.l",      "arm_stretch.l","上臂"),
    ("forearm_ref.l",  "forearm_stretch.l","前臂"),
    ("thigh_ref.l",    "thigh_stretch.l","大腿"),
    ("leg_ref.l",      "leg_stretch.l","小腿"),
    ("foot_ref.l",     "foot.l",       "脚"),
    ("neck_ref.x",     "c_neck.x",     "颈"),
]
print("部位 | 参考骨head | 变形骨head | 差(cm)")
for ref, defm, label in pairs:
    r, d = bh(ref), bh(defm)
    if r is None or d is None:
        print(f"{label}: ref={ref}存在={r is not None} def={defm}存在={d is not None}")
        continue
    diff = (r - d).length * 100
    print(f"{label}: ref=({r.x:.3f},{r.y:.3f},{r.z:.3f}) def=({d.x:.3f},{d.y:.3f},{d.z:.3f}) 差={diff:.1f}cm")

# 参考骨尾(=下一关节)
print("\n=== 参考骨tail(应指向下一关节) ===")
for name in ["arm_ref.l", "forearm_ref.l", "shoulder_ref.l"]:
    b = arm.data.bones.get(name)
    if b:
        t = mw @ b.tail_local
        print(f"{name} tail=({t.x:.3f},{t.y:.3f},{t.z:.3f})")

# 用户标记对照
print("\n标记: shoulder=(0.229,0.048,1.435) elbow=(0.458,0.095,1.435) hand=(0.715,0.019,1.435)")
print("DIAG4_DONE")
