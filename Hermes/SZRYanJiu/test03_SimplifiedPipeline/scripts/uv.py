"""
Stage 5: 自动UV展开 — 角色标准接缝 + Angle Based Unwrap + Pack.
Blender 5.1 background script.

接缝策略（不在脸上分割）：
1. 背中线（X≈0, Y>0 脊柱线）— 从头顶到尾椎
2. 手臂内侧（Y<0 前侧）— 腋窝到手腕
3. 腿内侧（Y<0 前侧）— 腹股沟到脚踝
4. 腰带线 — 腰部环切
5. 脖子环切 — 头与身体分离
6. 手腕/脚踝环切 — 手脚分离

模型朝向（repair阶段已旋转）：X=臂展, Y=体厚, Z=高度, 面朝-Y
"""
import bpy, bmesh, sys, json, math, argparse


def get_retopo_mesh():
    """Find retopo mesh (lower face count than original)."""
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'Retopo' in o.name:
            return o
    meshes = [(o, len(o.data.polygons)) for o in bpy.data.objects if o.type == 'MESH']
    if meshes:
        meshes.sort(key=lambda x: x[1])
        return meshes[0][0]
    return None


def mark_character_seams(mesh):
    """Mark seams following standard character UV conventions.
    
    Model orientation: X=arm span, Y=body depth (front=-Y), Z=height.
    """
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # Get bounding box
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    mid_x = (min_x + max_x) / 2
    mid_y = (min_y + max_y) / 2
    height = max_z - min_z
    
    # Tolerance for "near center" and "near axis"
    x_tol = (max_x - min_x) * 0.02  # 2% of width
    y_tol = (max_y - min_y) * 0.15  # 15% of depth
    z_tol = height * 0.02

    seams_marked = 0
    
    # Z-height bands for body parts
    head_z = min_z + height * 0.87   # head starts at ~87% height
    neck_z = min_z + height * 0.83   # neck band
    shoulder_z = min_z + height * 0.80
    waist_z = min_z + height * 0.55
    hip_z = min_z + height * 0.45
    knee_z = min_z + height * 0.25
    ankle_z = min_z + height * 0.07

    for edge in bm.edges:
        v0, v1 = edge.verts
        mid = (v0.co + v1.co) / 2
        
        # 1. Back center line (X≈0, Y>0 = back side)
        # Spine from neck to hip
        if (abs(v0.co.x - mid_x) < x_tol and abs(v1.co.x - mid_x) < x_tol and
            v0.co.y > mid_y and v1.co.y > mid_y and
            hip_z < mid.z < neck_z):
            edge.seam = True
            seams_marked += 1
            continue
        
        # Back of head (X≈0, Y>0, above neck)
        if (abs(v0.co.x - mid_x) < x_tol and abs(v1.co.x - mid_x) < x_tol and
            v0.co.y > mid_y and v1.co.y > mid_y and
            mid.z > neck_z):
            edge.seam = True
            seams_marked += 1
            continue

        # 2. Neck ring (separate head from body)
        if abs(mid.z - neck_z) < height * 0.02:
            edge.seam = True
            seams_marked += 1
            continue

        # 3. Waist ring
        if abs(mid.z - waist_z) < height * 0.015:
            edge.seam = True
            seams_marked += 1
            continue

        # 4. Arm inside (Y<0 = front side, between shoulder and hand)
        # Arms extend along X, inside is front (Y<0)
        arm_z_min = shoulder_z - height * 0.02
        arm_z_max = shoulder_z + height * 0.05
        if (v0.co.y < mid_y - y_tol * 0.5 and v1.co.y < mid_y - y_tol * 0.5 and
            arm_z_min < mid.z < arm_z_max and
            abs(mid.x) > (max_x - min_x) * 0.15):  # away from body center
            edge.seam = True
            seams_marked += 1
            continue

        # 5. Wrist ring (separate hands)
        hand_z = shoulder_z  # hands are at shoulder height in T-pose
        if abs(mid.z - hand_z) < height * 0.02:
            # Only at X extremes (wrist position)
            if abs(mid.x) > (max_x - min_x) * 0.35:
                edge.seam = True
                seams_marked += 1
                continue

        # 6. Leg inside (Y<0 = front side, between hip and ankle)
        if (v0.co.y < mid_y - y_tol * 0.5 and v1.co.y < mid_y - y_tol * 0.5 and
            ankle_z < mid.z < hip_z and
            abs(mid.x) < (max_x - min_x) * 0.1):  # near body center
            edge.seam = True
            seams_marked += 1
            continue

        # 7. Ankle ring (separate feet)
        if abs(mid.z - ankle_z) < height * 0.02:
            edge.seam = True
            seams_marked += 1
            continue

    bm.to_mesh(mesh)
    bm.free()
    return seams_marked


def auto_uv_pipeline(obj, angle_threshold_deg=55.0, island_margin=0.005):
    """Full auto UV pipeline with character-specific seams."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    bpy.ops.object.mode_set(mode='OBJECT')
    mesh = obj.data
    stats = {"vertices": len(mesh.vertices), "faces": len(mesh.polygons)}

    # Step 1: Clear existing seams
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    # Step 2: Mark character seams
    char_seams = mark_character_seams(mesh)
    stats["character_seams"] = char_seams
    print(f"Marked {char_seams} character seams")

    # Step 3: Also mark sharp edges (>55°) as additional seams
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    angle_threshold = math.radians(angle_threshold_deg)
    angle_seams = 0
    for edge in bm.edges:
        if not edge.seam and not edge.is_boundary and len(edge.link_faces) == 2:
            angle = edge.calc_face_angle()
            if angle is not None and angle >= angle_threshold:
                edge.seam = True
                angle_seams += 1
    bm.to_mesh(mesh)
    bm.free()
    stats["angle_seams"] = angle_seams
    stats["total_seams"] = char_seams + angle_seams
    print(f"Marked {angle_seams} angle seams (total: {char_seams + angle_seams})")

    # Step 4: Unwrap (Angle Based)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True,
                      correct_aspect=True, margin_method='SCALED',
                      margin=island_margin)

    # Step 5: Pack Islands
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, rotate_method='ANY', scale=True,
                            merge_overlap=False, margin_method='SCALED',
                            margin=0.003, shape_method='CONCAVE')

    bpy.ops.object.mode_set(mode='OBJECT')

    # Count UV islands
    uv_layer = mesh.uv_layers.active
    if uv_layer:
        loops = len(mesh.loops)
        flat = [0.0] * loops * 2
        uv_layer.uv.foreach_get('vector', flat)
        us = flat[0::2]
        vs = flat[1::2]
        stats["uv_range"] = f"U[{min(us):.3f},{max(us):.3f}] V[{min(vs):.3f},{max(vs):.3f}]"

    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--angle', type=float, default=55.0)
    parser.add_argument('--margin', type=float, default=0.005)
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args(
        sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    obj = get_retopo_mesh()
    if not obj:
        print("ERROR: No mesh found")
        sys.exit(1)

    result = auto_uv_pipeline(obj, args.angle, args.margin)
    print("Auto UV Result:", json.dumps(result, indent=2))

    if args.output:
        bpy.ops.wm.save_as_mainfile(filepath=args.output)
        print(f"Saved: {args.output}")

if __name__ == "__main__":
    main()
