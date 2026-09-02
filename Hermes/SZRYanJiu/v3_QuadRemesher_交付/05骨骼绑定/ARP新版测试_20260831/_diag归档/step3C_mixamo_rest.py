"""ARP全新测试 — 方案C: 骨架位置完全用Mixamo参考骨架rest(缩放适配), 标记点仅校验
输入: 02_go_detect骨架.blend (拿body mesh) + mixamo_rest_spec.json
输出: 03_骨骼绑定.blend, 04_行走测试.blend + 标记点校验报告"""
import bpy, os, json
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
OUT = os.path.join(BASE, "ARP新版测试_20260831")
IN = os.path.join(OUT, "02_go_detect骨架.blend")
WALK_FBX = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx"
SPEC = os.path.join(BASE, "_工作区_过程文件", "logs", "mixamo_rest_spec.json")

spec = json.load(open(SPEC, encoding="utf-8"))["bones"]

bpy.ops.wm.open_mainfile(filepath=IN)
rig = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
body = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices))
print(f"body={body.name}({len(body.data.vertices)}顶点)")

# 读用户标记点(仅校验) — location即世界坐标(顶层对象)
MK = {}
with bpy.data.libraries.load(os.path.join(OUT, "01_AI打点.blend")) as (src, dst):
    dst.objects = [n for n in src.objects if n.endswith('_loc') or n.endswith('_loc_sym')]
for o in dst.objects:
    MK[o.name] = o.location.copy()
    bpy.data.objects.remove(o, do_unlink=True)
assert any(v.length > 0.1 for v in MK.values())
print(f"标记点 {len(MK)}个(仅校验)")

# 比例: 我们模型 Hips z=0.876 / Mixamo参考 Hips z=0.9979
SCALE = 0.876 / spec['mixamorig:Hips']['head'][2]
print(f"比例系数: {SCALE:.4f} (Mixamo参考身高约{1.94:.2f}m -> 我们1.70m)")

# 55骨清单(Mixamo名, 不带前缀)
BONES = ["Hips","Spine","Spine1","Spine2","Neck","Head","HeadTop_End"]
for pre in ["Left","Right"]:
    BONES += [f"{pre}Shoulder",f"{pre}Arm",f"{pre}ForeArm",f"{pre}Hand",
              f"{pre}UpLeg",f"{pre}Leg",f"{pre}Foot",f"{pre}ToeBase",f"{pre}Toe_End"]
    for f in ["Thumb","Index","Middle","Ring","Pinky"]:
        BONES += [f"{pre}Hand{f}1",f"{pre}Hand{f}2",f"{pre}Hand{f}3"]
assert len(BONES) == 55

# ============ 步骤3C: 按Mixamo spec建骨 ============
print("\n########## 步骤3C: Mixamo参考骨架(缩放)建55骨 ##########")
body.modifiers.clear()
body.vertex_groups.clear()

arm_data = bpy.data.armatures.new("MixamoSkeleton")
arm = bpy.data.objects.new("MixamoSkeleton", arm_data)
bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm_data.edit_bones

created = {}
for name in BONES:
    sb = spec['mixamorig:' + name]
    head = Vector(sb['head']) * SCALE
    # tail: 沿spec的y轴(骨骼主轴)方向, 长度*SCALE
    ydir = Vector(sb['y']).normalized()
    tail = head + ydir * sb['length'] * SCALE
    b = eb.new(name)
    b.head = head; b.tail = tail
    created[name] = b
for name in BONES:
    p = spec['mixamorig:' + name].get('parent')
    if p and p.replace('mixamorig:','') in created:
        created[name].parent = created[p.replace('mixamorig:','')]
print(f"新骨架: {len(created)}骨 (全部Mixamo rest缩放)")

# 标记点校验: 关键关节 spec位置 vs 用户标记点 距离
print("\n标记点校验(距离, cm):")
CHK = [('LeftArm','shoulder_loc'), ('LeftForeArm','elbow_loc'), ('LeftHand','hand_loc'),
       ('LeftUpLeg','thigh_loc'), ('LeftLeg','knee_loc'), ('LeftFoot','foot_loc'),
       ('Hips','root_loc'), ('Neck','neck_loc')]
for bone, mk in CHK:
    sb = spec['mixamorig:' + bone]
    sp = Vector(sb['head']) * SCALE
    mp = MK.get(mk)
    if mp:
        # 右侧_sym的x取反比较? 统一取绝对值比大小没意义, 直接报两边
        d = (sp - mp).length * 100
        print(f"  {bone}: spec=({sp.x:.3f},{sp.y:.3f},{sp.z:.3f}) vs 标记=({mp.x:.3f},{mp.y:.3f},{mp.z:.3f}) 差{d:.1f}cm")

# ============ 步骤4: roll已随spec的y轴天然对齐(骨主轴=y), 无需align_roll ============
# 但Blender建骨默认roll=0(Z轴参考), spec还给了z轴——用align_roll对齐z轴确保动画轴一致
print("\n########## 步骤4: align_roll(对齐spec的z轴) ##########")
aligned = 0
for name in BONES:
    b = created[name]
    sb = spec['mixamorig:' + name]
    z = Vector(sb['z'])
    if z.length > 0.01:
        b.align_roll(Vector(z))  # 只转roll不动head/tail
        aligned += 1
print(f"roll对齐: {aligned}骨")

# ============ 步骤5: use_connect ============
n_conn = 0
for b in eb:
    if b.parent and (b.head - b.parent.tail).length < 0.002:
        b.use_connect = True; n_conn += 1
print(f"use_connect: {n_conn}根")
bpy.ops.object.mode_set(mode='OBJECT')

bpy.data.objects.remove(rig, do_unlink=True)

# ============ 步骤6: 自动权重 ============
print("\n########## 步骤6: 自动权重 ##########")
for o in bpy.data.objects: o.select_set(False)
body.select_set(True); arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
print(f"权重顶点组: {len(body.vertex_groups)}")

step06 = os.path.join(OUT, "03_骨骼绑定.blend")
bpy.ops.wm.save_mainfile(filepath=step06)
print(f"保存: {step06}")

# ============ 步骤7: 行走动画验证 ============
print("\n########## 步骤7: 行走动画验证 ##########")
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
                        bag.fcurves.remove(fc); removed += 1
                break
assert data_slot
print(f"数据slot: {data_slot.identifier}, 删Hips位移{removed}条")

if arm.animation_data is None:
    arm.animation_data_create()
arm.animation_data.action = rig_action
arm.animation_data.action_slot = data_slot

del_names = [o.name for o in bpy.data.objects if o.name != 'MixamoSkeleton' and o.name != body.name and 'Eye' not in o.name]
for nm in del_names:
    o = bpy.data.objects.get(nm)
    if o and o.type in ('ARMATURE', 'MESH'):
        bpy.data.objects.remove(o, do_unlink=True)

scn = bpy.context.scene
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
print(f"行走验证: {'PASS 通过' if ok else 'FAIL 失败'}")

step07 = os.path.join(OUT, "04_行走测试.blend")
bpy.ops.wm.save_mainfile(filepath=step07)
print(f"保存: {step07}")
print("\n========== PLAN_C_DONE ==========")
