"""清理ARP Godot版的残留: 孤立顶点组 + 4根无权重骨骼(HeadTop_End/Toe_End/Spine特殊处理)."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
IN = os.path.join(BASE, "B_骨骼绑定", "06_rig_arp_godot.blend")
OUT_GLB = os.path.join(BASE, "B_骨骼绑定", "06_rig_arp_godot.glb")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=IN)

arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
body = max((o for o in bpy.data.objects if o.type == 'MESH' and 'eye' not in o.name.lower()),
           key=lambda o: len(o.data.polygons))

# ===== 1) Spine无权重诊断: ARP把spine01-03弯骨当躯干变形骨, mixamo:Spine是中转 =====
# 查Spine是否有任何顶点引用
vg_spine = body.vertex_groups.get("Spine")
n_spine = sum(1 for v in body.data.vertices
              for g in v.groups if g.group == vg_spine.index and g.weight > 0.001) if vg_spine else -1
print(f"Spine组顶点数: {n_spine}")
# 若确实0权重 → 保留骨骼但顶点组无害; 躯干由 spine_01/02/03_bend 驱动!
# 关键: ARP的躯干变形走 c_spine_XX_bend.x 顶点组 — 这些必须映射到mixamo脊柱!

# ===== 2) bend顶点组的权重迁移到Mixamo标准名 =====
bend_map = {
    "c_spine_01_bend.x": "Spine",
    "c_spine_02_bend.x": "Spine1",
    "c_spine_03_bend.x": "Spine2",
}
def transfer_weights(src_name, dst_name):
    src = body.vertex_groups.get(src_name)
    dst = body.vertex_groups.get(dst_name)
    if src is None:
        print(f"  源组不存在: {src_name}")
        return
    if dst is None:
        dst = body.vertex_groups.new(name=dst_name)
    moved = 0
    for v in body.data.vertices:
        for g in v.groups:
            if g.group == src.index and g.weight > 0.0001:
                # 注意同顶点多组累加逻辑: 简单加法(ARP已保证权重归一在各组内独立)
                dst.add([v.index], g.weight, 'ADD')
                moved += 1
                break
    print(f"  {src_name} → {dst_name}: {moved}顶点")

print("bend权重迁移:")
for s, d in bend_map.items():
    transfer_weights(s, d)

# legs/arm .001重复组也迁给同名主组
for suffix in (".001",):
    for g in list(body.vertex_groups):
        if g.name.endswith(suffix) and g.name[:-4] in {v.name for v in body.vertex_groups}:
            transfer_weights(g.name, g.name[:-4])

# ===== 3) 删除孤立顶点组 =====
bnames = {b.name for b in arm.data.bones}
removed_vg = []
for g in list(body.vertex_groups):
    if g.name not in bnames:
        removed_vg.append(g.name)
        body.vertex_groups.remove(g)
print(f"删除孤立顶点组: {len(removed_vg)}")

# ===== 4) 删除永远无权重的端点骨(不参与变形, glTF里也无意义) =====
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones
for nm in ("HeadTop_End", "LeftToe_End", "RightToe_End"):
    b = eb.get(nm)
    if b:
        eb.remove(b)
        print("删端点骨:", nm)
bpy.ops.object.mode_set(mode='OBJECT')

# ===== 5) 验证+保存+导出 =====
bnames2 = {b.name for b in arm.data.bones}
vg2 = {g.name for g in body.vertex_groups}
print(f"最终: 骨骼{len(bnames2)}, 匹配{len(bnames2 & vg2)}/{len(bnames2)}")
zero = sum(1 for v in body.data.vertices if not any(g.weight > 0.001 for g in v.groups))
total = len(body.data.vertices)
print(f"权重覆盖: {total-zero}/{total} ({100*(total-zero)/total:.1f}%)")

mid = OUT_GLB.replace('.glb', '.blend')
bpy.ops.wm.save_as_mainfile(filepath=mid)
print(f"保存: {mid}")

bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format='GLB', export_apply=True,
                          export_texcoords=True, export_normals=True, export_materials='EXPORT')
print(f"GLB: {OUT_GLB} ({os.path.getsize(OUT_GLB)/(1024*1024):.1f} MB)")
print("CLEANUP_DONE")
