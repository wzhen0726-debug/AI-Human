"""ARP版完整绑定流程 — 从04烘焙输出重跑 (2026-08-28).
链路: 04_bake身体 → AI打点17点 → go_detect → 参考骨提取55骨 →
      align_roll → use_connect → 自动权重 → 行走动画验证.
输出: _工作区_过程文件/ARP重跑_20260828/步骤编号文件."""
import bpy, sys, os, math, json, subprocess
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\_工作区_过程文件"
BAKE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\04纹理烘焙\04_bake.blend"
WALK_FBX = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx"
AI_PATH = r"C:\Users\Liyunzhong\Documents\AutoRigPro\AI"
OUT = os.path.join(BASE, "ARP重跑_20260828")
os.makedirs(OUT, exist_ok=True)
SPEC = os.path.join(BASE, "logs", "mixamo_rest_spec.json")

# ============ 步骤1: AI打点 ============
print("\n########## 步骤1: AI打点 ##########")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module='auto_rig_pro-master')
bpy.context.preferences.addons['auto_rig_pro-master'].preferences.ai_presets_path = AI_PATH

for key, mod in list(sys.modules.items()):
    if 'auto_rig' in key and hasattr(mod, 'display_popup_message'):
        mod.display_popup_message = lambda m, h=' ', i='': print(f"[ARP {h}] {m}")
        break

ars = None
for key, mod in list(sys.modules.items()):
    if 'auto_rig_smart' in key and hasattr(mod, '_screenshot_char'):
        ars = mod
        break

# 截图补丁(256分辨率+灰模Emission+self写回)
def screenshot_patched(self):
    scn = bpy.context.scene
    orig_engine = scn.render.engine
    ox, oy = scn.render.resolution_x, scn.render.resolution_y
    scn.render.engine = 'BLENDER_EEVEE'
    scn.render.resolution_x = 256
    scn.render.resolution_y = 256
    scn.render.image_settings.file_format = 'JPEG'
    body_temp = bpy.data.objects.get('body_temp')
    if not body_temp:
        print("ERROR: body_temp缺失")
        return
    mat = bpy.data.materials.new("arp_gray")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    emit = nodes.new('ShaderNodeEmission')
    emit.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1.0)
    emit.inputs["Strength"].default_value = 1.0
    mat.node_tree.links.new(emit.outputs["Emission"], nodes["Material Output"].inputs["Surface"])
    body_temp.data.materials.clear()
    body_temp.data.materials.append(mat)
    self.front_samples_rot = [0.0]
    if scn.world is None:
        scn.world = bpy.data.worlds.new("arp_bg")
    scn.world.use_nodes = True
    bg = scn.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.04, 0.04, 0.04, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    corners = [body_temp.matrix_world @ Vector(c) for c in body_temp.bound_box]
    x1, x2 = corners[0][0], corners[4][0]
    y1, y2 = corners[0][1], corners[6][1]
    z1, z2 = corners[0][2], corners[2][2]
    dx, dy, dz = abs(x2-x1), abs(y2-y1), abs(z2-z1)
    mx, my, mz = (x1+x2)/2, (y1+y2)/2, (z1+z2)/2
    lower_y, gx, gz = min(y1, y2), max(x1, x2), max(z1, z2)
    l1, l2, l3 = max(dx, dz), max(dy, dz), max(dy, dx)
    margin = 1.35
    self.larger_dim, self.larger_dimy, self.larger_dimtop = l1, l2, l3
    self.midx, self.midy, self.midz = mx, my, mz
    self.margin = margin
    cam_data = bpy.data.cameras.new("arp_cam_char")
    cam_data.type = 'ORTHO'
    cam_data.clip_end = 50000
    cam_obj = bpy.data.objects.new("arp_cam_char", cam_data)
    scn.collection.objects.link(cam_obj)
    scn.camera = cam_obj
    inf = self.inf_path
    def rv(name, loc, rot, ortho):
        cam_obj.location, cam_obj.rotation_euler = loc, rot
        cam_obj.data.ortho_scale = ortho
        scn.render.filepath = os.path.join(inf, name)
        bpy.ops.render.render(write_still=True)
    rv("front1.jpg", (mx, lower_y - dy*10, mz), (math.pi/2, 0, 0), l1*margin)
    rv("char_side.jpg", (gx + dx*10, my, mz), (math.pi/2, 0, math.pi/2), l2*margin)
    rv("char_top.jpg", (mx, my, gz + dz*10), (0, 0, 0), l3*margin)
    bpy.data.objects.remove(cam_obj, do_unlink=True)
    bpy.data.cameras.remove(cam_data)
    scn.render.engine, scn.render.resolution_x, scn.render.resolution_y = orig_engine, ox, oy

if ars:
    ars._screenshot_char = screenshot_patched
    print("截图补丁OK")

# 打开烘焙输出, 只留身体
bpy.ops.wm.open_mainfile(filepath=BAKE)
for o in list(bpy.data.objects):
    if o.type != 'MESH':
        bpy.data.objects.remove(o, do_unlink=True)
body = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices))
print(f"身体: {body.name}, {len(body.data.vertices)}顶点")

bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.context.window.screen = bpy.data.screens['Layout']
area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')
scn = bpy.context.scene

with bpy.context.temp_override(area=area, region=region):
    bpy.ops.id.get_selected_objects('EXEC_DEFAULT')
    scn.arp_smart_AI_body_samples = 1
    bpy.ops.arp.guess_markers('EXEC_DEFAULT')
    print("guess_markers OK")

    # ============ 步骤2: go_detect ============
    print("\n########## 步骤2: go_detect ##########")
    scn.arp_smart_depth = False
    scn.arp_smart_fingers_engine = 'LEGACY'
    bpy.ops.id.go_detect('EXEC_DEFAULT')
    print("go_detect OK")

rig = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
assert rig, "go_detect未生成骨架"
ref_count = len([b for b in rig.data.bones if '_ref' in b.name])
print(f"ARP骨架: {len(rig.data.bones)}骨, 参考骨{ref_count}根")

# ============ 步骤3: 参考骨提取 ============
print("\n########## 步骤3: 参考骨提取(55骨Mixamo命名) ##########")
mw = rig.matrix_world
def whead(name):
    return mw @ rig.data.bones[name].head_local
def wtail(name):
    return mw @ rig.data.bones[name].tail_local

MAP = [("Hips", None, "root_ref.x", "root_ref.x"),
       ("Spine", "Hips", "spine_01_ref.x", "spine_01_ref.x"),
       ("Spine1", "Spine", "spine_02_ref.x", "spine_02_ref.x"),
       ("Spine2", "Spine1", "spine_03_ref.x", "spine_03_ref.x"),
       ("Neck", "Spine2", "neck_ref.x", "neck_ref.x"),
       ("Head", "Neck", "head_ref.x", "head_ref.x"),
       ("HeadTop_End", "Head", "SPECIAL_HEADTOP", None)]
for side, pre in [("l", "Left"), ("r", "Right")]:
    s = "." + side
    MAP += [
        (f"{pre}Shoulder", "Spine2", f"shoulder_ref{s}", f"shoulder_ref{s}"),
        (f"{pre}Arm", f"{pre}Shoulder", f"arm_ref{s}", f"arm_ref{s}"),
        (f"{pre}ForeArm", f"{pre}Arm", f"forearm_ref{s}", f"forearm_ref{s}"),
        (f"{pre}Hand", f"{pre}ForeArm", f"hand_ref{s}", f"HEAD_middle1_ref{s}"),
        (f"{pre}HandThumb1", f"{pre}Hand", f"thumb1_ref{s}", f"thumb1_ref{s}"),
        (f"{pre}HandThumb2", f"{pre}HandThumb1", f"thumb2_ref{s}", f"thumb2_ref{s}"),
        (f"{pre}HandThumb3", f"{pre}HandThumb2", f"thumb3_ref{s}", f"thumb3_ref{s}"),
    ]
    for f in ["index", "middle", "ring", "pinky"]:
        F = f.capitalize()
        MAP += [
            (f"{pre}Hand{F}1", f"{pre}Hand", f"{f}1_ref{s}", f"{f}1_ref{s}"),
            (f"{pre}Hand{F}2", f"{pre}Hand{F}1", f"{f}2_ref{s}", f"{f}2_ref{s}"),
            (f"{pre}Hand{F}3", f"{pre}Hand{F}2", f"{f}3_ref{s}", f"{f}3_ref{s}"),
        ]
    MAP += [
        (f"{pre}UpLeg", "Hips", f"thigh_ref{s}", f"thigh_ref{s}"),
        (f"{pre}Leg", f"{pre}UpLeg", f"leg_ref{s}", f"leg_ref{s}"),
        (f"{pre}Foot", f"{pre}Leg", f"foot_ref{s}", f"foot_ref{s}"),
        (f"{pre}ToeBase", f"{pre}Foot", f"toes_ref{s}", f"toes_ref{s}"),
        (f"{pre}Toe_End", f"{pre}ToeBase", "SPECIAL_TOE", s),
    ]

# 清body旧绑定
body.modifiers.clear()
body.vertex_groups.clear()

# 建新骨架
arm_data = bpy.data.armatures.new("MixamoSkeleton")
arm = bpy.data.objects.new("MixamoSkeleton", arm_data)
bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm_data.edit_bones

created = {}
for name, parent, hsrc, tsrc in MAP:
    b = eb.new(name)
    if tsrc and tsrc.startswith("HEAD_"):
        b.head = whead(hsrc)
        b.tail = whead(tsrc[5:])
    elif hsrc == "SPECIAL_HEADTOP":
        h = wtail("head_ref.x")
        b.head = h
        b.tail = h + Vector((0, 0, 0.10))
    elif hsrc == "SPECIAL_TOE":
        h = wtail(f"toes_ref{tsrc}")
        d = (wtail(f"toes_ref{tsrc}") - whead(f"toes_ref{tsrc}")).normalized()
        b.head = h
        b.tail = h + d * 0.05
    else:
        b.head = whead(hsrc)
        b.tail = wtail(tsrc if tsrc else hsrc)
    if (b.tail - b.head).length < 0.005:
        b.tail = b.head + Vector((0, 0, 0.02))
    created[name] = b
for name, parent, _, _ in MAP:
    if parent:
        created[name].parent = created[parent]
print(f"新骨架: {len(created)}骨")

# ============ 步骤4: align_roll ============
print("\n########## 步骤4: align_roll对齐Mixamo ##########")
spec = json.load(open(SPEC, encoding="utf-8"))["bones"]
aligned, skipped = 0, []
for b in eb:
    sb = spec.get("mixamorig:" + b.name)
    if not sb:
        skipped.append(b.name)
        continue
    z = Vector(sb["z"])
    if z.length > 0.01:
        b.align_roll(z)   # 只改roll, 不动head/tail
    aligned += 1
print(f"roll对齐: {aligned}骨, 跳过: {skipped}")

# ============ 步骤5: use_connect ============
n_conn = 0
for b in eb:
    if b.parent and (b.head - b.parent.tail).length < 0.002:
        b.use_connect = True
        n_conn += 1
print(f"use_connect: {n_conn}根")
bpy.ops.object.mode_set(mode='OBJECT')

# 删旧ARP rig
bpy.data.objects.remove(rig, do_unlink=True)

# ============ 步骤6: 自动权重 ============
print("\n########## 步骤6: 自动权重 ##########")
for o in bpy.data.objects:
    o.select_set(False)
body.select_set(True)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
print(f"权重顶点组: {len(body.vertex_groups)}")

step06 = os.path.join(OUT, "06_骨骼绑定_重跑.blend")
bpy.ops.wm.save_mainfile(filepath=step06)
print(f"保存: {step06}")

# ============ 步骤7: 行走动画验证 ============
print("\n########## 步骤7: 行走动画验证 ##########")
# 加mixamorig前缀
for b in arm.data.bones:
    if not b.name.startswith("mixamorig:"):
        b.name = "mixamorig:" + b.name
for vg in body.vertex_groups:
    if not vg.name.startswith("mixamorig:"):
        vg.name = "mixamorig:" + vg.name

bpy.ops.import_scene.fbx(filepath=WALK_FBX)
walk_arm = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE' and o.name != 'MixamoSkeleton' and o.animation_data and o.animation_data.action:
        walk_arm = o
assert walk_arm, "行走FBX导入失败"
action = walk_arm.animation_data.action
rig_action = action.copy()
rig_action.name = "Walk_noroot"

data_slot = None
removed = 0
for layer in rig_action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            if len(bag.fcurves) > 0:
                data_slot = next((s for s in rig_action.slots if s.handle == bag.slot_handle), None)
                for fc in list(bag.fcurves):
                    if 'mixamorig:Hips' in fc.data_path and 'location' in fc.data_path:
                        bag.fcurves.remove(fc)
                        removed += 1
                break
assert data_slot
print(f"数据slot: {data_slot.identifier}, 删Hips位移{removed}条")

if arm.animation_data is None:
    arm.animation_data_create()
arm.animation_data.action = rig_action
arm.animation_data.action_slot = data_slot

# 删参考对象
del_names = [o.name for o in bpy.data.objects if o.name != 'MixamoSkeleton' and o.name != body.name and 'Eye' not in o.name]
for nm in del_names:
    o = bpy.data.objects.get(nm)
    if o and o.type in ('ARMATURE', 'MESH'):
        bpy.data.objects.remove(o, do_unlink=True)

scn.frame_start = int(action.frame_range[0])
scn.frame_end = int(action.frame_range[1])

dg = bpy.context.evaluated_depsgraph_get()
body_ev = body.evaluated_get(dg)
scn.frame_set(1); bpy.context.view_layer.update()
base_v = [v.co.copy() for v in body_ev.data.vertices[:3000]]
lh1 = (arm.matrix_world @ arm.pose.bones['mixamorig:LeftHand'].matrix).translation.copy()
scn.frame_set(18); bpy.context.view_layer.update()
moved = sum(1 for i, v in enumerate(body_ev.data.vertices[:3000]) if (v.co - base_v[i]).length > 0.01)
lh18 = (arm.matrix_world @ arm.pose.bones['mixamorig:LeftHand'].matrix).translation.copy()
rf18 = (arm.matrix_world @ arm.pose.bones['mixamorig:RightFoot'].matrix).translation.copy()
print(f"mesh变形: {moved}/3000")
print(f"帧18左手: z={lh18.z:.3f}, 摆臂{(lh18-lh1).length*100:.1f}cm")
print(f"帧18右脚: z={rf18.z:.3f}")
ok = moved > 500 and lh18.z < 1.8 and (lh18-lh1).length > 0.02 and rf18.z < 0.4
print(f"行走验证: {'✓ 通过' if ok else '✗ 失败'}")

step07 = os.path.join(OUT, "07_行走测试_重跑.blend")
bpy.ops.wm.save_mainfile(filepath=step07)
print(f"保存: {step07}")
print("\n========== ARP_RERUN_ALL_DONE ==========")
