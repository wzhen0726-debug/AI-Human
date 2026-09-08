"""03 自动UV: Smart UV Project (2026-09-08 A方案: 去掉rim倒角环节)

输入: 02_qr_150k.blend (QR低模, 干净无倒角权重)
输出: 03_auto_uv.blend

历史: 旧版先应用"RimBevel"倒角修改器再UV展开(文件夹曾名03自动UV_rim_bevel)。
2026-09-08实测该倒角链失效: rim预锐化的bevel权重被bm.to_mesh冲掉→高模倒角空转→
QR没拿到眼睑缘引导→低模无rim边环→倒角只能落在散碎边上(276条, 眼周碎线带权重),
既不连续也无锐化效果。整套机制已删除, 眼睑缘锐利度由烘焙法线贴图从高模获取。
本脚本主动剥离任何残留的bevel_weight_edge/crease属性, 保证下游不再出现权重线."""
import bpy, os, math

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付"
QR_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend")
OUT_03 = os.path.join(DELIVERY, "03自动UV")
os.makedirs(OUT_03, exist_ok=True)

print("=== Step 3: Auto UV (A方案, 无倒角) ===")
bpy.ops.wm.open_mainfile(filepath=QR_BLEND)
mesh = max([o for o in bpy.data.objects if o.type == 'MESH'],
           key=lambda o: len(o.data.vertices))
print(f"低模: {mesh.name}, {len(mesh.data.vertices):,}顶点 {len(mesh.data.polygons):,}面")

# ---- 剥离残留倒角/折痕属性 + 无用修改器(防御: 输入若来自旧产物也保证干净) ----
removed_attr = []
for name in ("bevel_weight_edge", "bevel_weight_vert", "crease_edge", "crease_vert"):
    a = mesh.data.attributes.get(name)
    if a is not None:
        mesh.data.attributes.remove(a)
        removed_attr.append(name)
removed_mod = [m.name for m in mesh.modifiers if m.type == 'BEVEL']
for m in list(mesh.modifiers):
    if m.type == 'BEVEL':
        mesh.modifiers.remove(m)
print(f"剥离属性: {removed_attr if removed_attr else '无(输入已干净)'} 移除BEVEL修改器: {removed_mod if removed_mod else '无'}")

# ---- 变换归零检查(FBX导入残留微旋转不能带进UV/烘焙) ----
rot = tuple(round(r, 9) for r in mesh.rotation_euler)
print(f"对象旋转: {rot}")
if any(abs(r) > 1e-9 for r in mesh.rotation_euler):
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    print(f"  已归零 -> {tuple(round(r,9) for r in mesh.rotation_euler)}")

# ---- UV展开 ----
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

uv_layer = mesh.data.uv_layers.active
us = [l.uv[0] for l in uv_layer.data]
vs = [l.uv[1] for l in uv_layer.data]
print(f"UV范围: U[{min(us):.3f}, {max(us):.3f}] V[{min(vs):.3f}, {max(vs):.3f}]")
print(f"UV岛边距: 0.01 角度限制: 66°")

# ---- 自查: 确认无bevel权重残留 ----
assert mesh.data.attributes.get("bevel_weight_edge") is None, "bevel_weight_edge未清除!"
assert not [m for m in mesh.modifiers if m.type == 'BEVEL'], "BEVEL修改器未清除!"
print("自查: 无倒角权重/无BEVEL修改器 PASS")

out_blend = os.path.join(OUT_03, "03_auto_uv.blend")
bpy.ops.wm.save_mainfile(filepath=out_blend)
print(f"已保存: {out_blend}")
print("UV_DONE")
