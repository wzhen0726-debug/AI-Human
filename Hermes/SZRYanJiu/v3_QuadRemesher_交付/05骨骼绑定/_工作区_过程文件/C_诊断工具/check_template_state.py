"""检查06_rig_markers.blend当前真实状态: 视口/标记点/约束/对象."""
import bpy, os

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

print("=== 工作区视口状态 ===")
for ws in bpy.data.workspaces:
    for scr in ws.screens:
        for area in scr.areas:
            if area.type != 'VIEW_3D':
                continue
            for sp in area.spaces:
                if sp.type != 'VIEW_3D':
                    continue
                rv = sp.region_3d
                print(f"  {ws.name}/{scr.name}: shading={sp.shading.type}, dist={round(rv.view_distance,2) if rv else None}, loc={[round(v,2) for v in rv.view_location] if rv else None}")

print("=== 标记点 ===")
for o in sorted([o for o in bpy.data.objects if o.name.startswith("LM_")], key=lambda o: o.name):
    cons = [c.type for c in o.constraints]
    print(f"  {o.name} @ {[round(v,3) for v in o.location]} 约束={cons}")

print("=== 其他对象 ===")
for o in bpy.data.objects:
    if not o.name.startswith("LM_"):
        print(f"  {o.name}: {o.type}")

print("STATE_CHECK_DONE")
