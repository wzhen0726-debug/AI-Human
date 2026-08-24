"""制作演示用 blend(原生约束版, 零脚本零授权):
- 单视口: 正视图(看上下左右), 按小键盘3或拖动转侧面看前后凸出
- 右眼 Copy Location 约束跟随左眼(镜像) → 拖左眼, 右眼自动同步
- 视口默认材质预览模式(带贴图, 外行不会以为没材质)
- 默认激活移动工具(XYZ轴gizmo可见) + 左眼默认选中
注意: 视口布局/工具必须在有UI上下文时设置; 后台-b模式无窗口,
      因此改用 --python 在 Blender 正常启动下跑一次自动保存(需短暂弹窗)."""
import bpy, os, sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *

OUT_DIR = os.path.dirname(OUT_BLEND)
DEMO_BLEND = os.path.join(OUT_DIR, "演示_眼球调整.blend")


def setup_constraints():
    """右眼 Copy Location 跟随左眼(镜像同步). 只跟Y/Z, X镜像由左右对称眼球位置天然得到."""
    eyeL = bpy.data.objects.get("Eye002_L")
    eyeR = bpy.data.objects.get("Eye002_R")
    if not eyeL or not eyeR:
        print("!! 找不到 Eye002_L/R")
        return False
    # 清掉右眼旧约束
    for c in list(eyeR.constraints):
        eyeR.constraints.remove(c)
    con = eyeR.constraints.new(type='COPY_LOCATION')
    con.name = "镜像跟随左眼"
    con.target = eyeL
    # 镜像: 以两眼中线为轴. 用Copy Location的invert: X反向, Y/Z同向
    con.use_x = True; con.invert_x = True
    con.use_y = True; con.invert_y = False
    con.use_z = True; con.invert_z = False
    # 关键: 镜像轴心. 两眼x坐标应关于 x=0 对称(L=-0.0355, R=+0.0355, 中线x=0)
    # Copy Location invert_x 使 R.x = -L.x → 只要 L.x=-0.0355 则 R.x=+0.0355 ✓
    con.target_space = 'WORLD'
    con.owner_space = 'WORLD'
    print(f"约束已加: {eyeR.name} 镜像跟随 {eyeL.name}")
    return True


def setup_viewport():
    """单视口拆成左右双视口: 左正视图(前) + 右侧视图, 均材质预览+移动工具."""
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        # 找到第一个3D视口, 水平拆成两个
        v3d = [a for a in screen.areas if a.type == 'VIEW_3D']
        if not v3d:
            continue
        area = v3d[0]
        override = {'window': window, 'screen': screen, 'area': area}
        with bpy.context.temp_override(**override):
            # 只在还没拆分(只有一个视口)时拆一次
            if len([a for a in screen.areas if a.type == 'VIEW_3D']) == 1:
                bpy.ops.screen.area_split(direction='VERTICAL', factor=0.5)
        # 拆分后重新收集视口, 逐个设置
        areas3d = [a for a in screen.areas if a.type == 'VIEW_3D']
        for idx, area in enumerate(areas3d):
            override = {'window': window, 'screen': screen, 'area': area}
            with bpy.context.temp_override(**override):
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'MATERIAL'
                        region3d = space.region_3d
                        if region3d:
                            if idx == 0:
                                region3d.view_perspective = 'ORTHO'
                                # 正视图: 从-Y看向+Y(脸朝-Y, 相机在前方)
                                region3d.view_rotation = (0.7071, 0.7071, 0.0, 0.0)  # 四元数
                            else:
                                region3d.view_perspective = 'ORTHO'
                                # 右侧视: 从+X看
                                region3d.view_rotation = (0.5, 0.5, 0.5, 0.5)
                try:
                    bpy.ops.wm.tool_set_by_id(name="builtin.move")
                except Exception:
                    pass
    print(f"视口: 拆分为{len(areas3d)}个, 左正视/右侧视, 材质预览+移动工具")


def select_eye():
    bpy.ops.object.select_all(action='DESELECT')
    eyeL = bpy.data.objects.get("Eye002_L")
    if eyeL:
        eyeL.select_set(True)
        bpy.context.view_layer.objects.active = eyeL
        print("已选中左眼(移动它, 右眼自动镜像)")


def main():
    bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
    setup_constraints()
    select_eye()
    setup_viewport()
    bpy.ops.wm.save_as_mainfile(filepath=DEMO_BLEND)
    print(f"Saved demo(原生约束版): {DEMO_BLEND}")
    print("done")


if __name__ == "__main__":
    main()
