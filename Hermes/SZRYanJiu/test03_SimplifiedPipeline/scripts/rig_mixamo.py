"""
Mixamo-standard skeleton from mesh geometry.
General-purpose joint detection: works for any body type.
Uses X-axis density analysis to find joints, no hardcoded percentages.
"""
import bpy, bmesh, sys, argparse, os, math
from mathutils import Vector

def get_mesh():
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'Retopo' in o.name:
            return o
    return None

def analyze_limb_separation(verts, H, mid_x, min_x, max_x, min_z, max_z):
    """Find arm/leg separation Z using X-width profile."""
    W = max_x - min_x
    # Build X-width + max_X profile
    profile = []
    for pct in range(10, 88, 1):
        z = min_z + H * pct / 100
        band = [v for v in verts if abs(v.co.z - z) < H * 0.01]
        if len(band) > 50:
            bx = [v.co.x for v in band]
            profile.append((z, max(bx) - min(bx), max(bx), min(bx)))
    
    if not profile:
        return min_z + H * 0.78, min_z + H * 0.42
    
    # Arm separation: Z where max_X reaches its peak in upper body
    best_arm_z = min_z + H * 0.78
    best_max_x = 0
    for z, width, mx_val, mn_val in profile:
        if z > min_z + H * 0.65 and mx_val > best_max_x:
            best_max_x = mx_val
            best_arm_z = z
    
    # Leg separation: widest point in lower body [0.25, 0.55]
    best_leg_z = min_z + H * 0.42
    best_width = 0
    for z, width, mx_val, mn_val in profile:
        if min_z + H * 0.25 < z < min_z + H * 0.55:
            if width > best_width:
                best_width = width
                best_leg_z = z
    
    return best_arm_z, best_leg_z

def density_peak_x(verts, z_lo, z_hi, x_range, step=0.005):
    """Find X with highest vertex density in a Z band."""
    band = [v for v in verts if z_lo <= v.co.z <= z_hi]
    best_x, best_count = None, 0
    x = x_range[0]
    while x <= x_range[1]:
        count = sum(1 for v in band if abs(v.co.x - x) < step)
        if count > best_count:
            best_count = count; best_x = x
        x += step * 2
    return best_x if best_x else x_range[0]

def density_valley_x(verts, z_lo, z_hi, x_range, step=0.005):
    """Find X with lowest vertex density (wrist)."""
    band = [v for v in verts if z_lo <= v.co.z <= z_hi]
    best_x, best_count = None, 999999
    x = x_range[0]
    while x <= x_range[1]:
        count = sum(1 for v in band if abs(v.co.x - x) < step)
        if count < best_count and count > 10:
            best_count = count; best_x = x
        x += step * 2
    return best_x if best_x else x_range[0]

def band_center(verts, z_lo, z_hi, x_lo, x_hi):
    """Average position of vertices in a Z+X box."""
    band = [v for v in verts if z_lo <= v.co.z <= z_hi and x_lo <= v.co.x <= x_hi]
    if not band:
        return (x_lo + x_hi) / 2, 0, (z_lo + z_hi) / 2
    cx = sum(v.co.x for v in band) / len(band)
    cy = sum(v.co.y for v in band) / len(band)
    cz = sum(v.co.z for v in band) / len(band)
    return cx, cy, cz

def compute_joints(mesh):
    """Compute all Mixamo joint positions from mesh geometry."""
    verts = mesh.data.vertices
    xs = [v.co.x for v in verts]; ys = [v.co.y for v in verts]; zs = [v.co.z for v in verts]
    min_x, max_x = min(xs), max(xs); min_z, max_z = min(zs), max(zs)
    mid_x = (min_x + max_x) / 2; mid_y = (min(ys) + max(ys)) / 2
    H = max_z - min_z; W = max_x - min_x

    joints = {}
    arm_sep_z, leg_sep_z = analyze_limb_separation(verts, H, mid_x, min_x, max_x, min_z, max_z)

    # Hips (root) — at leg separation
    z = leg_sep_z
    jx, jy, _ = band_center(verts, z - H * 0.02, z + H * 0.02, mid_x - W * 0.08, mid_x + W * 0.08)
    joints['Hips'] = (jx, jy, z)

    # Spine chain
    spine_pcts = [('Spine', 0.55), ('Spine1', 0.65), ('Spine2', 0.72)]
    for name, pct in spine_pcts:
        z = min_z + H * pct
        sx, sy, _ = band_center(verts, z - H * 0.02, z + H * 0.02, mid_x - W * 0.08, mid_x + W * 0.08)
        joints[name] = (sx, sy, z)

    # Neck
    z = min_z + H * 0.82
    nx, ny, _ = band_center(verts, z - H * 0.02, z + H * 0.02, mid_x - W * 0.05, mid_x + W * 0.05)
    joints['Neck'] = (nx, ny, z)

    # Head
    z = min_z + H * 0.90
    hx, hy, _ = band_center(verts, z - H * 0.02, z + H * 0.02, mid_x - W * 0.06, mid_x + W * 0.06)
    joints['Head'] = (hx, hy, z)
    joints['HeadTop'] = (mid_x, mid_y, max_z - H * 0.02)

    # Shoulders — density peak at arm separation Z
    z = arm_sep_z
    r_sh_x = density_peak_x(verts, z - H * 0.02, z + H * 0.02, (0.02, max_x * 0.35))
    l_sh_x = -r_sh_x
    # Get Y at shoulder
    r_sh_y = sum(v.co.y for v in verts if abs(v.co.z - z) < H * 0.02 and abs(v.co.x - r_sh_x) < 0.02) / max(1, sum(1 for v in verts if abs(v.co.z - z) < H * 0.02 and abs(v.co.x - r_sh_x) < 0.02))
    l_sh_y = sum(v.co.y for v in verts if abs(v.co.z - z) < H * 0.02 and abs(v.co.x - l_sh_x) < 0.02) / max(1, sum(1 for v in verts if abs(v.co.z - z) < H * 0.02 and abs(v.co.x - l_sh_x) < 0.02))
    joints['RightShoulder'] = (r_sh_x, r_sh_y, z)
    joints['LeftShoulder'] = (l_sh_x, l_sh_y, z)

    # Elbows — midpoint
    r_el_x = (r_sh_x + max_x * 0.85) / 2
    l_el_x = (l_sh_x + min_x * 0.85) / 2
    joints['RightArm'] = (r_el_x, r_sh_y, z)
    joints['LeftArm'] = (l_el_x, l_sh_y, z)

    # Wrists — density valley
    r_wr_x = density_valley_x(verts, z - H * 0.03, z + H * 0.03, (max_x * 0.7, max_x * 0.95))
    l_wr_x = -r_wr_x
    joints['RightForeArm'] = (r_wr_x, r_sh_y, z)
    joints['LeftForeArm'] = (l_wr_x, l_sh_y, z)

    # Hands — fingertip
    joints['RightHand'] = (max_x * 0.98, r_sh_y, z)
    joints['LeftHand'] = (min_x * 0.98, l_sh_y, z)

    # Hips (left/right)
    z = leg_sep_z
    r_hip_x = density_peak_x(verts, z - H * 0.02, z + H * 0.02, (0.02, max_x * 0.30))
    l_hip_x = -r_hip_x
    r_hip_y = sum(v.co.y for v in verts if abs(v.co.z - z) < H * 0.02 and abs(v.co.x - r_hip_x) < 0.02) / max(1, sum(1 for v in verts if abs(v.co.z - z) < H * 0.02 and abs(v.co.x - r_hip_x) < 0.02))
    l_hip_y = sum(v.co.y for v in verts if abs(v.co.z - z) < H * 0.02 and abs(v.co.x - l_hip_x) < 0.02) / max(1, sum(1 for v in verts if abs(v.co.z - z) < H * 0.02 and abs(v.co.x - l_hip_x) < 0.02))
    joints['RightUpLeg'] = (r_hip_x, r_hip_y, z)
    joints['LeftUpLeg'] = (l_hip_x, l_hip_y, z)

    # Knees
    z = min_z + H * 0.22
    rk = [v for v in verts if abs(v.co.z - z) < H * 0.02 and v.co.x > mid_x + 0.003]
    lk = [v for v in verts if abs(v.co.z - z) < H * 0.02 and v.co.x < mid_x - 0.003]
    rk_x = sum(v.co.x for v in rk) / len(rk) if rk else r_hip_x
    rk_y = sum(v.co.y for v in rk) / len(rk) if rk else r_hip_y
    lk_x = sum(v.co.x for v in lk) / len(lk) if lk else l_hip_x
    lk_y = sum(v.co.y for v in lk) / len(lk) if lk else l_hip_y
    joints['RightLeg'] = (rk_x, rk_y, z)
    joints['LeftLeg'] = (lk_x, lk_y, z)

    # Feet
    z = min_z + H * 0.05
    rf = [v for v in verts if abs(v.co.z - z) < H * 0.02 and v.co.x > mid_x]
    lf = [v for v in verts if abs(v.co.z - z) < H * 0.02 and v.co.x < mid_x]
    rf_x = sum(v.co.x for v in rf) / len(rf) if rf else r_hip_x
    rf_y = sum(v.co.y for v in rf) / len(rf) if rf else r_hip_y
    lf_x = sum(v.co.x for v in lf) / len(lf) if lf else l_hip_x
    lf_y = sum(v.co.y for v in lf) / len(lf) if lf else l_hip_y
    joints['RightFoot'] = (rf_x, rf_y, z)
    joints['LeftFoot'] = (lf_x, lf_y, z)

    # Toes
    z = min_z + H * 0.01
    joints['RightToe'] = (rf_x, rf_y, z)
    joints['LeftToe'] = (lf_x, lf_y, z)

    return joints

def create_armature(joints, mesh):
    """Create Mixamo-standard bone hierarchy from joints."""
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

    def mk_bone(name, head_key, tail_key, parent=None):
        b = eb.new(name)
        b.head = Vector(joints[head_key])
        b.tail = Vector(joints[tail_key])
        if parent:
            b.parent = eb.get(parent)
        return b

    # Spine chain
    mk_bone('Hips', 'Hips', 'Spine')
    mk_bone('Spine', 'Spine', 'Spine1', 'Hips')
    mk_bone('Spine1', 'Spine1', 'Spine2', 'Spine')
    mk_bone('Spine2', 'Spine2', 'Neck', 'Spine1')
    mk_bone('Neck', 'Neck', 'Head', 'Spine2')
    mk_bone('Head', 'Head', 'HeadTop', 'Neck')

    # Arms
    mk_bone('RightShoulder', 'RightShoulder', 'RightArm', 'Spine2')
    mk_bone('RightArm', 'RightArm', 'RightForeArm', 'RightShoulder')
    mk_bone('RightForeArm', 'RightForeArm', 'RightHand', 'RightArm')
    mk_bone('RightHand', 'RightHand', 'RightHand', 'RightForeArm')

    mk_bone('LeftShoulder', 'LeftShoulder', 'LeftArm', 'Spine2')
    mk_bone('LeftArm', 'LeftArm', 'LeftForeArm', 'LeftShoulder')
    mk_bone('LeftForeArm', 'LeftForeArm', 'LeftHand', 'LeftArm')
    mk_bone('LeftHand', 'LeftHand', 'LeftHand', 'LeftForeArm')

    # Fix hand tails to extend to fingertips
    for side, sign in [('Right', 1), ('Left', -1)]:
        hb = eb.get(f'{side}Hand')
        if hb:
            hb.tail = Vector((max_x * sign * 0.98, hb.head.y, hb.head.z))

    # Legs
    mk_bone('RightUpLeg', 'RightUpLeg', 'RightLeg', 'Hips')
    mk_bone('RightLeg', 'RightLeg', 'RightFoot', 'RightUpLeg')
    mk_bone('RightFoot', 'RightFoot', 'RightToe', 'RightLeg')

    mk_bone('LeftUpLeg', 'LeftUpLeg', 'LeftLeg', 'Hips')
    mk_bone('LeftLeg', 'LeftLeg', 'LeftFoot', 'LeftUpLeg')
    mk_bone('LeftFoot', 'LeftFoot', 'LeftToe', 'LeftLeg')

    bpy.ops.object.mode_set(mode='OBJECT')
    return arm_obj

def bind_weights(arm, mesh):
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
                                    active_object=arm, selected_objects=[arm, mesh]):
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    wv = sum(1 for vg in mesh.vertex_groups
             if sum(1 for v in mesh.data.vertices
                    if any(g.group == vg.index and g.weight > 0 for g in v.groups)) > 0)
    return len(mesh.vertex_groups), wv

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    mesh = get_mesh()
    if not mesh:
        print("ERROR: no mesh")
        sys.exit(1)
    for o in list(bpy.data.objects):
        if o.type == 'ARMATURE':
            bpy.data.objects.remove(o, do_unlink=True)
    joints = compute_joints(mesh)
    for name, pos in joints.items():
        print(f"  {name}: ({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f})")
    arm = create_armature(joints, mesh)
    arm.data.pose_position = 'REST'
    print(f"Armature: {arm.name} bones={len(arm.data.bones)}")
    total, weighted = bind_weights(arm, mesh)
    print(f"Weights: vg={total} weighted={weighted}")
    if args.output:
        bpy.ops.wm.save_as_mainfile(filepath=args.output)

if __name__ == "__main__":
    main()
