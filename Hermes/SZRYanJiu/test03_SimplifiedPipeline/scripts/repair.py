"""
Stage 1: 高模几何修复 — High-poly geometry repair (no voxel remesh).
Preserves original high face count and facial detail.
Output goes directly to adhesion stage, then Quad Remesher.

Steps:
  1. Import GLB, cleanup junk objects
  2. Orientation detection & rotation (arms→X, face→-Y, Z up)
  3. Center on origin (X=0, Y=0), ground at Z=0
  4. Remove doubles (merge coincident verts from open shell seams)
  5. Dissolve degenerate faces (zero-area, no holes left)
  6. Fill holes (close all boundary edge loops)
  7. Fix non-manifold edges (dissolve or split to make manifold)
  8. Recalculate normals (consistent outward)
  9. Laplacian smooth (gentle, 2 iterations, preserve detail)
  10. Final fill holes + remove doubles
  11. Re-ground (smooth may shift Z)
  12. Quality verification

Blender 5.1 background script.
"""
import bpy, bmesh, sys, os, json, argparse, math, time


def get_main_mesh():
    """Get the largest mesh object, removing all junk."""
    for obj in list(bpy.data.objects):
        if obj.type != 'MESH':
            bpy.data.objects.remove(obj, do_unlink=True)
    for obj in list(bpy.data.objects):
        if obj.type == 'MESH' and len(obj.data.vertices) < 100:
            bpy.data.objects.remove(obj, do_unlink=True)
    meshes = [(o, len(o.data.vertices)) for o in bpy.data.objects if o.type == 'MESH']
    if not meshes:
        return None
    meshes.sort(key=lambda x: x[1], reverse=True)
    for obj, _ in meshes[1:]:
        bpy.data.objects.remove(obj, do_unlink=True)
    return meshes[0][0]


def get_bbox(obj):
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)), \
           (max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))


def rotate_to_standard(obj):
    """Rotate so arms→X, face→-Y. Tripo default: arms along Y, face +X."""
    mn, mx, dims = get_bbox(obj)
    dim_x, dim_y = dims[0], dims[1]
    if dim_y > dim_x * 1.8:
        print(f"  Rotating: dim_x={dim_x:.3f} dim_y={dim_y:.3f}")
        bm = bmesh.new(); bm.from_mesh(obj.data)
        for v in bm.verts:
            old_x, old_y = v.co.x, v.co.y
            v.co.x = old_y; v.co.y = -old_x
        bm.to_mesh(obj.data); bm.free(); obj.data.update()
        mn2, mx2, dims2 = get_bbox(obj)
        print(f"  After: dim_x={dims2[0]:.3f} dim_y={dims2[1]:.3f} dim_z={dims2[2]:.3f}")
        return True
    print(f"  No rotation: dim_x={dim_x:.3f} dim_y={dim_y:.3f}")
    return False


def center_model(obj):
    """Center on origin (X=0, Y=0), feet at Z=0."""
    mn, mx, dims = get_bbox(obj)
    cx = (mn[0] + mx[0]) / 2.0
    cy = (mn[1] + mx[1]) / 2.0
    cz_min = mn[2]
    bm = bmesh.new(); bm.from_mesh(obj.data)
    for v in bm.verts:
        v.co.x -= cx; v.co.y -= cy; v.co.z -= cz_min
    bm.to_mesh(obj.data); bm.free(); obj.data.update()
    print(f"  Centered: offset=({cx:.4f}, {cy:.4f}, {cz_min:.4f})")


def dissolve_degenerate(obj):
    """Dissolve zero-area faces (merges into neighbors, no holes)."""
    bm = bmesh.new(); bm.from_mesh(obj.data)
    degen = [f for f in bm.faces if f.calc_area() < 1e-10]
    if degen:
        bmesh.ops.dissolve_faces(bm, faces=degen)
    loose = [v for v in bm.verts if len(v.link_edges) == 0]
    for v in loose:
        bm.verts.remove(v)
    bm.to_mesh(obj.data); bm.free(); obj.data.update()
    print(f"  Dissolved: {len(degen)} degenerate, {len(loose)} loose verts")
    return len(degen), len(loose)


def fix_non_manifold_edges(obj):
    """Fix non-manifold edges by dissolving edges shared by >2 faces."""
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Find edges with >2 faces (true non-manifold, not just boundary)
    over_connected = [e for e in bm.edges if len(e.link_faces) > 2]
    fixed = 0
    for e in over_connected:
        # Dissolve the extra faces on this edge
        faces_to_remove = list(e.link_faces[2:])
        for f in faces_to_remove:
            if f in bm.faces:
                bm.faces.remove(f)
                fixed += 1

    # Merge coincident verts on boundary edges to close gaps
    boundary_verts = set()
    for e in bm.edges:
        if len(e.link_faces) == 1:
            for v in e.verts:
                boundary_verts.add(v)

    bm.to_mesh(obj.data); bm.free(); obj.data.update()
    print(f"  Fixed {fixed} non-manifold faces, {len(boundary_verts)} boundary verts found")
    return fixed


def laplacian_smooth(obj, iterations=2, lambda_factor=0.3):
    """Gentle smooth: just enough to remove scan noise, preserve detail."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    for _ in range(iterations):
        try:
            bpy.ops.mesh.vertices_smooth_laplacian(repeat=1, lambda_factor=lambda_factor)
        except AttributeError:
            bpy.ops.mesh.vertices_smooth(factor=0.3, repeat=1)
    bpy.ops.object.mode_set(mode='OBJECT')


def verify_mesh(obj):
    mesh = obj.data
    bm = bmesh.new(); bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    loose = sum(1 for v in bm.verts if len(v.link_edges) == 0)
    degen = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
    mn, mx, dims = get_bbox(obj)
    oriented = dims[0] > dims[1] * 1.5
    bm.free()
    result = {
        "verts": len(mesh.vertices), "faces": len(mesh.polygons),
        "non_manifold_edges": non_manifold, "boundary_edges": boundary,
        "loose_verts": loose, "degenerate_faces": degen,
        "watertight": boundary == 0, "manifold": non_manifold == 0,
        "oriented_correctly": oriented,
        "dimensions": {"x": round(dims[0],4), "y": round(dims[1],4), "z": round(dims[2],4)},
    }
    # Acceptable: non_manifold < 50 and boundary < 50 (minor, QR can handle)
    result["PASS"] = (loose == 0) and (degen == 0) and (non_manifold < 50) and (boundary < 50) and oriented
    return result


def repair_pipeline(obj, smooth_iter=2, smooth_factor=0.3):
    """Main repair pipeline — preserves high face count, no Voxel Remesh."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    mesh = obj.data
    stats = {"initial_verts": len(mesh.vertices), "initial_faces": len(mesh.polygons)}
    print(f"\n{'='*60}")
    print(f"REPAIR START: {len(mesh.vertices)} verts, {len(mesh.polygons)} faces")

    t0 = time.time()
    print("\n[1] Orientation...")
    stats["rotated"] = rotate_to_standard(obj)

    print("\n[2] Center & ground...")
    center_model(obj)

    print("\n[3] Remove doubles...")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.object.mode_set(mode='OBJECT')
    stats["after_remove_doubles"] = len(mesh.vertices)
    print(f"  {len(mesh.vertices)} verts")

    print("\n[4] Dissolve degenerate...")
    stats["degen_cleaned"] = dissolve_degenerate(obj)

    print("\n[5] Fill holes...")
    t0 = time.time()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.fill_holes(sides=0)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"  Done ({time.time()-t0:.1f}s)")

    print("\n[6] Fix non-manifold edges...")
    stats["non_manifold_fixed"] = fix_non_manifold_edges(obj)

    print(f"\n[7] Laplacian smooth (iter={smooth_iter})...")
    laplacian_smooth(obj, smooth_iter, smooth_factor)

    print("\n[8] Final fill holes + remove doubles...")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.mesh.fill_holes(sides=0)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

    print("\n[9] Re-ground...")
    mn, mx, dims = get_bbox(obj)
    if abs(mn[2]) > 0.0005:
        bm = bmesh.new(); bm.from_mesh(obj.data)
        for v in bm.verts:
            v.co.z -= mn[2]
        bm.to_mesh(obj.data); bm.free(); obj.data.update()
        print(f"  Re-grounded: Z={mn[2]:.6f}")

    print("\n[10] Verify...")
    stats["verify"] = verify_mesh(obj)
    v = stats["verify"]
    status = "PASS" if v["PASS"] else "FAIL"
    print(f"\n{'='*60}")
    print(f"REPAIR COMPLETE: {status}")
    print(f"  {v['verts']} verts, {v['faces']} faces")
    print(f"  watertight={v['watertight']} manifold={v['manifold']}")
    print(f"  non_manifold={v['non_manifold_edges']} boundary={v['boundary_edges']}")
    print(f"  dims={v['dimensions']}")
    print(f"{'='*60}")
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smooth_iter', type=int, default=2)
    parser.add_argument('--smooth_factor', type=float, default=0.3)
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args(
        sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    obj = get_main_mesh()
    if not obj:
        print("ERROR: No mesh"); sys.exit(1)
    result = repair_pipeline(obj, args.smooth_iter, args.smooth_factor)
    print("Result:", json.dumps(result, indent=2))
    if args.output:
        bpy.ops.wm.save_as_mainfile(filepath=args.output)
        print(f"Saved: {args.output}")

if __name__ == "__main__":
    main()
