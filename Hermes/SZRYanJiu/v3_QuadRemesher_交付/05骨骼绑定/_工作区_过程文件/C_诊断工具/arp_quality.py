"""ARP绑定质量三查: ①body权重/modifier ②关键骨头尾 vs 用户点位 ③眼球绑定状态."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
SRC = os.path.join(BASE, "ARP版交付", "02_ARP绑定.blend")
OUT = os.path.join(BASE, "_工作区_过程文件", "logs", "arp_quality.txt")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=SRC)

out = []
arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
a = arms[0]
mw = a.matrix_world
body = bpy.data.objects.get("tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR")

# ===== ① body权重 =====
mods = [m.type for m in body.modifiers]
vg = [g.name for g in body.vertex_groups]
deform_vg = [g for g in vg if any(x in g for x in ("thigh", "shin", "foot", "arm", "forearm", "hand", "upArm", "loArm", "spine", "head", "neck", "clav"))]
import random
random.seed(7)
sample = random.sample(list(body.data.vertices), min(1000, len(body.data.vertices)))
w_total = sum(sum(g.weight for g in v.groups) for v in sample)
out.append(f"[权重] modifier={mods} 顶点组={len(vg)}(变形类{len(deform_vg)}) 千点总权={w_total:.0f}(满权1000)")

# ===== ② 关键变形骨头尾 vs 用户点位 =====
# 用户点位(实测自07模板): 主侧(+X=角色左)
u = {
    "root":   (0.000,-0.089,0.925), "chin": (0.000,-0.110,1.620), "neck": (0.000,-0.033,1.533),
    "shoulder_l": (0.190,-0.005,1.398), "elbow_l": (0.479,0.000,1.402), "wrist_l": (0.708,-0.028,1.419),
    "hip_l": (0.093,-0.010,0.862), "knee_l": (0.130,0.020,0.487), "ankle_l": (0.142,-0.055,0.104),
}
cands = {
    "root": ["c_root.x","root.x"], "chin":["head_scale_fix.x"], "neck":["neck_b.x"],
    "shoulder_l": ["clavicle.l","upArm_fk.l","shoulder.l"], "elbow_l":["loArm_fk.l","forearm.l"],
    "wrist_l": ["hand_fk.l","hand.l"], "hip_l": ["thigh_fk.l","thigh.l"],
    "knee_l": ["shin_fk.l","shin.l"], "ankle_l": ["foot_fk.l","foot.l"],
}
out.append("[关键骨位置] 名称: 实际head | 用户点 | 差cm")
for label, names in cands.items():
    b = next((a.data.bones.get(n) for n in names if a.data.bones.get(n)), None)
    if b:
        h = mw @ b.head_local
        ux, uy, uz = u[label]
        d = ((h.x-ux)**2+(h.y-uy)**2+(h.z-uz)**2)**0.5*100
        out.append(f"  {label}: {b.name} ({h.x:.3f},{h.y:.3f},{h.z:.3f}) | ({ux:.3f},{uy:.3f},{uz:.3f}) | 差{d:.1f}cm")
    else:
        out.append(f"  {label}: 找不到 {names}")

# ===== ③ 眼球 =====
for en in ("Eye002_L","Eye002_R"):
    e = bpy.data.objects.get(en)
    if e:
        emods = [m.type for m in e.modifiers]
        evgs = len(e.vertex_groups)
        out.append(f"[{en}] 父级={e.parent.name if e.parent else '无'} modifier={emods} 顶点组={evgs}")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("WROTE")
