"""重做ARP半自动打点模板 v2(2026-08-27 根因修复).
根因: v1把ARP标记直接叠加在手写版模板上, 没删旧的15个LM_*标记和旧提示牌
      → 画面上32个标记+2块提示牌全糊一起, 模型被挡住, 无法使用.
修复: 打开手写版模板 → 删除全部LM_*标记/全部文字牌/旧集合 →
      只保留模型+新增的17个ARP标记+一块简短提示牌."""
import bpy, os
from mathutils import Vector, Quaternion
import bmesh

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
SRC = os.path.join(BASE, "A_半自动打点", "06_rig_markers.blend")
OUT = os.path.join(BASE, "A_半自动打点", "07_arp_markers.blend")
BODY = "tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=SRC)

# ===== 0) 先读用户8点(删除前读!) =====
def get_lm(name_part):
    for o in bpy.data.objects:
        if o.name.startswith("LM_") and name_part in o.name:
            return o.matrix_world.translation.copy()
    return None

pt = {}
pt["headtop"]    = get_lm("头顶")
pt["neck"]       = get_lm("颈根")
pt["crotch"]     = get_lm("会阴")
pt["shoulder_R"] = get_lm("右肩")
pt["elbow_R"]    = get_lm("右肘")
pt["wrist_R"]    = get_lm("右腕")
pt["knee_R"]     = get_lm("右膝")
pt["ankle_R"]    = get_lm("右踝")
for k, v in pt.items():
    assert v, f"缺标记: {k}"
print("用户8点读取OK(删除旧标记前)")

# ===== 1) 删除全部旧标记和旧文字牌(根因修复核心) =====
to_remove = []
for o in bpy.data.objects:
    if o.name.startswith("LM_"):          # 手写版15个标记
        to_remove.append(o)
    elif o.type == 'FONT':                 # 所有文字牌
        to_remove.append(o)
for o in to_remove:
    bpy.data.objects.remove(o, do_unlink=True)
print(f"已删除旧标记/文字牌: {len(to_remove)}个")

# 删除空的旧集合
for c in list(bpy.data.collections):
    if c.name in ("LM_M", "LM_R", "LM_L") and len(c.objects) == 0:
        bpy.data.collections.remove(c)

body = bpy.data.objects.get(BODY)
assert body, "找不到身体网格"

# ===== 2) 换算ARP 17点(10主+7镜像, 同v1规则) =====
arm_dir = (pt["wrist_R"] - pt["elbow_R"]).normalized()
army = {
    "root_loc":     Vector((0, pt["crotch"].y, pt["crotch"].z + 0.05)),
    "neck_loc":     pt["neck"].copy(),
    "chin_loc":     pt["neck"] + Vector((0, 0, 0.10)),
    "shoulder_loc": pt["shoulder_R"].copy(),
    "hand_loc":     pt["wrist_R"].copy(),
    "hand_tip_loc": pt["wrist_R"] + arm_dir * 0.16,
    "foot_loc":     pt["ankle_R"].copy(),
    "thigh_loc":    Vector(((pt["crotch"].x + pt["knee_R"].x) / 2,
                            (pt["crotch"].y + pt["knee_R"].y) / 2,
                            (pt["crotch"].z + pt["knee_R"].z) / 2)),
    "knee_loc":     pt["knee_R"].copy(),
    "elbow_loc":    pt["elbow_R"].copy(),
}
for k in ("shoulder_loc", "hand_loc", "hand_tip_loc", "foot_loc",
          "thigh_loc", "knee_loc", "elbow_loc"):
    v = army[k]
    army[k + "_sym"] = Vector((-v.x, v.y, v.z))

# ===== 3) 建干净的ARP_Markers集合 =====
coll = bpy.data.collections.new("ARP_Markers")
bpy.context.scene.collection.children.link(coll)

# 橙色材质(让球在Material视口显示橙色, o.color对MESH不生效)
mat = bpy.data.materials.new("arp_orange")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = (1.0, 0.6, 0.1, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.4

mesh = bpy.data.meshes.new("arp_marker_ball")
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.02)
bm.to_mesh(mesh); bm.free()
mesh.materials.append(mat)

made = []
for name, pos in army.items():
    o = bpy.data.objects.new(f"ARP_{name}", mesh)
    o.location = pos
    o.show_in_front = True
    o.show_name = False          # 不显示名字(避免文字糊脸), 只留球
    o.color = (1.0, 0.6, 0.1, 1.0)  # 橙色, 与手写版红/蓝区分
    coll.objects.link(o)
    made.append((name, pos))
print(f"ARP标记生成: {len(made)}个")

# ===== 4) 视口: 正视全身 =====
for ws in bpy.data.workspaces:
    for scr in ws.screens:
        for area in scr.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        sp = space.region_3d
                        sp.view_perspective = 'ORTHO'
                        sp.view_distance = 3.0
                        sp.view_location = (0.0, 0.0, 0.9)
                        sp.view_rotation = Quaternion((0.7071, 0.7071, 0.0, 0.0))
                        space.shading.type = 'MATERIAL'

# ===== 5) 一块简短提示牌(放模型左侧, 不挡模型) =====
cu = bpy.data.curves.new("arp_hint", type='FONT')
cu.body = ("ARP打点核对(17球已自动放好)\n"
           "重点检查: chin=下巴 root=骨盆中心\n"
           "hand_tip=指尖 thigh=大腿中段\n"
           "微调后Ctrl+S保存")
cu.size = 0.06
txt = bpy.data.objects.new("ARP提示", cu)
txt.location = (-1.4, -1.2, 1.6)
txt.rotation_euler = (1.5708, 0.0, 0.0)
bpy.context.scene.collection.objects.link(txt)

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"保存: {OUT}")
print("ARP_TEMPLATE_V2_DONE")
