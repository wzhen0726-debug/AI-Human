"""
Stage 1-2: 几何修复 — Fill holes, dissolve degenerate, Voxel Remesh, Laplacian Smooth.
ALSO: rotate model to standard orientation (arms along X, face toward -Y, Z up).
This rotation happens ONCE here, all subsequent stages inherit it.

Blender 5.1 background script.
"""
import bpy, bmesh, sys, os, json, argparse, math


def get_main_mesh():
    """Get the largest mesh object, skipping default cube."""
    meshes = [(o, len(o.data.vertices)) for o in bpy.data.objects if o.type == 'MESH']
    if not meshes:
        return None
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and len(obj.data.vertices) < 100:
            bpy.data.objects.remove(obj, do_unlink=True)
    meshes = [(o, len(o.data.vertices)) for o in bpy.data.objects if o.type == 'MESH']
    if not meshes:
        return None
    meshes.sort(key=lambda x: x[1], reverse=True)
    return meshes[0][0]


def rotate_to_standard(obj):
    """Rotate model so arms extend along X, face toward -Y, Z stays up.
    
    Input model: arms along Y, face toward +X (Tripo default).
    Rotation 90° CW around Z: new_x = old_y, new_y = -old_x
    → arms: Y → X (correct)
    → face: +X → -Y (correct for ARP/standard)
    """
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    dim_x = max(xs) - min(xs)
    dim_y = max(ys) - min(ys)
    
    if dim_y > dim_x * 2:
        # Arms along Y — need rotation
        print(f"Rotating: dim_x={dim_x:.3f} dim_y={dim_y:.3f} → arms along Y")
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        for v in bm.verts:
            old_x, old_y = v.co.x, v.co.y
            v.co.x = old_y      # new X = old Y (arm span)
            v.co.y = -old_x     # new Y = -old X (body depth)
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        # Verify
        xs2 = [v.co.x for v in obj.data.vertices]
        ys2 = [v.co.y for v in obj.data.vertices]
        print(f"After rotation: dim_x={max(xs2)-min(xs2):.3f} dim_y={max(ys2)-min(ys2):.3f}")
        return True
    print(f"No rotation needed: dim_x={dim_x:.3f} dim_y={dim_y:.3f}")
    return False


def repair_pipeline(obj, voxel_size=0.005, smooth_iter=5, smooth_factor=0.5):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    mesh = obj.data
    stats = {"initial_verts": len(mesh.vertices), "initial_faces": len(mesh.polygons)}

    # Step 0: Rotate to standard orientation (ONCE, here)
    stats["rotated"] = rotate_to_standard(obj)

    # Step 1: Remove doubles
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.object.mode_set(mode='OBJECT')
    stats["after_remove_doubles_verts"] = len(mesh.vertices)

    # Step 2: Dissolve degenerate
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    degenerate_removed = 0
    for face in list(bm.faces):
        if face.calc_area() < 1e-8:
            bm.faces.remove(face)
            degenerate_removed += 1
    bm.to_mesh(mesh)
    bm.free()
    stats["degenerate_faces_removed"] = degenerate_removed

    # Step 3: Fill holes
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.fill_holes(sides=100)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Step 4: Voxel Remesh
    mod = obj.modifiers.new(name="VoxelRemesh", type='REMESH')
    mod.mode = 'VOXEL'
    mod.voxel_size = voxel_size
    mod.use_remove_disconnected = False
    bpy.ops.object.modifier_apply(modifier="VoxelRemesh")
    stats["after_voxel_verts"] = len(mesh.vertices)
    stats["after_voxel_faces"] = len(mesh.polygons)

    # Step 5: Recalculate normals
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)

    # Step 6: Laplacian Smooth
    for i in range(smooth_iter):
        bpy.ops.mesh.vertices_smooth(factor=smooth_factor, repeat=1)
    bpy.ops.object.mode_set(mode='OBJECT')
    stats["after_smooth_verts"] = len(mesh.vertices)

    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--voxel_size', type=float, default=0.005)
    parser.add_argument('--smooth_iter', type=int, default=5)
    parser.add_argument('--smooth_factor', type=float, default=0.5)
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args(
        sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    obj = get_main_mesh()
    if not obj:
        print("ERROR: No mesh found")
        sys.exit(1)

    result = repair_pipeline(obj, args.voxel_size, args.smooth_iter, args.smooth_factor)
    print("Repair Pipeline Result:", json.dumps(result, indent=2))

    if args.output:
        bpy.ops.wm.save_as_mainfile(filepath=args.output)
        print(f"Saved: {args.output}")

if __name__ == "__main__":
    main()
