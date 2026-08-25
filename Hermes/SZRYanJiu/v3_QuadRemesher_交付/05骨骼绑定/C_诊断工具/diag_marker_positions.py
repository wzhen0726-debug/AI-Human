"""检查: 标记点约束生效后的实际位置(是否偏离中线) + 文字牌朝向."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

# 评估约束后的实际位置
dg = bpy.context.evaluated_depsgraph_get()

print("=== 标记点: 原始位置 vs 约束生效后位置 ===")
for o in sorted(bpy.data.objects, key=lambda o: o.name):
    if not o.name.startswith("LM_"):
        continue
    oe = o.evaluated_get(dg)
    loc_eval = oe.matrix_world.translation
    cons = [c.type for c in o.constraints]
    off = loc_eval.x
    flag = " ←偏离中线!" if o.name.startswith("LM_0") and abs(off) > 0.01 else ""
    print(f"{o.name:38s} 约束={cons} 约束后=({loc_eval.x:+.3f},{loc_eval.y:+.3f},{loc_eval.z:.3f}){flag}")

print("\n=== 文字牌朝向 ===")
for o in bpy.data.objects:
    if o.type == 'FONT':
        print(f"{o.name}: rotation_euler={[round(r,3) for r in o.rotation_euler]} "
              f"(0,0,0)=平躺面朝上 ←如果这样就是错的")

print("\nDIAG_VIEWPORT2_DONE")
