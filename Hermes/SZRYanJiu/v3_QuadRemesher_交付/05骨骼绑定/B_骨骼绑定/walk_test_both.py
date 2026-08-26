"""两版行走动画测试: 对比手写版 vs ARP版在行走动画下的表现."""
import bpy, os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
WALK_FBX = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\Standard Walk.fbx"

def test_walk(rig_path, label):
    print(f"\n{'='*50}")
    print(f"测试: {label}")
    print(f"{'='*50}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=rig_path)

    # 找骨架
    rig_arm = None
    for o in bpy.data.objects:
        if o.type == 'ARMATURE':
            rig_arm = o; break
    if not rig_arm:
        print("  未找到骨架"); return False

    # 导入行走动画
    bpy.ops.import_scene.fbx(filepath=WALK_FBX)
    walk_arm = None
    for o in bpy.data.objects:
        if o.type == 'ARMATURE' and o != rig_arm:
            walk_arm = o; break
    if not walk_arm:
        print("  未找到行走骨架"); return False

    action = walk_arm.animation_data.action if walk_arm.animation_data else None
    if not action:
        print("  行走动画无action"); return False

    # 复制action, 去Hips位移
    new_action = action.copy()
    new_action.name = "Walk_noroot"

    # 找到Hips的location曲线并删除
    for layer in new_action.layers:
        for strip in layer.strips:
            for cbag in strip.channelbags:
                fcurves = [fc for fc in cbag.fcurves if 'Hips' in fc.data_path and fc.data_path.endswith('location')]
                for fc in fcurves:
                    cbag.fcurves.remove(fc)
                print(f"  删除Hips位移曲线: {len(fcurves)}条")

    # 绑定到rig
    if not rig_arm.animation_data:
        rig_arm.animation_data_create()
    rig_arm.animation_data.action = new_action
    # 为新action创建slot (不能复用原始action的slot, 那是别的对象)
    new_slot = new_action.slots.new(id_type='OBJECT', name='walk_rig_slot')
    rig_arm.animation_data.action_slot = new_slot

    # 验证骨骼名匹配
    walk_bones = set(b.name.replace('mixamorig:', '') for b in walk_arm.data.bones)
    rig_bones = set(b.name.replace('mixamorig:', '') for b in rig_arm.data.bones)
    matched = walk_bones & rig_bones
    missing = walk_bones - rig_bones
    print(f"  骨骼匹配: {len(matched)}/{len(walk_bones)}")
    if missing:
        print(f"  缺失: {sorted(missing)[:10]}")

    # 验证变形
    body = None
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'eye' not in o.name.lower():
            if body is None or len(o.data.vertices) > len(body.data.vertices):
                body = o

    # 强制求值(5.1新动画系统需要)
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    import numpy as np
    v1 = np.array([body.matrix_world @ v.co for v in body.data.vertices])

    bpy.context.scene.frame_set(20)
    bpy.context.view_layer.update()
    v2 = np.array([body.matrix_world @ v.co for v in body.data.vertices])

    diff = np.linalg.norm(v2 - v1, axis=1)
    moved = (diff > 0.01).sum()
    max_d = diff.max()

    print(f"  网格变形: {moved}/{len(body.data.vertices)}顶点, 最大{max_d*100:.1f}cm")
    
    # 如果变形为0, 尝试用bpy.ops.object.mode_set强制刷新
    if moved == 0:
        print(f"  变形为0, 尝试强制刷新...")
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.view_layer.update()
        v1 = np.array([body.matrix_world @ v.co for v in body.data.vertices])
        bpy.context.scene.frame_set(20)
        bpy.context.view_layer.update()
        v2 = np.array([body.matrix_world @ v.co for v in body.data.vertices])
        diff = np.linalg.norm(v2 - v1, axis=1)
        moved = (diff > 0.01).sum()
        max_d = diff.max()
        print(f"  刷新后变形: {moved}/{len(body.data.vertices)}顶点, 最大{max_d*100:.1f}cm")

    # 保存测试文件
    out = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", f"walk_test_{label}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print(f"  保存: {out}")
    return True

# 测试两版
test_walk(os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_final.blend"), "手写版")
test_walk(os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.blend"), "ARP版")

print("\nWALK_TEST_BOTH_DONE")
