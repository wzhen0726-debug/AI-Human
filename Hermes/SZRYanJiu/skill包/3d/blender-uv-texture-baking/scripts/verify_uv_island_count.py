"""Headless probe: verify UV island counting is seam-aware.

Run: blender --background --factory-startup --python verify_uv_island_count.py

Builds two synthetic cases:
  A1: 2x1 subdivided plane with UVs split at x=0 (right half offset +1.0)
      -> correct seam-aware count = 2; naive geometric BFS = 1 (the bug).
  A2: default cube + smart_project -> seam-aware count must be > 1.

Validated 2026-08-05 on Blender 5.1 (A1: 2 vs 1, A2: 6 vs 1).
"""
import bpy, bmesh, math

EPS = 1e-6


def count_islands(mesh):
    """Seam-aware: same island only if loop UVs match at BOTH shared-edge endpoints."""
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    bm.faces.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.active
    face_vert_uv = {}
    for f in bm.faces:
        d = {}
        for l in f.loops:
            uvc = l[uv_layer].uv
            d[l.vert.index] = (uvc.x, uvc.y)
        face_vert_uv[f.index] = d
    adj = {f.index: [] for f in bm.faces}
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) != 2:
            continue
        f1, f2 = lf
        v1, v2 = e.verts[0].index, e.verts[1].index
        a1, a2 = face_vert_uv[f1.index].get(v1), face_vert_uv[f1.index].get(v2)
        b1, b2 = face_vert_uv[f2.index].get(v1), face_vert_uv[f2.index].get(v2)
        if a1 and a2 and b1 and b2:
            if (abs(a1[0] - b1[0]) < EPS and abs(a1[1] - b1[1]) < EPS and
                    abs(a2[0] - b2[0]) < EPS and abs(a2[1] - b2[1]) < EPS):
                adj[f1.index].append(f2.index)
                adj[f2.index].append(f1.index)
    island_count = 0
    visited = set()
    for fi in adj:
        if fi in visited:
            continue
        island_count += 1
        stack = [fi]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            stack.extend(adj[cur])
    bm.free()
    return island_count


def count_islands_naive(mesh):
    """Naive geometric BFS (ignores UV seams) — always 1 on connected meshes."""
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    island_count = 0
    visited = set()
    for f in bm.faces:
        if f.index in visited:
            continue
        island_count += 1
        stack = [f]
        while stack:
            face = stack.pop()
            if face.index in visited:
                continue
            visited.add(face.index)
            for edge in face.edges:
                for linked in edge.link_faces:
                    if linked.index not in visited:
                        stack.append(linked)
    bm.free()
    return island_count


# A1: synthetic 2-island mesh
bpy.ops.mesh.primitive_plane_add(size=1)
obj = bpy.context.active_object
obj.scale = (2, 1, 1)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=1)
bpy.ops.object.mode_set(mode='OBJECT')
uv = obj.data.uv_layers.new(name='test_uv')
obj.data.uv_layers.active = uv
for poly in obj.data.polygons:
    cx = sum(obj.data.vertices[vi].co.x for vi in poly.vertices) / len(poly.vertices)
    off = 1.0 if cx > 0.01 else 0.0
    for li in poly.loop_indices:
        vi = obj.data.loops[li].vertex_index
        v = obj.data.vertices[vi]
        uv.data[li].uv = ((v.co.x + 1.0) * 0.25 + off, v.co.y * 0.5)
new_ct = count_islands(obj)
old_ct = count_islands_naive(obj)
print(f"A1 synthetic 2-island mesh: seam-aware={new_ct} (expect 2), naive={old_ct} (expect 1)")
assert new_ct == 2 and old_ct == 1
bpy.data.objects.remove(obj, do_unlink=True)

# A2: cube + smart_project
bpy.ops.mesh.primitive_cube_add()
cube = bpy.context.active_object
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.01)
bpy.ops.object.mode_set(mode='OBJECT')
new_ct2 = count_islands(cube)
old_ct2 = count_islands_naive(cube)
print(f"A2 cube+smart_project: seam-aware={new_ct2} (expect >1), naive={old_ct2}")
assert new_ct2 > 1 and old_ct2 == 1
bpy.data.objects.remove(cube, do_unlink=True)

print("ALL CHECKS PASSED")
