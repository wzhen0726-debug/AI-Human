"""诊断: 文字牌位置 + 视口相机参数."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)
bpy.context.view_layer.update()

print("=== 文字牌 ===")
for o in bpy.data.objects:
    if o.type == 'FONT' and o.name.startswith("打点操作提示"):
        v = o.matrix_world.translation
        print(f"  {o.name}: ({v.x:.3f}, {v.y:.3f}, {v.z:.3f}) rot={tuple(round(x,3) for x in o.rotation_euler)}")

print("\n=== 视口参数(全部工作区) ===")
for ws in bpy.data.workspaces:
    for scr in ws.screens:
        for area in scr.areas:
            if area.type != 'VIEW_3D':
                continue
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    print(f"  shading={sp.shading.type}, dist={sp.region_3d.view_distance}")
                    print(f"  loc={tuple(round(x,3) for x in sp.region_3d.view_location)}")
                    print(f"  rot={tuple(round(x,3) for x in sp.region_3d.view_rotation)}")
                    print(f"  persp={sp.region_3d.view_perspective}")
                    break

print("DIAG_VIEWPORT_DONE")
