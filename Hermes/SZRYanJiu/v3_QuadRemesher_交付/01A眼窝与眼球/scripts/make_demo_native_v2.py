"""演示blend v2: 双视口聚焦眼部 + 文字提示(纯原生, 零脚本).
- 两个视口view_location对准眼球中心, view_distance缩小 → 打开就是眼部特写
- 视口左上角显示视图名称(text_show_name), 3D场景里加文字牌提示操作
- 眼球联动约束保持不变"""
import bpy, os, sys
from mathutils import Vector, Euler
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *

OUT_DIR = os.path.dirname(OUT_BLEND)
DEMO_BLEND = os.path.join(OUT_DIR, "演示_眼球调整.blend")


def setup_viewport_focus():
    """双视口: 左正视+右侧视, 聚焦到眼球中心, 材质预览+移动工具+视图名称."""
    eyeL = bpy.data.objects.get("Eye002_L")
    eyeR = bpy.data.objects.get("Eye002_R")
    # 眼部中心(两眼之间), 单位米
    center = (eyeL.location + eyeR.location) / 2 if (eyeL and eyeR) else Vector((0, 0, 1.67))

    for window in bpy.context.window_manager.windows:
        screen = window.screen
        areas3d = [a for a in screen.areas if a.type == 'VIEW_3D']
        # 还没拆分则拆
        if len(areas3d) == 1:
            area = areas3d[0]
            with bpy.context.temp_override(window=window, screen=screen, area=area):
                bpy.ops.screen.area_split(direction='VERTICAL', factor=0.5)
            areas3d = [a for a in screen.areas if a.type == 'VIEW_3D']

        for idx, area in enumerate(areas3d):
            with bpy.context.temp_override(window=window, screen=screen, area=area):
                for space in area.spaces:
                    if space.type != 'VIEW_3D':
                        continue
                    space.shading.type = 'MATERIAL'
                    # 显示视图名称/操作提示
                    space.overlay.show_text = True
                    rv = space.region_3d
                    if not rv:
                        continue
                    # 聚焦到眼部: 视野放大35%(原0.06→0.082m), 能看到更多头部上下文
                    rv.view_location = Vector(center)
                    rv.view_distance = 0.082   # 8.2cm视野
                    rv.view_perspective = 'ORTHO'
                    if idx == 0:
                        rv.view_rotation = (0.7071, 0.7071, 0.0, 0.0)  # 正视
                    else:
                        rv.view_rotation = (0.5, 0.5, 0.5, 0.5)        # 右侧视
                try:
                    bpy.ops.wm.tool_set_by_id(name="builtin.move")
                except Exception:
                    pass
    print(f"双视口聚焦眼部完成, 中心={tuple(round(v,3) for v in center)}")


def add_text_hint():
    """场景里加文字牌(眼球正前方, 不被头挡住), 中文提示操作."""
    eyeL = bpy.data.objects.get("Eye002_L")
    eyeR = bpy.data.objects.get("Eye002_R")
    if not eyeL:
        return
    center = (eyeL.location + eyeR.location) / 2
    # 删除旧文字
    for o in [o for o in bpy.data.objects if o.name.startswith("操作提示")]:
        bpy.data.objects.remove(o, do_unlink=True)
    # 文字放在两眼中间正前方(脸朝-Y, 往-Y方向=脸前方), 略高于眉毛(必须在视口±3.9cm内)
    loc = center + Vector((0, -0.075, 0.025))
    cu = bpy.data.curves.new("操作提示_curve", type='FONT')
    cu.body = "拖动眼球上的彩色箭头移动\n右眼自动跟着动\n红=左右 绿=前后 蓝=上下"
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.size = 0.005          # 5mm字高(12字一行约6cm宽, 8.2cm视野放得下)
    cu.space_line = 1.8
    # 关键: 加载微软雅黑, 否则中文渲染不出来(默认字体无CJK字形)
    FONT = r"C:\Windows\Fonts\msyh.ttc"
    if os.path.exists(FONT):
        f = bpy.data.fonts.load(FONT)
        cu.font = f
        cu.font_bold = f
        print(f"已加载中文字体: {FONT}")
    else:
        print(f"!! 找不到字体 {FONT}, 中文可能显示为方框")
    ob = bpy.data.objects.new("操作提示", cu)
    ob.location = loc
    # 面朝前方(-Y): 文字默认面朝+Z, 绕X转90度使面朝-Y
    ob.rotation_euler = Euler((math.radians(90), 0, 0), 'XYZ')
    mat = bpy.data.materials.new("提示黄")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (1.0, 0.8, 0.05, 1)
        bsdf.inputs["Emission Color"].default_value = (1.0, 0.8, 0.05, 1)
        bsdf.inputs["Emission Strength"].default_value = 3.0
    cu.materials.append(mat)
    bpy.context.scene.collection.objects.link(ob)
    print(f"已加文字提示牌 位置={[round(v,3) for v in loc]}")


def setup_constraints_and_select():
    eyeL = bpy.data.objects.get("Eye002_L")
    eyeR = bpy.data.objects.get("Eye002_R")
    for c in list(eyeR.constraints):
        eyeR.constraints.remove(c)
    con = eyeR.constraints.new(type='COPY_LOCATION')
    con.name = "镜像跟随左眼"
    con.target = eyeL
    con.use_x = True; con.invert_x = True
    con.use_y = True; con.invert_y = False
    con.use_z = True; con.invert_z = False
    con.target_space = 'WORLD'; con.owner_space = 'WORLD'
    bpy.ops.object.select_all(action='DESELECT')
    eyeL.select_set(True)
    bpy.context.view_layer.objects.active = eyeL
    print("约束+选中左眼完成")


def main():
    bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
    setup_constraints_and_select()
    setup_viewport_focus()
    add_text_hint()
    bpy.ops.wm.save_as_mainfile(filepath=DEMO_BLEND)
    print(f"Saved demo v2: {DEMO_BLEND}")
    print("done")


if __name__ == "__main__":
    main()
