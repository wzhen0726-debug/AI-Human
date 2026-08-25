# xatlas Two-Step UV Workflow (2026-07-20)

## Overview

xatlas is a free, open-source UV unwrapper that runs as a Python library.
It CANNOT be installed into Blender's bundled Python (pip fails), so a
two-step workflow is required: export mesh from Blender → run xatlas in
system Python → import UVs back.

## Installation

```bash
# In system Python (NOT Blender's Python)
pip install xatlas trimesh numpy
```

Blender's `--background` Python cannot install xatlas — `ensurepip.bootstrap()`
installs to the wrong site-packages, and `import xatlas` fails even after
`pip install` reports success.

## Step 1: Export mesh from Blender

```python
# Blender --background script
import bpy
mesh = [o for o in bpy.data.objects if o.type == 'MESH' and 'Retopo' in o.name][0]
bpy.context.view_layer.objects.active = mesh
mesh.select_set(True)
# Blender 5.1 uses wm.obj_export (NOT export_scene.obj which doesn't exist)
bpy.ops.wm.obj_export(filepath='temp_mesh.obj',
    export_selected_objects=True, export_materials=False,
    export_normals=False, export_uv=False)
```

**API quirk**: Blender 5.1's OBJ exporter is `bpy.ops.wm.obj_export`, NOT
`bpy.ops.export_scene.obj` (which raises "could not be found"). The file
extension can be .ply but the content is OBJ format.

## Step 2: Run xatlas in system Python

```python
import xatlas, trimesh, numpy as np

mesh = trimesh.load('temp_mesh.obj')
atlas = xatlas.Atlas()
atlas.add_mesh(mesh.vertices, mesh.faces)
# ChartOptions and PackOptions are CLASSES, not attributes
co = xatlas.ChartOptions()
po = xatlas.PackOptions()
atlas.generate(co, po)

# API returns 3-tuple, NOT the documented vertex_array/uv_array
vm, fm, uv = atlas[0]
# vm: (N,) vertex_map — original→new vertex mapping
# fm: (F, 3) face_map — xatlas vertex indices per face
# uv: (N, 2) UV coordinates per new vertex

np.savez('xatlas_result.npz', vertex_map=vm, face_map=fm, uvs=uv)
```

## Step 3: Import UVs back to Blender

**CRITICAL**: Use `fm` (face_map) for UV assignment, NOT `vm` (vertex_map).
`vm[orig_vi]` gives ONE uv per original vertex, but xatlas splits vertices
to create proper UVs. Using `vm` collapses distinct UVs and produces
near-zero UV area for arms/legs.

Correct mapping:
```python
for fi, poly in enumerate(mesh.data.polygons):
    xatlas_face = fm[fi]  # (xvi0, xvi1, xvi2)
    for li_idx, li in enumerate(poly.loop_indices):
        if li_idx < len(xatlas_face):
            xvi = xatlas_face[li_idx]
            uv_data[li*2] = uvs[xvi][0]
            uv_data[li*2+1] = uvs[xvi][1]
```

## Results (2026-07-20)

- Input: 90333 verts, 180662 faces
- Output: 98514 new vertices (split), 180662 faces
- Islands: ~2000
- Vision score: 3/10 (slightly better than Blender's 2/10)
- Arms/legs still near-zero UV area
- `texels_per_unit` PackOption did not take effect (v0.0.11)

## Conclusion

xatlas is marginally better than Blender's built-in unwrappers for QR meshes,
but still produces unusable UVs for character models. The fundamental issue
is the QR mesh topology, not the unwrapping algorithm.

## API Version Notes

- xatlas v0.0.11 (Python binding)
- `atlas.chart_options` / `atlas.pack_options` → AttributeError (NOT attributes)
- `xatlas.ChartOptions()` / `xatlas.PackOptions()` → correct (classes)
- `atlas[0]` returns tuple of 3 ndarrays, NOT an object with `.vertex_array`
- `po.texels_per_unit` exists as attribute but did not affect output
