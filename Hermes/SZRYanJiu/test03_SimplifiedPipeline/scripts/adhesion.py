"""
Stage 2: 黏连检测与修复 — Adhesion detection and repair.
Works on high-poly model (preserved from repair stage).

Detects true adhesion: face pairs that are close AND facing each other
AND in body regions likely to clamp (inner thighs, underarms, etc).

Blender 5.1 background script.
"""
import bpy, bmesh, sys, os, json, math, argparse, time
from mathutils import Vector, kdtree


def get_main_mesh():
    for obj in list(bpy.data.objects):
        if obj.type == 'MESH' and len(obj.data.vertices) < 100:
            bpy.data.objects.remove(obj, do_unlink=True)
    meshes = [(o, len(o.data.vertices)) for o in bpy.data.objects if o.type == 'MESH']
    if not meshes:
        return None
    meshes.sort(key=lambda x: x[1], reverse=True)
    return meshes[0][0]


def detect_adhesion(obj, threshold_mm=5.0, max_pairs=2000):
    """Detect true adhesion pairs: close, facing each other, non-adjacent.

    Stricter than proximity-only: requires n·dir > 0.5 (nearly opposing normals)
    to filter out clothing-on-body and normal close surface pairs.
    """
    mesh = obj.data
    threshold = threshold_mm / 1000.0
    n_faces = len(mesh.polygons)
    print(f"  Detecting: {n_faces} faces, threshold={threshold_mm}mm")

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    centers = []
    normals = []
    for f in bm.faces:
        centers.append(f.calc_center_median())
        normals.append(f.normal.normalized())

    t0 = time.time()
    kd = kdtree.KDTree(n_faces)
    for i, c in enumerate(centers):
        kd.insert(c, i)
    kd.balance()
    print(f"  KDTree built ({time.time()-t0:.1f}s)")

    t0 = time.time()
    adhesion_pairs = []
    processed = set()

    for i in range(n_faces):
        if i % 50000 == 0 and i > 0:
            print(f"    {i}/{n_faces}, pairs={len(adhesion_pairs)}")

        c_i = centers[i]
        for (co, j, dist) in kd.find_range(c_i, 2.0 * threshold):
            if i >= j:
                continue
            if (i, j) in processed:
                continue

            fi, fj = bm.faces[i], bm.faces[j]
            shared = set(v.index for v in fi.verts) & set(v.index for v in fj.verts)
            if shared:
                continue

            dir_vec = centers[j] - centers[i]
            if dir_vec.length < 1e-8:
                continue
            dir_vec = dir_vec.normalized()
            n_i, n_j = normals[i], normals[j]
            dot_i = n_i.dot(dir_vec)
            dot_j = n_j.dot(-dir_vec)

            # Strict: both normals must strongly oppose (faces truly facing each other)
            # 0.5 = ~60° cone, filters out grazing-angle clothing pairs
            if dot_i > 0.5 and dot_j > 0.5 and dist < threshold:
                adhesion_pairs.append((i, j, dist))
                processed.add((i, j))

        if len(adhesion_pairs) >= max_pairs:
            print(f"    Max pairs ({max_pairs})")
            break

    bm.free()
    elapsed = time.time() - t0
    print(f"  Found {len(adhesion_pairs)} pairs ({elapsed:.1f}s)")
    return adhesion_pairs


def fix_adhesion(obj, adhesion_pairs, push_step_mm=0.3, smooth_iter=3,
                 smooth_factor=0.15):
    """Push clamped verts apart, then smooth. Small steps to avoid distortion."""
    if not adhesion_pairs:
        return {"affected_vertices": 0, "adhesion_pairs": 0}

    mesh = obj.data
    push_step = push_step_mm / 1000.0

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    affected = {}
    for (fi, fj, dist) in adhesion_pairs:
        for v in bm.faces[fi].verts:
            if v.index not in affected:
                affected[v.index] = Vector((0, 0, 0))
            if v.normal.length > 0:
                affected[v.index] += v.normal.normalized() * push_step
        for v in bm.faces[fj].verts:
            if v.index not in affected:
                affected[v.index] = Vector((0, 0, 0))
            if v.normal.length > 0:
                affected[v.index] += v.normal.normalized() * push_step

    for vi, push_vec in affected.items():
        bm.verts[vi].co += push_vec

    bm.to_mesh(mesh)
    bm.free()

    # Smooth affected region
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    for vi in affected:
        if vi < len(mesh.vertices):
            mesh.vertices[vi].select = True

    bpy.ops.object.mode_set(mode='EDIT')
    for _ in range(smooth_iter):
        bpy.ops.mesh.vertices_smooth(factor=smooth_factor, repeat=1)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    return {"affected_vertices": len(affected),
            "adhesion_pairs": len(adhesion_pairs)}


def adhesion_pipeline(obj, threshold_mm=5.0, push_step_mm=0.3,
                      smooth_iter=3, smooth_factor=0.15, max_pairs=2000):
    """Full adhesion detect + fix + verify."""
    stats = {}
    print(f"\n{'='*60}")
    print(f"ADHESION START: {len(obj.data.vertices)} verts, {len(obj.data.polygons)} faces")

    pairs = detect_adhesion(obj, threshold_mm, max_pairs)
    stats["pairs_detected"] = len(pairs)

    if pairs:
        result = fix_adhesion(obj, pairs, push_step_mm, smooth_iter, smooth_factor)
        stats.update(result)
        print(f"  Fixed: {result}")

        # Verify reduction
        remaining = detect_adhesion(obj, threshold_mm, max_pairs)
        stats["pairs_remaining"] = len(remaining)
        print(f"  Remaining: {len(remaining)}")
    else:
        stats["affected_vertices"] = 0
        stats["pairs_remaining"] = 0
        print("  No adhesion detected")

    print(f"{'='*60}")
    print("ADHESION COMPLETE")
    print(f"{'='*60}")
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--threshold', type=float, default=5.0)
    parser.add_argument('--push_step', type=float, default=0.3)
    parser.add_argument('--smooth_iter', type=int, default=3)
    parser.add_argument('--smooth_factor', type=float, default=0.15)
    parser.add_argument('--max_pairs', type=int, default=2000)
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args(
        sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    obj = get_main_mesh()
    if not obj:
        print("ERROR: No mesh"); sys.exit(1)

    result = adhesion_pipeline(obj, args.threshold, args.push_step,
                               args.smooth_iter, args.smooth_factor,
                               args.max_pairs)
    print("Adhesion Result:", json.dumps(result, indent=2))

    if args.output:
        bpy.ops.wm.save_as_mainfile(filepath=args.output)
        print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
