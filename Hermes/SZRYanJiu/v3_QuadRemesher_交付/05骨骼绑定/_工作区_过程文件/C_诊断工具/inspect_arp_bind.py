"""查02_ARP绑定.blend骨骼问题: 骨架数/骨骼名/关键骨头尾位置 vs 用户点位."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
SRC = os.path.join(BASE, "ARP版交付", "02_ARP绑定.blend")
OUT = os.path.join(BASE, "_工作区_过程文件", "logs", "arp_bind_inspect.txt")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=SRC)

out = []
arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
out.append(f"骨架数={len(arms)} 网格数={len(meshes)}")
for a in arms:
    out.append(f"骨架 {a.name}: {len(a.data.bones)}骨, 尺寸缩放={tuple(round(v,4) for v in a.scale)}")
for m in meshes:
    out.append(f"网格 {m.name}: {len(m.data.vertices)}顶点, 缩放={tuple(round(v,4) for v in m.scale)}, 父级={m.parent.name if m.parent else None}")

# 用户点位(实测记录)
user_pts = {
    "root_loc": (0.000, -0.089, 0.925),
    "chin_loc": (0, -0.11, 1.62),
    "neck_loc": (0, -0.03, 1.53),
}
if arms:
    a = arms[0]
    eb_names = list(a.data.bones.keys())
    out.append(f"\n前10根骨骼名: {eb_names[:10]}")
    # 找几个关键骨看世界坐标
    mw = a.matrix_world
    for bn in ["Hips", "LeftUpLeg", "RightUpLeg", "LeftArm", "RightArm", "Head"]:
        b = a.data.bones.get(bn) or a.data.bones.get("mixamorig:"+bn) or next((x for x in list(a.data.bones) if bn.lower() in x.name.lower()), None)
        if b:
            h = mw @ b.head_local
            t = mw @ b.tail_local
            out.append(f"{b.name}: head=({h.x:.3f},{h.y:.3f},{h.z:.3f}) tail=({t.x:.3f},{t.y:.3f},{t.z:.3f})")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("WROTE", OUT)
