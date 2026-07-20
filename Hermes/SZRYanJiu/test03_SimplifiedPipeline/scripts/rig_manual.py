"""
Stage 7: 绑定 — 手动创建骨骼 + 自动权重.
Blender 5.1 background script.

不再使用ARP Smart（模板比例不匹配），改为：
1. 从mesh几何计算关节位置
2. 手动创建骨骼层级
3. Blender自动权重绑定
"""
import bpy, bmesh, sys, json, argparse, os, math
from mathutils import Vector


def get_retopo_mesh():
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'Retopo' in o.name:
            return o
    meshes = [(o, len(o.data.polygons)) for o in bpy.data.objects if o.type == 'MESH']
    if meshes:
        meshes.sort(key=lambda x: x[1])
        return meshes[0][0]
    return None


def compute_joint_positions(mesh):
    """从网格顶点计算各关节的3D位置。
    
    模型朝向：X=臂展, Y=体厚(前=-Y), Z=高度
    """
    verts = mesh.data.vertices
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    mid_x = (min_x + max_x) / 2
    mid_y = (min_y + max_y) / 2
    H = max_z - min_z
    W = max_x - min_x  # arm span
    
    def band_center(z_lo, z_hi, x_filter=None):
        band = [v for v in verts if z_lo <= v.co.z <= z_hi]
        if x_filter:
            band = [v for v in band if x_filter(v.co.x)]
        if not band:
            return mid_x, mid_y, (z_lo + z_hi) / 2
        bx = sum(v.co.x for v in band) / len(band)
        by = sum(v.co.y for v in band) / len(band)
        bz = sum(v.co.z for v in band) / len(band)
        return bx, by, bz

    def band_extreme_x(z_lo, z_hi, want_max):
        band = [v for v in verts if z_lo <= v.co.z <= z_hi]
        if not band:
            return max_x if want_max else min_x, mid_y
        if want_max:
            v = max(band, key=lambda v: v.co.x)
        else:
            v = min(band, key=lambda v: v.co.x)
        return v.co.x, v.co.y

    joints = {}
    
    # Root (pelvis center) — 胯部分叉点在~45%高度
    z = min_z + H * 0.45
    joints['root'] = band_center(z - H*0.02, z + H*0.02)
    
    # Spine
    z = min_z + H * 0.55
    joints['spine_01'] = band_center(z - H*0.02, z + H*0.02)
    
    z = min_z + H * 0.68
    joints['spine_02'] = band_center(z - H*0.02, z + H*0.02)
    
    z = min_z + H * 0.75
    joints['chest'] = band_center(z - H*0.02, z + H*0.02)
    
    # Neck
    z = min_z + H * 0.83
    joints['neck'] = band_center(z - H*0.01, z + H*0.01)
    
    # Head
    z = min_z + H * 0.90
    joints['head'] = band_center(z - H*0.02, z + H*0.02)
    
    # Head top
    z = min_z + H * 0.97
    joints['head_top'] = band_center(z - H*0.01, z + H*0.01)
    
    # Shoulders — 肩关节在躯干与手臂连接处
    # 用X方向密度分析找连接点（密度最高的位置）
    z = min_z + H * 0.78
    band = [v for v in verts if abs(v.co.z - z) < H*0.015]
    # 在右侧0.05~0.15范围内找密度最高的X
    if band:
        best_x = 0.08; best_count = 0
        for test_x in range(50, 160, 5):
            tx = test_x / 1000.0
            count = sum(1 for v in band if abs(v.co.x - tx) < 0.01)
            if count > best_count:
                best_count = count; best_x = tx
        right_shoulder_x = best_x
        left_shoulder_x = -best_x
    else:
        right_shoulder_x = 0.09; left_shoulder_x = -0.09
    # 用该位置附近的平均Y
    r_near = [v for v in band if abs(v.co.x - right_shoulder_x) < 0.02] if band else []
    l_near = [v for v in band if abs(v.co.x - left_shoulder_x) < 0.02] if band else []
    ry = sum(v.co.y for v in r_near) / len(r_near) if r_near else mid_y
    ly = sum(v.co.y for v in l_near) / len(l_near) if l_near else mid_y
    joints['shoulder_r'] = (right_shoulder_x, ry, z)
    joints['shoulder_l'] = (left_shoulder_x, ly, z)
    
    # Elbows — 手臂中段
    z = min_z + H * 0.78
    rx = (right_shoulder_x + max_x * 0.85) / 2
    lx = (left_shoulder_x + min_x * 0.85) / 2
    joints['elbow_r'] = (rx, ry, z)
    joints['elbow_l'] = (lx, ly, z)
    
    # Hands (wrist) — 手腕位置：手臂变细处
    # 在肩高度band中，找右手侧X密度突然下降的点
    z = min_z + H * 0.78
    right_band = sorted([v.co.x for v in band if v.co.x > right_shoulder_x]) if band else []
    # 手腕 = 密度从高变低的转折点（手臂→手掌变细）
    wrist_r = max_x * 0.88  # 默认值
    wrist_l = min_x * 0.88
    if right_band:
        # 在0.35~0.48范围内找密度最低的X（手腕处）
        best_low_x = 0.40; best_low_count = 999
        for test_x in range(350, 480, 5):
            tx = test_x / 1000.0
            count = sum(1 for v in band if abs(v.co.x - tx) < 0.008)
            if count < best_low_count and count > 50:
                best_low_count = count; best_low_x = tx
        wrist_r = best_low_x
        wrist_l = -best_low_x
    joints['hand_r'] = (wrist_r, ry, z)
    joints['hand_l'] = (wrist_l, ly, z)
    
    # Hips (left/right) — 与root同高
    z = min_z + H * 0.45
    joints['hip_r'] = band_center(z - H*0.02, z + H*0.02, lambda x: x > mid_x + W*0.03)
    joints['hip_l'] = band_center(z - H*0.02, z + H*0.02, lambda x: x < mid_x - W*0.03)
    
    # Knees
    z = min_z + H * 0.22
    joints['knee_r'] = band_center(z - H*0.02, z + H*0.02, lambda x: x > mid_x + 0.005)
    joints['knee_l'] = band_center(z - H*0.02, z + H*0.02, lambda x: x < mid_x - 0.005)
    
    # Ankles
    z = min_z + H * 0.05
    joints['ankle_r'] = band_center(z - H*0.02, z + H*0.02, lambda x: x > mid_x)
    joints['ankle_l'] = band_center(z - H*0.02, z + H*0.02, lambda x: x < mid_x)
    
    # Feet
    z = min_z + H * 0.01
    joints['foot_r'] = band_center(z - H*0.005, z + H*0.01, lambda x: x > mid_x)
    joints['foot_l'] = band_center(z - H*0.005, z + H*0.01, lambda x: x < mid_x)
    
    return joints


def create_armature(joints, mesh):
    """从关节位置创建骨骼层级。"""
    verts = mesh.data.vertices
    xs = [v.co.x for v in verts]
    min_x, max_x = min(xs), max(xs)
    
    arm_data = bpy.data.armatures.new('rig')
    arm_obj = bpy.data.objects.new('rig', arm_data)
    bpy.context.collection.objects.link(arm_obj)
    
    bpy.context.view_layer.objects.active = arm_obj
    arm_obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    
    eb = arm_data.edit_bones
    
    # Spine chain
    b_root = eb.new('root')
    b_root.head = Vector(joints['root'])
    b_root.tail = Vector(joints['spine_01'])
    
    b_spine1 = eb.new('spine_01')
    b_spine1.head = Vector(joints['spine_01'])
    b_spine1.tail = Vector(joints['spine_02'])
    b_spine1.parent = b_root
    
    b_spine2 = eb.new('spine_02')
    b_spine2.head = Vector(joints['spine_02'])
    b_spine2.tail = Vector(joints['chest'])
    b_spine2.parent = b_spine1
    
    b_chest = eb.new('chest')
    b_chest.head = Vector(joints['chest'])
    b_chest.tail = Vector(joints['neck'])
    b_chest.parent = b_spine2
    
    b_neck = eb.new('neck')
    b_neck.head = Vector(joints['neck'])
    b_neck.tail = Vector(joints['head'])
    b_neck.parent = b_chest
    
    b_head = eb.new('head')
    b_head.head = Vector(joints['head'])
    b_head.tail = Vector(joints['head_top'])
    b_head.parent = b_neck
    
    # Right arm (positive X)
    b_sh_r = eb.new('shoulder_r')
    b_sh_r.head = Vector(joints['shoulder_r'])
    b_sh_r.tail = Vector(joints['elbow_r'])
    b_sh_r.parent = b_chest
    
    b_arm_r = eb.new('forearm_r')
    b_arm_r.head = Vector(joints['elbow_r'])
    b_arm_r.tail = Vector(joints['hand_r'])
    b_arm_r.parent = b_sh_r
    
    b_hand_r = eb.new('hand_r')
    b_hand_r.head = Vector(joints['hand_r'])
    hr = joints['hand_r']
    # hand骨骼延伸到指尖（max_x方向）
    b_hand_r.tail = Vector((max_x, hr[1], hr[2]))
    b_hand_r.parent = b_arm_r
    
    # Left arm (negative X)
    b_sh_l = eb.new('shoulder_l')
    b_sh_l.head = Vector(joints['shoulder_l'])
    b_sh_l.tail = Vector(joints['elbow_l'])
    b_sh_l.parent = b_chest
    
    b_arm_l = eb.new('forearm_l')
    b_arm_l.head = Vector(joints['elbow_l'])
    b_arm_l.tail = Vector(joints['hand_l'])
    b_arm_l.parent = b_sh_l
    
    b_hand_l = eb.new('hand_l')
    b_hand_l.head = Vector(joints['hand_l'])
    hl = joints['hand_l']
    b_hand_l.tail = Vector((min_x, hl[1], hl[2]))
    b_hand_l.parent = b_arm_l
    
    # Right leg
    b_hip_r = eb.new('thigh_r')
    b_hip_r.head = Vector(joints['hip_r'])
    b_hip_r.tail = Vector(joints['knee_r'])
    b_hip_r.parent = b_root
    
    b_knee_r = eb.new('knee_r')
    b_knee_r.head = Vector(joints['knee_r'])
    b_knee_r.tail = Vector(joints['ankle_r'])
    b_knee_r.parent = b_hip_r
    
    b_ankle_r = eb.new('foot_r')
    b_ankle_r.head = Vector(joints['ankle_r'])
    b_ankle_r.tail = Vector(joints['foot_r'])
    b_ankle_r.parent = b_knee_r
    
    # Left leg
    b_hip_l = eb.new('thigh_l')
    b_hip_l.head = Vector(joints['hip_l'])
    b_hip_l.tail = Vector(joints['knee_l'])
    b_hip_l.parent = b_root
    
    b_knee_l = eb.new('knee_l')
    b_knee_l.head = Vector(joints['knee_l'])
    b_knee_l.tail = Vector(joints['ankle_l'])
    b_knee_l.parent = b_hip_l
    
    b_ankle_l = eb.new('foot_l')
    b_ankle_l.head = Vector(joints['ankle_l'])
    b_ankle_l.tail = Vector(joints['foot_l'])
    b_ankle_l.parent = b_knee_l
    
    bpy.ops.object.mode_set(mode='OBJECT')
    return arm_obj


def bind_weights(arm, mesh):
    """绑定自动权重。"""
    bpy.context.window.screen = bpy.data.screens['Layout']
    area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    
    mesh.parent = arm
    mod = mesh.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm
    
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    arm.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm
    
    with bpy.context.temp_override(area=area, region=region,
                                    active_object=arm,
                                    selected_objects=[arm, mesh]):
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    
    weighted = sum(1 for vg in mesh.vertex_groups
                   if sum(1 for v in mesh.data.vertices
                          if any(g.group == vg.index and g.weight > 0
                                 for g in v.groups)) > 0)
    return len(mesh.vertex_groups), weighted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args(
        sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    mesh = get_retopo_mesh()
    if not mesh:
        print("ERROR: No mesh found")
        sys.exit(1)

    print(f"Rigging: {mesh.name} ({len(mesh.data.vertices)} verts)")
    
    # Clean up old armatures
    for o in list(bpy.data.objects):
        if o.type == 'ARMATURE':
            bpy.data.objects.remove(o, do_unlink=True)
    
    # Compute joint positions
    joints = compute_joint_positions(mesh)
    for name, pos in joints.items():
        print(f"  {name}: ({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f})")
    
    # Create armature
    arm = create_armature(joints, mesh)
    print(f"Armature: {arm.name} bones={len(arm.data.bones)}")
    
    # Bind weights
    total_vg, weighted_vg = bind_weights(arm, mesh)
    print(f"Weights: vg={total_vg} weighted={weighted_vg}")
    
    # Set REST position
    arm.data.pose_position = 'REST'
    
    if args.output:
        bpy.ops.wm.save_as_mainfile(filepath=args.output)
        print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
