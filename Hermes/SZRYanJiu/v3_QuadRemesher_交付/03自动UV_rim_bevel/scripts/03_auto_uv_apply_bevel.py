"""rim倒角版UV: 先应用倒角修改器(固化几何), 再UV展开."""
import bpy, os, math

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
BEVEL_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_rim_bevel.blend")
OUT_03 = os.path.join(DELIVERY, "03自动UV_rim_bevel")
os.makedirs(OUT_03, exist_ok=True)

print("=== Step 3: Auto UV (rim倒角版, 先应用倒角) ===")

bpy.ops.wm.open_mainfile(filepath=BEVEL_BLEND)
mesh = max([o for o in bpy.data.objects if o.type == 'MESH'],
           key=lambda o: len(o.data.vertices))
print(f"低模: {mesh.name}, {len(mesh.data.polygons)}面")

# 关键: 先应用倒角修改器(固化rim锐利几何)
bpy.context.view_layer.objects.active = mesh
if mesh.modifiers.get("RimBevel"):
    bpy.ops.object.modifier_apply(modifier="RimBevel")
    print("倒角修改器已应用")
print(f"应用倒角后: {len(mesh.data.polygons)}面")

# UV展开
bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(
    angle_limit=math.radians(66.0),
    island_margin=0.01,
    area_weight=0.0,
    correct_aspect=True,
    scale_to_bounds=False
)
bpy.ops.object.mode_set(mode='OBJECT')

# 统计
uv_layer = mesh.data.uv_layers.active
us = [l.uv[0] for l in uv_layer.data]
vs = [l.uv[1] for l in uv_layer.data]
print(f"UV范围: U[{min(us):.3f}, {max(us):.3f}] V[{min(vs):.3f}, {max(vs):.3f}]")

out_blend = os.path.join(OUT_03, "03_auto_uv.blend")
bpy.ops.wm.save_mainfile(filepath=out_blend)
print(f"已保存: {out_blend}")
print("UV_DONE")
