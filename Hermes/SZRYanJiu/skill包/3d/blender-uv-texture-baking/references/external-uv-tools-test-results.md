# External UV Tools — Testing Results (2026-07-21)

## pymeshlab (v0.1.x, installed via pip in Blender Python)

### Available UV filters
- `compute_texcoord_parametrization_least_squares_conformal_maps` (LSCM)
- `compute_texcoord_parametrization_harmonic` (Harmonic)
- `generate_voronoi_atlas_parametrization` (Voronoi chart-based)
- `compute_texcoord_parametrization_triangle_trivial_per_wedge` (Basic)

### Test results on 90K-face QR mesh (180K triangles)
| Method | Result |
|--------|--------|
| LSCM | **Timeout** (>120s, no output) |
| Harmonic | **Timeout** |
| Voronoi atlas | **Timeout** |

All methods timed out on 180K triangles. pymeshlab's UV algorithms are too slow for this mesh size.

### API quirk
pymeshlab exports OBJ without UVs by default. The wedge_tex_coord_matrix() returns UV data after parameterization, but the OBJ export doesn't include it unless explicitly saved with UV data.

## xatlas (v0.0.11, installed in system Python)

### API
```python
atlas = xatlas.Atlas()
atlas.add_mesh(vertices, faces)
atlas.generate(ChartOptions(), PackOptions())
vm, fm, uv = atlas[0]  # vertex_map, face_map, uv_coords
```

### Test results
- ~2000 islands on 90K-face QR mesh
- Vision score 3/10 (arms/legs near-zero UV area)
- texels_per_unit PackOption didn't take effect in Python binding

### Integration issue
xatlas is installed in system Python (Hermes venv), NOT in Blender's bundled Python. Two-step workflow needed:
1. Export OBJ from Blender
2. Run xatlas in system Python via subprocess
3. Import UVs back via .npz file

The subprocess approach from Blender's `--background` mode failed to produce output — the system Python call completes but the JSON output file is never written.

## open3d
Installation failed in Blender's Python: `pip install open3d` returns error. Not viable.

## Conclusion
- **pymeshlab**: Too slow for >100K triangle meshes
- **xatlas**: Quality insufficient (3/10), integration brittle
- **open3d**: Installation fails
- **None of these are viable** for the QR character pipeline