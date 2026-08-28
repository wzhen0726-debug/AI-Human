"""验证新版02_ARP绑定.blend: 关键骨头尾 vs 用户17点实测值."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
SRC = os.path.join(BASE, "ARP版交付", "02_ARP绑定.blend")
OUT = os.path.join(BASE, "_工作区_过程文件", "logs", "arp_v2_verify.txt")

# 用户点(stage1实测)
U = {
    "crotch": (-0.001,-0.116,0.885), "neck": (0.000,-0.052,1.536),
    "shoulder": (0.196,0.010,1.398), "elbow": (0.479,0.000,1.402), "wrist": (0.708,-0.028,1.419),
    "knee": (0.130,0.020,0.487), "ankle": (0.142,-0.055,0.104),
}
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=SRC)

out = []
arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
out.append(f"骨架={len(arms)} 网格={len(meshes)}")
a = arms[0]
out.append(f"{a.name}: {len(a.data.bones)}骨 缩放{tuple(round(v,3) for v in a.scale)}")
mw = a.matrix_world

checks = [
    ("Hips", U["crotch"]),
    ("Neck", U["neck"]),
    ("LeftShoulder", None), ("LeftArm", U["shoulder"]),
    ("LeftForeArm", U["elbow"]), ("LeftHand", U["wrist"]),
    ("LeftUpLeg", None), ("LeftLeg", U["knee"]), ("LeftFoot", U["ankle"]),
]
for bn, target in checks:
    b = a.data.bones.get(bn)
    if not b:
        out.append(f"{bn}: ❌不存在")
        continue
    h = mw @ b.head_local
    s = f"{bn}: head=({h.x:.3f},{h.y:.3f},{h.z:.3f})"
    if target:
        d = ((h.x-target[0])**2+(h.y-target[1])**2+(h.z-target[2])**2)**0.5*100
        s += f" | 用户点=({target[0]:.3f},{target[1]:.3f},{target[2]:.3f}) | 差{d:.1f}cm {'✓' if d < 2 else '❌'}"
    out.append(s)

body = bpy.data.objects.get("tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR")
eyes = [o.name for o in bpy.data.objects if 'eye' in o.name.lower() and o.type=='MESH']
e_ok = all(bpy.data.objects[e].parent and bpy.data.objects[e].parent.type=='ARMATURE' for e in eyes) if eyes else False
out.append(f"眼球绑定: {eyes} → {'✓' if e_ok else '❌'}")
leftover = [o.name for o in bpy.data.objects if o.type != 'MESH' and o.type != 'ARMATURE' and o.name not in ('Key',)]
out.append(f"残留标记球: {len([o for o in bpy.data.objects if any(c.isdigit() for c in o.name[:2])])}个")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("VERIFY_DONE")
