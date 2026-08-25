"""诊断: 06_rig_markers.blend 的中线偏移 + 文字牌朝向 + 视口状态."""
import bpy, math

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)
dg = bpy.context.evaluated_depsgraph_get()

print("=== 标记点约束生效后的实际位置 ===")
for o in sorted(bpy.data.objects, key=lambda x: x.name):
    if not o.name.startswith("LM_"):
        continue
    ev = o.evaluated_get(dg).matrix_world.translation
    cons = ",".join(c.type for c in o.constraints)
    print(f"{o.name:38s} 约束=[{cons}] 位置=({ev.x:+.3f},{ev.y:+.3f},{ev.z:.3f})")

print("=== 文字牌 ===")
for o in bpy.data.objects:
    if o.type == 'FONT':
        print(f"{o.name}: rot={[round(r,2) for r in o.rotation_euler]}")

print("=== 视口 ===")
for ws in bpy.data.workspaces:
    for scr in ws.screens:
        for area in scr.areas:
            if area.type != 'VIEW_3D':
                continue
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    rv = sp.region_3d
                    print(f"{ws.name}: shading={sp.shading.type} dist={rv.view_distance if rv else None} persp={rv.view_perspective if rv else None}")

print("DIAG_DONE")
