"""
Stage 3: 黏连检测与修复 — BVH-based self-proximity detection + normal push + Laplacian smooth.
Blender 5.1 background script.
"""
import bpy, bmesh, sys, os, json, math, argparse
from mathutils import Vector, kdtree

def get_main_mesh():
    """Get the largest mesh, skipping small objects."""
    # Clean up small objects
    for obj in list(bpy.data.objects):
        if obj.type == 'MESH' and len(obj.data.vertices) < 100:
            bpy.data.objects.remove(obj, do_unlink=True)
    meshes = [(o, len(o.data.vertices)) for o in bpy.data.objects if o.type == 'MESH']
    if not meshes:
        return None
    meshes.sort(key=lambda x: x[1], reverse=True)
    return meshes[0][0]

def detect_adhesion(obj, threshold_mm=5.0):
    """Detect pairs of faces within threshold distance (non-adjacent)."""
    mesh = obj.data
    threshold = threshold_mm / 1000.0

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    face_centers = []
    face_normals = []
    for f in bm.faces:
        c = f.calc_center_median()
        face_centers.append(c)
        face_normals.append(f.normal.normalized())

    kd = kdtree.KDTree(len(face_centers))
    for i, c in enumerate(face_centers):
        kd.insert(c, i)
    kd.balance()

    adhesion_pairs = []
    processed = set()

    for i, c in enumerate(face_centers):
        for (co, j, dist) in kd.find_range(c, 10.0 * threshold):
            if i == j or j <= i:
                continue
            pair_key = (min(i, j), max(i, j))
            if pair_key in processed:
                continue
            fi, fj = bm.faces[i], bm.faces[j]
            shared_verts = set(v.index for v in fi.verts) & set(v.index for v in fj.verts)
            if shared_verts:
                continue
            n_i = face_normals[i]
            n_j = face_normals[j]
            dir_vec = (face_centers[j] - face_centers[i]).normalized()
            if n_i.dot(dir_vec) > 0.3 and n_j.dot(-dir_vec) > 0.3:
                if dist < threshold:
                    adhesion_pairs.append((i, j, dist))
                    processed.add(pair_key)

    bm.free()
    return adhesion_pairs


def fix_adhesion(obj, adhesion_pairs, push_step_mm=0.5, max_iter=20,
                 smooth_iter=10, smooth_factor=0.3):
    """Push vertices apart along normals, then smooth transition region."""
    mesh = obj.data
    push_step = push_step_mm / 1000.0

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    affected_verts = set()
    for (fi, fj, dist) in adhesion_pairs:
        for v in bm.faces[fi].verts:
            affected_verts.add(v.index)
        for v in bm.faces[fj].verts:
            affected_verts.add(v.index)

    for vi in affected_verts:
        v = bm.verts[vi]
        if v.normal.length > 0:
            v.co += v.normal.normalized() * push_step

    bm.to_mesh(mesh)

    # Select affected vertices for smooth
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    for vi in affected_verts:
        if vi < len(mesh.vertices):
            mesh.vertices[vi].select = True

    bpy.ops.object.mode_set(mode='EDIT')
    for i in range(smooth_iter):
        bpy.ops.mesh.vertices_smooth(factor=smooth_factor, repeat=1)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    bm.free()
    return {"affected_vertices": len(affected_verts),
            "adhesion_pairs": len(adhesion_pairs)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--threshold', type=float, default=5.0)
    parser.add_argument('--push_step', type=float, default=0.5)
    parser.add_argument('--max_iter', type=int, default=20)
    parser.add_argument('--smooth_iter', type=int, default=10)
    parser.add_argument('--smooth_factor', type=float, default=0.3)
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args(
        sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    obj = get_main_mesh()
    if not obj:
        print("ERROR: No mesh found")
        sys.exit(1)

    pairs = detect_adhesion(obj, args.threshold)
    print(f"Detected {len(pairs)} adhesion pairs")

    if pairs:
        result = fix_adhesion(obj, pairs, args.push_step, args.max_iter,
                              args.smooth_iter, args.smooth_factor)
        print("Fix Result:", json.dumps(result, indent=2))
    else:
        print("No adhesion detected.")

    if args.output:
        bpy.ops.wm.save_as_mainfile(filepath=args.output)
        print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()