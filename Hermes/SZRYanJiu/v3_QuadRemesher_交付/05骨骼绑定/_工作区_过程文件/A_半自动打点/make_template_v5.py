"""ARP打点模板 v5 (2026-08-27): 完全照抄手写版模板规格.
修复用户三问: ①点样式统一(中线黄/右红/腿绿/镜像蓝)+show_in_front身体内可见
             ②左侧驱动器实时镜像+锁定 ③只管前视图(深度我处理)."""
import bpy, os, bmesh
from mathutils import Quaternion

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
BAKE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\04纹理烘焙\04_bake.blend"
OUT = os.path.join(BASE, "_工作区_过程文件", "A_半自动打点", "08_arp打点模板_AI预置.blend")

# AI实测预置点(主侧+X = 模型右侧)
AI_PTS = {
    "root_loc":     (0.000,  0.000, 0.901),
    "chin_loc":     (0.000, -0.114, 1.588),
    "neck_loc":     (0.000,  0.038, 1.473),
    "shoulder_loc": (0.229,  0.048, 1.435),
    "elbow_loc":    (0.458,  0.095, 1.435),
    "hand_loc":     (0.715,  0.019, 1.435),
    "hand_tip_loc": (0.906,  0.019, 1.435),
    "thigh_loc":    (0.114,  0.000, 0.901),
    "knee_loc":     (0.114,  0.000, 0.519),
    "foot_loc":     (0.114,  0.076, 0.138),
}
TIPS = {
    "root_loc": "骨盆中心", "chin_loc": "下巴", "neck_loc": "颈根",
    "shoulder_loc": "肩", "elbow_loc": "肘", "hand_loc": "腕",
    "hand_tip_loc": "指尖", "thigh_loc": "大腿", "knee_loc": "膝", "foot_loc": "踝",
}
# 手写版同款配色
YELLOW = (1.0, 0.9, 0.2)    # 中线点
RED    = (1.0, 0.35, 0.35)  # 右臂点
GREEN  = (0.35, 0.9, 0.4)   # 右腿点
BLUE   = (0.35, 0.5, 1.0)   # 镜像点(自动)
def color_of(name):
    if name in ("root_loc", "chin_loc", "neck_loc"):
        return YELLOW
    if name in ("thigh_loc", "knee_loc", "foot_loc"):
        return GREEN
    return RED

bpy.ops.wm.open_mainfile(filepath=BAKE)

# 球网格(比v4大: 半径30mm, 外行好点选)
me = bpy.data.meshes.new("arp_ball")
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.030)
bm.to_mesh(me)
bm.free()

def make_mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1.0)
    return m

coll = bpy.data.collections.new("ARP标记点")
bpy.context.scene.collection.children.link(coll)

mat_cache = {}
def get_mat(rgb):
    key = tuple(round(c, 2) for c in rgb)
    if key not in mat_cache:
        mat_cache[key] = make_mat(f"arp_m_{key}", rgb)
    return mat_cache[key]

def add_ball(name, loc, rgb):
    ball_me = me.copy()   # 独立网格副本, 否则共享网格上对象材质不生效(渲染全灰)
    o = bpy.data.objects.new(name, ball_me)
    o.location = loc
    o.show_in_front = True          # 身体内的点也永远显示在最前(关键!)
    o.display_type = 'TEXTURED'
    o.data.materials.append(get_mat(rgb))
    coll.objects.link(o)
    return o

main_objs = {}
for name, loc in AI_PTS.items():
    main = add_ball(name, loc, color_of(name))
    main_objs[name] = main
    # 镜像球: 蓝色, 驱动器跟随, 锁定不可选
    sym = add_ball(name + "_sym", (-loc[0], loc[1], loc[2]), BLUE)
    sym.select_set(False)
    sym.hide_select = True   # 对称点禁止误选
    for ax in range(3):
        fcurve = sym.driver_add("location", ax)
        drv = fcurve.driver
        drv.type = 'SCRIPTED'
        var = drv.variables.new()
        var.name = "m"
        var.type = 'TRANSFORMS'
        var.targets[0].id = main
        var.targets[0].transform_type = ['LOC_X', 'LOC_Y', 'LOC_Z'][ax]
        drv.expression = "-m" if ax == 0 else "m"
    sym.lock_location = (True, True, True)
print(f"预置标记: {len(main_objs)}主 + {len(main_objs)}镜像")

# 说明牌(左侧不挡右手, +90°法线朝前 — 手写版教训)
txt = bpy.data.curves.new("arp_tip", 'FONT')
tip = bpy.data.objects.new("打点说明", txt)
tip.data.body = ("ARP打点模板 (AI已预置, 只需微调)\n"
                 "1. 只调身体右侧的红/绿/黄球 (G拖动)\n"
                 "2. 左侧蓝球自动镜像跟随, 不用碰\n"
                 "3. 只管正面视图, 不用管身体厚度\n"
                 "4. 调完 Ctrl+S 保存, 完成!\n"
                 "黄=骨盆/下巴/颈根  红=肩肘腕指尖  绿=大腿膝踝")
tip.location = (-1.75, -1.2, 1.65)   # 往左挪, 避开右臂遮挡
tip.rotation_euler = (1.5708, 0, 0)
tip.data.size = 0.045
tip.data.align_x = 'LEFT'
tip.show_in_front = True
bpy.context.scene.collection.objects.link(tip)

# 视口: 手写版同款 (MATERIAL着色/正交/纯正面)
for scr in bpy.data.screens:
    for a in scr.areas:
        if a.type != 'VIEW_3D':
            continue
        sp = a.spaces[0]
        sp.shading.type = 'MATERIAL'
        sp.region_3d.view_perspective = 'ORTHO'
        sp.region_3d.view_location = (0, 0, 0.9)
        sp.region_3d.view_distance = 3.0
        sp.region_3d.view_rotation = Quaternion((0.7071, 0.7071, 0, 0))

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("TEMPLATE_V5_DONE")
