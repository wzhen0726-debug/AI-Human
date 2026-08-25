"""测试: -b后台模式下, 能否设置视口并持久化(工作区/屏幕/区域数据块)."""
import bpy

print("=== windows ===")
print("window数:", len(bpy.context.window_manager.windows))

print("=== bpy.data.workspaces ===")
for ws in bpy.data.workspaces:
    print(f"  workspace: {ws.name}")
    for scr in ws.screens:
        areas3d = [a for a in scr.areas if a.type == 'VIEW_3D']
        print(f"    screen: {scr.name}, 3D区域数={len(areas3d)}")
        for area in areas3d:
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    print(f"      space shading={sp.shading.type}, region_3d={sp.region_3d is not None}")

# 尝试在数据块上设置
set_ok = False
for ws in bpy.data.workspaces:
    for scr in ws.screens:
        for area in scr.areas:
            if area.type != 'VIEW_3D':
                continue
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    sp.shading.type = 'MATERIAL'
                    rv = sp.region_3d
                    if rv:
                        from mathutils import Vector
                        rv.view_location = Vector((0, 0, 0.9))
                        rv.view_distance = 3.0
                        rv.view_perspective = 'ORTHO'
                    set_ok = True
print("设置到数据块:", set_ok)

OUT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\logs\_viewport_test.blend"
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("SAVED_TEST")
