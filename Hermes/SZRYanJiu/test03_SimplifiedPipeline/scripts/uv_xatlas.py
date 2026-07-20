"""UV unwrap v6: xatlas (external unwrapper).
Exports mesh → xatlas unwrap → import UVs back.
Creates clean, non-overlapping UVs with consistent texel density.
"""
import bpy, bmesh, random, math, os, tempfile, json
import numpy as np

def run():
    mesh = [o for o in bpy.data.objects if o.type == 'MESH' and 'Retopo' in o.name][0]
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)

    if not mesh.data.uv_layers:
        mesh.data.uv_layers.new(name='UVMap')

    # Export mesh to numpy arrays for xatlas
    verts = mesh.data.vertices
    faces = mesh.data.polygons
    n_verts = len(verts)
    n_faces = len(faces)

    # Position array
    positions = np.zeros((n_verts, 3), dtype=np.float32)
    verts.foreach_get('co', positions.reshape(-1))

    # Face index array
    face_indices = []
    for f in faces:
        face_indices.append(list(f.vertices))
    face_indices = np.array(face_indices, dtype=np.int32)

    print(f"Mesh: {n_verts} verts, {n_faces} faces")

    # Run xatlas
    import xatlas
    atlas = xatlas.Atlas()

    # Add mesh
    atlas.add_mesh(positions, face_indices)

    # Parameters for character UV
    atlas.chart_options.max_cost = 2.0  # Better chart quality
    atlas.pack_options.max_iterations = 4
    atlas.pack_options.texel_density = 512.0  # Consistent density

    print("Running xatlas...")
    atlas.generate()
    print("xatlas done")

    # Get results
    result = atlas[0]
    new_verts = result.vertex_array
    new_uvs = result.uv_array
    new_faces = result.face_array

    print(f"xatlas result: {len(new_uvs)} UVs, {len(new_faces)} faces")

    # Build new mesh data
    # xatlas may create new vertices (splitting), need to rebuild mesh
    bm = bmesh.new()
    bm.from_mesh(mesh.data)

    # Create new vertex UV map
    uv_layer = mesh.data.uv_layers.active
    if not uv_layer:
        uv_layer = mesh.data.uv_layers.new(name='UVMap')

    # xatlas returns new face indices into new vertex array
    # We need to map new faces back to original mesh loops
    # 
    # Strategy: xatlas output has same number of faces as input
    # Each face in xatlas output references new vertex indices
    # We need to update UV for each loop based on xatlas UVs

    # For each face, set UVs for its loops
    uv_data = [0.0] * len(mesh.data.loops) * 2

    for fi, poly in enumerate(mesh.data.polygons):
        if fi >= len(new_faces):
            break
        xatlas_face = new_faces[fi]
        loops = list(poly.loop_indices)

        for li_idx, loop_idx in enumerate(loops):
            if li_idx < len(xatlas_face):
                vi = xatlas_face[li_idx]
                if vi < len(new_uvs):
                    uv_data[loop_idx * 2] = new_uvs[vi][0]
                    uv_data[loop_idx * 2 + 1] = new_uvs[vi][1]

    uv_layer.uv.foreach_set('vector', uv_data)

    # Normalize to [0,1]
    us = uv_data[0::2]
    vs = uv_data[1::2]
    min_u, max_u = min(us), max(us)
    min_v, max_v = min(vs), max(vs)
    ru = max(max_u - min_u, 1e-6)
    rv = max(max_v - min_v, 1e-6)
    for i in range(len(us)):
        uv_data[i*2] = (us[i] - min_u) / ru
        uv_data[i*2+1] = (vs[i] - min_v) / rv
    uv_layer.uv.foreach_set('vector', uv_data)

    # Stats
    s = random.sample(list(zip(uv_data[0::2], uv_data[1::2])), min(2000, len(uv_data)//2))
    islands = len(set((round(u, 3), round(v, 3)) for u, v in s))
    print(f'UV: islands~{islands} U[{min(uv_data[0::2]):.3f},{max(uv_data[0::2]):.3f}] V[{min(uv_data[1::2]):.3f},{max(uv_data[1::2]):.3f}]')

    bm.free()
    return {'islands': islands}


if __name__ == '__main__':
    run()
