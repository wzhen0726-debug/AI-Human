"""ARP半自动打点模板 v4 (2026-08-27 彻底重做).
正确流程(官方): AI预测标记→用户微调→Build. 本版把AI预测的17点(官方命名)直接预置进模板,
用户打开即见标记, 只需目视微调, 保存即可.
预置点来自 ai_guess_test.py 实测(guess_markers完整成功).
颜色/置顶显示/简短说明牌. 参考01A眼窝打点经验."""
import bpy, os
from mathutils import Quaternion

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
TPL = os.path.join(BASE, "_工作区_过程文件", "A_半自动打点", "07_arp_markers.blend")
OUT = os.path.join(BASE, "_工作区_过程文件", "A_半自动打点", "08_arp打点模板_AI预置.blend")

# AI实测预测点(主侧+X, 来自guess_markers成功运行)
AI_PTS = {
    "root_loc":       (0.000,  0.000, 0.901),
    "chin_loc":       (0.000, -0.114, 1.588),
    "neck_loc":       (0.000,  0.038, 1.473),
    "shoulder_loc":   (0.229,  0.048, 1.435),
    "elbow_loc":      (0.458,  0.095, 1.435),
    "hand_loc":       (0.715,  0.019, 1.435),
    "hand_tip_loc":   (0.906,  0.019, 1.435),
    "thigh_loc":      (0.114,  0.000, 0.901),
    "knee_loc":       (0.114,  0.000, 0.519),
    "foot_loc":       (0.114,  0.076, 0.138),
}
TIPS = {
    "root_loc": "骨盆中心(腰部中间)",
    "chin_loc": "下巴",
    "neck_loc": "颈根(脖子底部)",
    "shoulder_loc": "肩关节",
    "elbow_loc": "手肘",
    "hand_loc": "手腕",
    "hand_tip_loc": "指尖",
    "thigh_loc": "大腿上段",
    "knee_loc": "膝盖",
    "foot_loc": "脚踝",
}

# ===== 用干净的烘焙源04_bake.blend为基底(含身体), 加标记点 =====
BAKE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\04纹理烘焙\04_bake.blend"
bpy.ops.wm.open_mainfile(filepath=BAKE)
print("已打开烘焙源(含身体)")

BODY = "tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR"
body = bpy.data.objects[BODY]

# ===== 材质: 橙色主球 + 黄色对称球 =====
def make_mat(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Emission Color"].default_value = (*rgb, 1.0) if "Emission Color" in bsdf.inputs else bsdf.inputs["Emission"].default_value
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = 0.6
    return m

mat_main = make_mat("arp_marker_main", (1.0, 0.45, 0.05))
mat_sym  = make_mat("arp_marker_sym",  (1.0, 0.85, 0.0))

coll = bpy.data.collections.new("ARP标记点")
bpy.context.scene.collection.children.link(coll)

# 球网格
import bmesh
me = bpy.data.meshes.new("arp_ball")
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.022)
bm.to_mesh(me)
bm.free()

def add_marker(name, loc, mat, show_in_front=True):
    o = bpy.data.objects.new(name, me)
    o.location = loc
    o.show_in_front = show_in_front   # 参考01A眼窝打点: 标记永远显示在最前
    o.color = (*mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value[:3], 1.0)
    o.data.materials.append(mat)
    coll.objects.link(o)
    return o

count = 0
for name, loc in AI_PTS.items():
    # 主侧(+X)
    add_marker(name, loc, mat_main)
    count += 1
    # 对称侧: 官方命名 _sym, x取反
    sym = add_marker(name + "_sym", (-loc[0], loc[1], loc[2]), mat_sym)
    count += 1
print(f"预置标记: {count}个 (10主+10对称)")

# ===== 简短说明牌 =====
txt = bpy.data.curves.get("arp_tip_curve") or bpy.data.curves.new("arp_tip_curve", 'FONT')
tip = bpy.data.objects.new("说明", txt)
tip.data.body = ("ARP半自动打点 (AI已预置标记点)\n"
                 "操作: 选中橙色球→G拖动微调→全部满意后Ctrl+S保存, 完成!\n"
                 "黄色球是对称侧会自动镜像, 不用管. 只需核对橙色球(身体右半边).\n"
                 "提示: root=骨盆中心, chin=下巴, neck=颈根, shoulder=肩,\n"
                 "      elbow=肘, hand=腕, hand_tip=指尖, thigh=大腿,\n"
                 "      knee=膝, foot=踝")
tip.location = (-1.15, -1.2, 1.65)
tip.rotation_euler = (1.5708, 0, 0)  # 法线朝-Y(正视相机方向), 历史教训
tip.data.size = 0.035
tip.data.align_x = 'LEFT'
tip.show_in_front = True
bpy.context.scene.collection.objects.link(tip)
print("说明牌已放置")

# ===== 视口: 正视全身 =====
for scr in bpy.data.screens:
    for a in scr.areas:
        if a.type != 'VIEW_3D':
            continue
        sp = a.spaces[0]
        sp.region_3d.view_perspective = 'ORTHO'
        sp.region_3d.view_location = (0, 0, 0.9)
        sp.region_3d.view_distance = 2.6
        sp.region_3d.view_rotation = Quaternion((0.7071, 0.7071, 0, 0))
        sp.shading.type = 'MATERIAL'
print("视口配置完成")

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"已保存: {OUT}")
print("TEMPLATE_V4_DONE")
