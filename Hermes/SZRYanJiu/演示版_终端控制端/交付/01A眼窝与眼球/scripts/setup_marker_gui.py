# -*- coding: utf-8 -*-
"""01A 打点 GUI 打开时的视口设置(控制台启动 Blender 时 --python 带入):
① 正视图对准右眼打点区 ② Material Preview 着色(显示纹理) ③ 确认面捕捉开启.
防御式写法: 找不到3D视口/标记集合就静默跳过, 不阻塞用户操作."""
import bpy

# ---- 1) 找右眼标记点, 算视口中心与距离 ----
center = None
try:
    coll = bpy.data.collections.get("LM_R")
    pts = [o.location[:] for o in coll.objects if o.type == 'EMPTY'] if coll else []
    if pts:
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; zs = [p[2] for p in pts]
        center = ((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2)
        span = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
except Exception as e:
    print("setup_marker_gui: 标记点解析失败:", e)

if center is None:
    # 退而求其次: 用网格对象包围盒中心的上部(头)
    mesh = next((o for o in bpy.data.objects if o.type == 'MESH'), None)
    if mesh:
        import mathutils
        corners = [mesh.matrix_world @ mathutils.Vector(c) for c in mesh.bound_box]
        cz = max(c.z for c in corners)
        center = (0.0, min(c.y for c in corners) + 0.05, cz - 0.08)
        span = 0.15

# ---- 2) 遍历所有3D视口: 正交前视图 + 对准 + Material Preview ----
for window in bpy.context.window_manager.windows:
    for area in window.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        space = area.spaces.active
        # 显示纹理
        try:
            space.shading.type = 'MATERIAL'
        except Exception:
            pass
        r3d = space.region_3d
        r3d.view_perspective = 'ORTHO'
        from mathutils import Vector, Quaternion
        # 前视图: 相机朝+Y看, 上为Z
        r3d.view_rotation = Quaternion((1, 0, 0, 0))  # identity = 前视
        r3d.view_location = Vector(center)
        # 正交缩放: 视野包住打点区留余量 (span单位是米)
        r3d.view_distance = 0.5
        try:
            space.region_3d.view_camera_zoom = 0
        except Exception:
            pass
        # ortho scale 通过 view_distance 在正交下无效, 用 ops 更稳
        for region in area.regions:
            if region.type == 'WINDOW':
                with bpy.context.temp_override(window=window, area=area, region=region):
                    bpy.ops.view3d.view_axis(type='FRONT')
                    try:
                        space.region_3d.view_location = Vector(center)
                        # 正交视野比例: ortho_scale 是视图宽度(米)
                        space.region_3d.ortho_scale = max(span * 3.0, 0.15)
                    except Exception:
                        pass

# ---- 3) 面捕捉兜底(万一 blend 里没存上) ----
ts = bpy.context.scene.tool_settings
ts.use_snap = True
try:
    ts.snap_elements = {'FACE'}
except (TypeError, AttributeError):
    try:
        ts.snap_elements_base = {'FACE'}
    except AttributeError:
        pass

print("setup_marker_gui: 视图已对准眼部, Material Preview + 面捕捉已开启")
