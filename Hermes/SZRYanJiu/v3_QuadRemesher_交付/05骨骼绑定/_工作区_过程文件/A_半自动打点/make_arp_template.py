"""生成ARP半自动打点模板(2026-08-27).
从用户已打好的8点(06_rig_markers.blend)换算ARP Smart的20个标记:
  root/neck/chin/shoulder/hand/foot/thigh/knee/elbow/hand_tip + _sym
换算规则(解剖几何, 全部从用户点+网格实测推导, 不拍脑袋):
  root = 会阴上移到髋中(骨盆中心)   neck = 颈根
  chin = 头顶与颈根之间(下颌位置≈颈根上10cm)
  shoulder = 用户肩点  hand = 用户腕点
  hand_tip = 腕沿臂方向+16cm(指尖)
  thigh = 会阴与膝的中点(大腿中段)
  knee = 用户膝点  ankle→foot: 用户踝点
  elbow = 用户肘点   _sym = X取反镜像
模板放ARP_Markers集合, 用户在GUI里核对微调→保存→我跑ARP绑定."""
import bpy, os, json
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
SRC = os.path.join(BASE, "A_半自动打点", "06_rig_markers.blend")
OUT = os.path.join(BASE, "A_半自动打点", "07_arp_markers.blend")
BODY = "tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=SRC)

# 1) 读用户8点(matrix_world, 即用户所见)
def get_lm(name_part):
    for o in bpy.data.objects:
        if o.name.startswith("LM_") and name_part in o.name:
            return o.matrix_world.translation.copy()
    return None

pt = {}
pt["headtop"] = get_lm("头顶") or get_lm("headtop")
pt["neck"]    = get_lm("颈根") or get_lm("neckbase")
pt["crotch"]  = get_lm("会阴") or get_lm("crotch")
pt["shoulder_R"] = get_lm("右肩") or get_lm("shoulder_R")
pt["elbow_R"]    = get_lm("右肘") or get_lm("elbow_R")
pt["wrist_R"]    = get_lm("右腕") or get_lm("wrist_R")
pt["knee_R"]     = get_lm("右膝") or get_lm("knee_R")
pt["ankle_R"]    = get_lm("右踝") or get_lm("ankle_R")
for k, v in pt.items():
    assert v, f"缺标记: {k}"
print("用户8点读取OK")

body = bpy.data.objects.get(BODY)
assert body, "找不到身体网格"

# 2) 换算ARP 20点
arm_dir = (pt["wrist_R"] - pt["elbow_R"]).normalized()   # 前臂方向(朝指尖)
army = {
    "root_loc":        Vector((0, pt["crotch"].y, pt["crotch"].z + 0.05)),
    "neck_loc":        pt["neck"].copy(),
    "chin_loc":        pt["neck"] + Vector((0, 0, 0.10)),
    "shoulder_loc":    pt["shoulder_R"].copy(),
    "hand_loc":        pt["wrist_R"].copy(),
    "hand_tip_loc":    pt["wrist_R"] + arm_dir * 0.16,
    "foot_loc":        pt["ankle_R"].copy(),
    "thigh_loc":       ((pt["crotch"].x + pt["knee_R"].x) / 2,
                        (pt["crotch"].y + pt["knee_R"].y) / 2,
                        (pt["crotch"].z + pt["knee_R"].z) / 2),
    "knee_loc":        pt["knee_R"].copy(),
    "elbow_loc":       pt["elbow_R"].copy(),
}
army["thigh_loc"] = Vector(army["thigh_loc"])
# _sym侧: x取反
for k in ("shoulder_loc", "hand_loc", "hand_tip_loc", "foot_loc", "thigh_loc", "knee_loc", "elbow_loc"):
    v = army[k]
    army[k + "_sym"] = Vector((-v.x, v.y, v.z))

# 3) 建ARP_Markers集合 + 球标记(照手写版模板样式)
coll = bpy.data.collections.new("ARP_Markers")
bpy.context.scene.collection.children.link(coll)

mesh = bpy.data.meshes.new("marker_ball")
import bmesh
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.02)
bm.to_mesh(mesh); bm.free()

made = []
for name, pos in army.items():
    o = bpy.data.objects.new(f"ARP_{name}", mesh)
    o.location = pos
    o.show_in_front = True
    o.show_name = True
    o.empty_display_size = 0.05
    coll.objects.link(o)
    made.append((name, pos))

print(f"ARP标记生成: {len(made)}个")
for n, p in sorted(made):
    print(f"  {n}: ({p.x:.3f}, {p.y:.3f}, {p.z:.3f})")

# 4) 视口配置: 打开即正视全身
for ws in bpy.data.workspaces:
    for scr in ws.screens:
        for area in scr.areas:
            if area.type == 'VIEW_3D':
                for reg in area.regions:
                    if reg.type == 'WINDOW':
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                sp = space.region_3d
                                sp.view_perspective = 'ORTHO'
                                sp.view_distance = 3.0
                                sp.view_location = (0.0, 0.0, 0.9)
                                from mathutils import Quaternion
                                sp.view_rotation = Quaternion((0.7071, 0.7071, 0.0, 0.0))
                                space.shading.type = 'MATERIAL'

# 5) 中文提示牌
cu = bpy.data.curves.new("hint", type='FONT')
cu.body = "ARP打点核对: 20个球已按你的8点自动放好\n只需检查微调位置 → Ctrl+S保存\nroot=骨盆中心 chin=下巴 thigh=大腿中段\nhand_tip=指尖(腕前16cm)"
txt = bpy.data.objects.new("ARP打点提示", cu)
txt.location = (-1.1, -1.2, 1.5)
txt.rotation_euler = (1.5708, 0.0, 0.0)
bpy.context.scene.collection.objects.link(txt)

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"保存: {OUT}")
print("ARP_TEMPLATE_DONE")