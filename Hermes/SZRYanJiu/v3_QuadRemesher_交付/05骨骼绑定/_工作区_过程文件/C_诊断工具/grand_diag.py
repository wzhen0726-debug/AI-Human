"""综合诊断: 手写版眼珠/手骨/行走姿态/Mixamo骨骼朝向对照. 结果写文件."""
import bpy, glob, os
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
RIG_BLEND = os.path.join(BASE, "B_骨骼绑定", "06_rig_final.blend")
WALK_BLEND = os.path.join(BASE, "B_骨骼绑定", "walk_test_手写版.blend")
MIXAMO_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件"
OUT = os.path.join(BASE, "logs", "grand_diag.txt")

out = []
def sec(t): out.append(""); out.append(f"===== {t} =====")

def find_rig():
    for o in bpy.data.objects:
        if o.type == 'ARMATURE':
            return o
    return None

def dump_armature_bones(rig, names, label):
    sec(label)
    if rig is None:
        out.append("无骨架"); return
    for bn in names:
        b = rig.data.bones.get(bn)
        if b is None:
            out.append(f"{bn}: 不存在"); continue
        M = rig.matrix_world @ b.matrix_local
        ydir = (M.to_3x3() @ Vector((0,1,0))).normalized()
        zdir = (M.to_3x3() @ Vector((0,0,1))).normalized()
        out.append(f"{bn}: head=({b.head_local.x:.3f},{b.head_local.y:.3f},{b.head_local.z:.3f}) "
                   f"tail=({b.tail_local.x:.3f},{b.tail_local.y:.3f},{b.tail_local.z:.3f})")
        out.append(f"    世界Y向={tuple(round(c,2) for c in ydir)} 世界Z向={tuple(round(c,2) for c in zdir)}")

# ============ A. 手写版绑定文件: 眼珠 + 手骨 ============
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG_BLEND)
rig = find_rig()
body = bpy.data.objects.get("tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR")

sec("A1 眼珠朝向")
for o in bpy.data.objects:
    if o.type == 'MESH' and 'Eye' in o.name:
        iris_world = (o.matrix_world.to_3x3() @ Vector((0,-1,0))).normalized()
        out.append(f"{o.name}: 父={o.parent.name if o.parent else None}/{o.parent_type}"
                   f"/骨={getattr(o,'parent_bone','')}")
        out.append(f"    虹膜方向(世界)={tuple(round(c,2) for c in iris_world)} (应为0,0附近x,z≈0... 正确=朝前(0,-1,0))")
        out.append(f"    位置={tuple(round(c,3) for c in o.matrix_world.translation)}")

sec("A2 右手: 骨骼 vs 网格")
hand_bones = [b.name for b in rig.data.bones if 'Hand' in b.name and ('R' in b.name.split(':')[-1][-2:] or 'Right' in b.name)]
hand_bones = [b.name for b in rig.data.bones if any(k in b.name for k in ('Thumb','Index','Middle','Ring','Pinky')) and b.name in rig.data.bones.keys()]
# 右手骨骼(名字含R或Right)
rh = [b.name for b in rig.data.bones if any(k in b.name for k in ('Thumb','Index','Middle','Ring','Pinky','Hand')) 
      and ('Right' in b.name or b.name.endswith('_R') or '_R.' in b.name)]
for bn in sorted(rh)[:20]:
    b = rig.data.bones[bn]
    out.append(f"{bn}: head=({b.head_local.x:.3f},{b.head_local.y:.3f},{b.head_local.z:.3f}) tail=({b.tail_local.x:.3f},{b.tail_local.y:.3f},{b.tail_local.z:.3f})")

# 右手网格几何: x>0.72 的顶点(指尖区域)
if body:
    xs=[v.co.x for v in body.data.vertices]; 
    vmax=max(xs)
    tips=[v.co for v in body.data.vertices if v.co.x > vmax-0.05]
    ys=[v.y for v in tips]; zs=[v.z for v in tips]
    out.append(f"网格指尖区(x>{vmax-0.05:.2f}): {len(tips)}顶点 y范围{min(ys):.3f}~{max(ys):.3f} z范围{min(zs):.3f}~{max(zs):.3f}")
    # 腕部厚度
    wrist=[v.co for v in body.data.vertices if abs(v.co.x-0.70)<0.03]
    if wrist:
        ys2=[v.y for v in wrist]; zs2=[v.z for v in wrist]
        out.append(f"网格腕部(x≈0.70): {len(wrist)}顶点 y范围{min(ys2):.3f}~{max(ys2):.3f} z范围{min(zs2):.3f}~{max(zs2):.3f}")

# ============ B. Mixamo 参考骨骼朝向 ============
sec("B Mixamo参考骨骼(FBX导入)")
fbxs = glob.glob(os.path.join(MIXAMO_DIR, "*.fbx"))
out.append(f"FBX文件: {[os.path.basename(f) for f in fbxs]}")
if fbxs:
    walk_fbx = next((f for f in fbxs if 'alk' in os.path.basename(f)), fbxs[0])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=walk_fbx)
    mrig = find_rig()
    mnames = ['mixamorig:Hips','mixamorig:Spine','mixamorig:Neck','mixamorig:Head',
              'mixamorig:LeftArm','mixamorig:LeftForeArm','mixamorig:LeftHand',
              'mixamorig:LeftHandThumb1','mixamorig:LeftHandIndex1',
              'mixamorig:RightArm','mixamorig:RightUpLeg','mixamorig:RightLeg','mixamorig:RightFoot','mixamorig:RightToeBase']
    dump_armature_bones(mrig, mnames, "B1 Mixamo骨架关键骨骼")

# ============ C. 手写版同批骨骼对照 ============
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG_BLEND)
rig = find_rig()  # 重开后重新获取
th_name = 'mixamorig:LeftHandThumb1' if rig.data.bones.get('mixamorig:LeftHandThumb1') else sorted([b.name for b in rig.data.bones if 'Thumb' in b.name])[0]
toe_name = 'mixamorig:RightToeBase' if rig.data.bones.get('mixamorig:RightToeBase') else sorted([b.name for b in rig.data.bones if 'Toe' in b.name])[-1]
dump_armature_bones(rig, ['mixamorig:Hips','mixamorig:Spine','mixamorig:Neck','mixamorig:Head',
    'mixamorig:LeftArm','mixamorig:LeftForeArm','mixamorig:LeftHand', th_name,
    'mixamorig:RightArm','mixamorig:RightUpLeg','mixamorig:RightLeg','mixamorig:RightFoot', toe_name],
    "C 手写版同批骨骼(与B对比朝向)")

# ============ D. 行走测试姿态量化 ============
sec("D 行走测试姿态(帧1 vs 帧18)")
bpy.ops.wm.open_mainfile(filepath=WALK_BLEND)
rig2 = bpy.data.objects.get("MixamoSkeleton") or find_rig()
scn = bpy.context.scene
for fr in (1, 18):
    scn.frame_set(fr)
    bpy.context.view_layer.update()
    out.append(f"--- 帧{fr} ---")
    for bn in ['mixamorig:Hips','mixamorig:LeftArm','mixamorig:LeftHand','mixamorig:RightHand',
               'mixamorig:LeftForeArm','mixamorig:LeftUpLeg','mixamorig:LeftLeg','mixamorig:LeftFoot','mixamorig:LeftToeBase']:
        pb = rig2.pose.bones.get(bn)
        if pb:
            w = (rig2.matrix_world @ pb.matrix).translation
            out.append(f"{bn}: 世界=({w.x:.3f},{w.y:.3f},{w.z:.3f})")

out.append(""); out.append("GRAND_DIAG_DONE")
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("WROTE", OUT)