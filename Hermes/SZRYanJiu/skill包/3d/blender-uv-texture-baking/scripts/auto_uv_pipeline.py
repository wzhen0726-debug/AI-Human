"""
Auto UV Unwrap Pipeline for Digital Human (200-250K poly)
Blender 5.1 Python Script — fully automated, no manual intervention.

Pipeline:
  1. Detect sharp edges by dihedral angle → mark as seams
  2. Mark symmetry-axis (X=0) edges as seams (critical for left/right UV symmetry)
  3. Standard Angle-Based Unwrap
  4. Pack islands with rotation + scaling
  5. Average island scale for balanced texel density

Usage:
  blender --background model.blend --python auto_uv_pipeline.py
"""

import bpy
import bmesh
import math


def auto_uv_pipeline(
    angle_threshold_deg=55.0,
    island_margin=0.005,
    symmetry_axis='X',
    symmetry_threshold=0.001,
):
    """
    Full auto UV pipeline. Returns dict with stats.

    Parameters:
        angle_threshold_deg: Dihedral angle threshold for seam marking (default 55°)
        island_margin: UV island margin (default 0.005)
        symmetry_axis: Axis for symmetry seam ('X', 'Y', or 'Z')
        symmetry_threshold: Distance threshold for "on axis" check
    """
    obj = bpy.context.active_object
    if not obj or obj.type != 'MESH':
        for o in bpy.data.objects:
            if o.type == 'MESH':
                obj = o
                bpy.context.view_layer.objects.active = obj
                break
    if not obj:
        return {"error": "No mesh object found"}

    bpy.ops.object.mode_set(mode='OBJECT')
    obj.select_set(True)

    # ---- Step 1: Clear existing seams ----
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()

    angle_threshold = math.radians(angle_threshold_deg)

    # ---- Step 2: Mark seams by dihedral angle ----
    seams_marked = 0
    for edge in bm.edges:
        if not edge.is_boundary and len(edge.link_faces) == 2:
            angle = edge.calc_face_angle()
            if angle is not None and angle >= angle_threshold:
                edge.seam = True
                seams_marked += 1

    # ---- Step 3: Mark symmetry-axis seams ----
    axis_idx = {'X': 0, 'Y': 1, 'Z': 2}[symmetry_axis]
    sym_seams = 0
    for edge in bm.edges:
        if edge.seam:
            continue
        v0_on_axis = abs(edge.verts[0].co[axis_idx]) < symmetry_threshold
        v1_on_axis = abs(edge.verts[1].co[axis_idx]) < symmetry_threshold
        if v0_on_axis and v1_on_axis:
            edge.seam = True
            sym_seams += 1

    bm.to_mesh(mesh)
    bm.free()

    # ---- Step 4: Unwrap (Angle Based) ----
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(
        method='ANGLE_BASED',
        fill_holes=True,
        correct_aspect=True,
        margin_method='SCALED',
        margin=island_margin,
    )

    # ---- Step 5: Pack Islands ----
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(
        rotate=True,
        rotate_method='ANY',
        scale=True,
        merge_overlap=False,
        margin_method='SCALED',
        margin=island_margin,
        shape_method='CONCAVE',
    )

    bpy.ops.object.mode_set(mode='OBJECT')

    return {
        "angle_seams": seams_marked,
        "symmetry_seams": sym_seams,
        "total_seams": seams_marked + sym_seams,
        "vertices": len(mesh.vertices),
        "faces": len(mesh.polygons),
        "angle_threshold_deg": angle_threshold_deg,
        "island_margin": island_margin,
    }


if __name__ == "__main__":
    result = auto_uv_pipeline(
        angle_threshold_deg=55.0,
        island_margin=0.005,
        symmetry_axis='X',
    )
    print("Auto UV Pipeline Result:")
    for k, v in result.items():
        print(f"  {k}: {v}")