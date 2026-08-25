"""
Blender: Mirror vertex positions along an axis while preserving UV layers
and material assignments. The closest Blender equivalent to ZBrush Smart
Resymmetry.

Run from Blender's Text Editor or via:
    blender --python mirror_geometry_keep_uv.py -- --object "MyMesh" --axis X

Requires:
  - Blender 4.0+ (bmesh, mathutils.kdtree)
  - Object must be a mesh in OBJECT mode
  - Mesh must be topologically symmetric (same vert count both sides)

What this does:
  1. Reads vertex coordinates from the positive side of the mirror axis
  2. Matches each to the nearest vertex on the negative side (by the two
     non-mirror axes)
  3. Overwrites the negative-side vertex's coordinates with the mirrored
     positive-side coordinates
  4. Snaps center-axis vertices to exactly 0
  5. Recalculates face normals

What this does NOT touch:
  - UV layers (stored on loops, independent of vert.co)
  - Material slots and face material assignments
  - Vertex colors / attributes
  - Shape keys (handle separately if needed)
"""

import argparse
import sys
import bmesh
import mathutils


def mirror_geometry_keep_uv(obj, axis='X', threshold=0.0001, match_dist=0.001):
    """Mirror vertex positions along axis, preserving UV layers and materials.

    Args:
        obj: Blender object (must be mesh type)
        axis: 'X', 'Y', or 'Z'
        threshold: verts within this distance of axis plane are snapped to 0
        match_dist: max distance on non-mirror axes for left-right vertex pairing

    Returns:
        dict with counts: matched, unmatched_pos, center_snapped
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()

    axis_idx = {'X': 0, 'Y': 1, 'Z': 2}[axis]
    other_axes = [i for i in range(3) if i != axis_idx]

    # 1. Partition verts
    pos_verts = [v for v in bm.verts if v.co[axis_idx] > threshold]
    neg_verts = [v for v in bm.verts if v.co[axis_idx] < -threshold]
    center_verts = [v for v in bm.verts if abs(v.co[axis_idx]) <= threshold]

    if len(pos_verts) != len(neg_verts):
        print(f"WARNING: asymmetric vert counts — pos={len(pos_verts)}, "
              f"neg={len(neg_verts)}. Unmatched verts will not be mirrored.")

    # 2. Build KDTree on negative side (2D: non-mirror axes only)
    kdtree = mathutils.kdtree.KDTree(len(neg_verts))
    for i, v in enumerate(neg_verts):
        co_2d = mathutils.Vector((v.co[other_axes[0]], v.co[other_axes[1]], 0))
        kdtree.insert(co_2d, i)
    kdtree.balance()

    # 3. Match and mirror
    matched = 0
    unmatched = 0
    matched_neg = set()
    for pos_v in pos_verts:
        co_2d = mathutils.Vector(
            (pos_v.co[other_axes[0]], pos_v.co[other_axes[1]], 0))
        co_find, idx, dist = kdtree.find_nearest(co_2d)

        if idx is not None and dist < match_dist and idx not in matched_neg:
            neg_v = neg_verts[idx]
            matched_neg.add(idx)
            neg_v.co[axis_idx] = -pos_v.co[axis_idx]
            neg_v.co[other_axes[0]] = pos_v.co[other_axes[0]]
            neg_v.co[other_axes[1]] = pos_v.co[other_axes[1]]
            matched += 1
        else:
            unmatched += 1

    # 4. Snap center verts to axis plane
    for v in center_verts:
        v.co[axis_idx] = 0.0

    # 5. Recalculate normals
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    return {
        'matched': matched,
        'unmatched_pos': unmatched,
        'center_snapped': len(center_verts),
    }


# ── CLI entry point (for `blender --python` usage) ─────────────────────────

if __name__ == '__main__':
    # When run via `blender --python script.py -- --args`, Blender passes
    # only the args after `--` to sys.argv. Parse those.
    argv = sys.argv
    if '--' in argv:
        argv = argv[argv.index('--') + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(
        description='Mirror mesh geometry while preserving UV layers.')
    parser.add_argument('--object', required=True,
                        help='Name of the mesh object to mirror')
    parser.add_argument('--axis', default='X', choices=['X', 'Y', 'Z'],
                        help='Mirror axis (default: X)')
    parser.add_argument('--threshold', type=float, default=0.0001,
                        help='Snap distance for center-axis verts')
    parser.add_argument('--match-dist', type=float, default=0.001,
                        help='Max distance for left-right vertex matching')
    args = parser.parse_args(argv)

    import bpy
    obj = bpy.data.objects.get(args.object)
    if obj is None:
        print(f"ERROR: object '{args.object}' not found")
        sys.exit(1)

    # Ensure object mode
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    result = mirror_geometry_keep_uv(
        obj, axis=args.axis,
        threshold=args.threshold, match_dist=args.match_dist)

    print(f"Mirror complete: {result}")
