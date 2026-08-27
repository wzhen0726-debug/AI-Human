"""ARP版去控制器 → Godot可用GLB (2026-08-27).
用户需求: Godot只要模型跟骨骼, 控制器不支持.
流程: 打开06_rig_arp_mixamo.blend(65 Mixamo命名骨骼) →
      ①保留变形骨骼(mixamorig:前缀), 删除ARP机制骨(cs_/c_/ctp_/msn_等非mixamorig骨)
      ②删全部约束/驱动器
      ③确认mesh的armature修改器指向骨架, 顶点组匹配
      ④导出GLB(仅变形骨骼进glTF)."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
IN = os.path.join(BASE, "B_骨骼绑定", "06_rig_arp_mixamo.blend")
OUT_GLB = os.path.join(BASE, "B_骨骼绑定", "06_rig_arp_godot.glb")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=IN)

arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
body = max((o for o in bpy.data.objects if o.type == 'MESH' and 'eye' not in o.name.lower()),
           key=lambda o: len(o.data.polygons))
print(f"清理前: {len(arm.data.bones)}骨")

# ===== 1) 编辑模式: 白名单保留变形骨骼 =====
# 教训(2026-08-27): 不能用"mixamorig:前缀"过滤 — arp_to_mixamo.py产出的名字无前缀
# (实测: Hips/LeftArm/HeadTop_End...), 全被误删成空骨架!
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones
MIXAMO65 = {
    "Hips", "Spine", "Spine1", "Spine2", "Neck", "Head", "HeadTop_End",
    "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
    "RightShoulder", "RightArm", "RightForeArm", "RightHand",
    "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase", "LeftToe_End",
    "RightUpLeg", "RightLeg", "RightFoot", "RightToeBase", "RightToe_End",
}
for f in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
    for i in (1, 2, 3):
        MIXAMO65.add(f"LeftHand{f}{i}")
        MIXAMO65.add(f"RightHand{f}{i}")
keep = [b for b in eb if b.name in MIXAMO65]
remove = [b for b in eb if b.name not in MIXAMO65]
print(f"保留变形骨: {len(keep)}, 删除机制/控制器骨: {len(remove)}")
removed_names = [b.name for b in remove][:5]
if removed_names:
    print("删除样例:", removed_names)
for b in remove:
    eb.remove(b)
# 断开use_connect残留(父级被删后可能出现孤立连接标志)
for b in eb:
    b.use_connect = False
bpy.ops.object.mode_set(mode='OBJECT')

# 解除mesh与cs_grp等空对象的父子(ARP会挂到控制器组)
if body.parent and body.parent != arm:
    M = body.matrix_world.copy()
    body.parent = None
    body.matrix_world = M

# ===== 2) 删除约束与驱动器 =====
nc = 0
for pb in arm.pose.bones:
    for c in list(pb.constraints):
        pb.constraints.remove(c)
        nc += 1
nd = 0
if arm.animation_data:
    for d in list(arm.animation_data.drivers):
        arm.animation_data.drivers.remove(d)
        nd += 1
    arm.animation_data.action = None
print(f"删除约束{nc}, 驱动器{nd}")

# 其他对象上的驱动器也清掉
for o in bpy.data.objects:
    if o.animation_data:
        for d in list(o.animation_data.drivers):
            o.animation_data.drivers.remove(d)

# ===== 3) mesh修改器与顶点组核对 =====
mods = [m for m in body.modifiers if m.type == 'ARMATURE']
if mods:
    mods[0].object = arm
else:
    body.parent = arm
    m = body.modifiers.new('Armature', 'ARMATURE')
    m.object = arm
bnames = {b.name for b in arm.data.bones}
vgroups = {g.name for g in body.vertex_groups}
matched = len(bnames & vgroups)
print(f"修改器OK: {len(mods)}, 骨骼{len(bnames)}, 顶点组匹配{matched}/{len(bnames)}")

zero = sum(1 for v in body.data.vertices if not any(g.weight > 0.001 for g in v.groups))
total = len(body.data.vertices)
print(f"权重覆盖: {total-zero}/{total} ({100*(total-zero)/total:.1f}%)")

# 姿态纯净
for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.rotation_quaternion = (1, 0, 0, 0)
    pb.location = (0, 0, 0)

# 保存中间blend
mid_blend = OUT_GLB.replace('.glb', '.blend')
bpy.ops.wm.save_as_mainfile(filepath=mid_blend)
print(f"保存: {mid_blend}")

# ===== 4) 导出Godot GLB =====
bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format='GLB',
    export_apply=True,
    export_texcoords=True,
    export_normals=True,
    export_materials='EXPORT',
)
print(f"GLB: {OUT_GLB} ({os.path.getsize(OUT_GLB)/(1024*1024):.1f} MB)")
print("GODOT_EXPORT_DONE")
