# Blender 5.1 API Migration Notes

Cross-cutting API changes discovered during pipeline testing (2026-07-15, Blender 5.1.0).

## Texture Baking: `cycles.bake` → `scene.render.bake`

In Blender 5.1, bake settings moved from `bpy.context.scene.cycles.bake` to `bpy.context.scene.render.bake`:

```python
# Blender <5.1 (REMOVED):
cycles = bpy.context.scene.cycles
cycles.bake.use_cage = True
cycles.bake.cage_extrusion = 0.01
cycles.bake.max_ray_distance = 0.02

# Blender 5.1 (CURRENT):
bake = bpy.context.scene.render.bake
bake.use_selected_to_active = True
bake.use_cage = True
bake.cage_extrusion = 0.01
bake.max_ray_distance = 0.02
bake.margin = 16
```

## Normal Bake: `pass_filter` Parameter

For `bpy.ops.object.bake(type='NORMAL')`, do NOT pass `pass_filter`:
```python
# CORRECT:
bpy.ops.object.bake(type='NORMAL', use_clear=True)

# WRONG (TypeError in 5.1):
bpy.ops.object.bake(type='NORMAL', pass_filter={}, use_clear=True)

# ALSO WRONG (TypeError — 'NORMAL' not in valid values):
bpy.ops.object.bake(type='NORMAL', pass_filter={'NORMAL'}, use_clear=True)
```

Valid `pass_filter` values in Blender 5.1: 'NONE', 'EMIT', 'DIRECT', 'INDIRECT', 'COLOR', 'DIFFUSE', 'GLOSSY', 'TRANSMISSION'. Note 'NORMAL' is NOT a valid pass_filter even though the bake type is 'NORMAL'.

For DIFFUSE bake, `pass_filter={'COLOR'}` still works.

**⚠️ Blender 5.1: `colorspace_settings.name` clears baked pixel data**: Setting `tex_node.image.colorspace_settings.name = 'Non-Color'` on a Normal map image that ALREADY has baked pixel data DESTROYS all pixel data — the image becomes 100% black (all zeros). This is a Blender 5.1-specific regression. **Fix**: set colorspace BEFORE the bake call, and do NOT re-set it in any post-bake function (like `connect_textures()`). The bake itself works correctly; only the post-bake colorspace assignment triggers the clear. Debugging this took ~2 hours of bisecting — the data is intact after bake, after `nodes.clear()`, and after adding new nodes; it only goes to zero when `colorspace_settings.name` is set on the already-baked image.

**⚠️ Adaptive bake distance**: A fixed small `max_ray_distance` (e.g., 0.05m for a 1m model) causes black patches where rays don't reach the high-poly surface. Compute adaptively: `max(0.1, max(bbox_x_range, bbox_y_range, bbox_z_range) * 0.15)`. Minimum 0.1m, typical 0.15× model size.

**⚠️ UV pack margin**: `pack_islands(margin=0.005)` uses 5% of UV space for inter-island gaps, leaving ~54% of texture area unused. Reduce to `margin=0.002` for better space utilization. The `scale=True` parameter already handles island sizing.

## glTF Export: Removed Parameters

The following parameters are removed from `bpy.ops.export_scene.gltf()` in Blender 5.1:
- `export_colors` — removed (causes `TypeError: keyword unrecognized`)

Working parameters:
```python
bpy.ops.export_scene.gltf(
    filepath=output_path,
    export_format='GLB',
    export_apply=True,
    export_animations=False,
    export_image_format='JPEG',
    export_texcoords=True,
    export_normals=True,
    export_materials='EXPORT',
    use_selection=True,
    export_yup=True,
)
```

## bmesh: `ensure_lookup_table()` After Triangulation

After `bmesh.ops.triangulate()`, the face lookup table is invalidated. Must re-ensure:
```python
bm.faces.ensure_lookup_table()
bm.verts.ensure_lookup_table()
bmesh.ops.triangulate(bm, faces=bm.faces[:])
bm.faces.ensure_lookup_table()  # REQUIRED after triangulation
bm.verts.ensure_lookup_table()  # REQUIRED after triangulation
```

Without this, `bm.faces[i]` raises `IndexError: BMElemSeq[index]: outdated internal index table`.

## Edit-Mode Operators: `xray` Parameter Removed

`bpy.ops.mesh.vertices_smooth()` no longer accepts the `xray` parameter:
```python
# CORRECT (Blender 5.1):
bpy.ops.mesh.vertices_smooth(factor=0.5, repeat=1)

# WRONG (TypeError in 5.1):
bpy.ops.mesh.vertices_smooth(factor=0.5, repeat=1, xray=False)
```

## NumPy 2.0: `ndarray.ptp()` Removed

Blender 5.1 ships NumPy 2.3.4 where `ndarray.ptp()` is removed. Use `np.ptp(arr)` instead:
```python
# CORRECT:
np.ptp(arr)

# WRONG (AttributeError in NumPy 2.0+):
arr.ptp()
```

## Material API: `use_nodes` Deprecated

`Material.use_nodes` is deprecated in Blender 5.1, removed in 6.0. No replacement needed yet — still functional but prints `DeprecationWarning`.

## QuadRemesher: See `references/quad-remesher-blender51-api.md`

## Bake-to-GLB Material Connection (Critical Pitfall)

After texture baking, baked images are stored internally but NOT included in GLB
exports unless two steps are done:

1. **Pack images**: `img.pack()` — unpacked images are silently discarded on GLB export.
2. **Wire to material output**: Bake image nodes must be connected to the
   `Principled BSDF` → `Material Output` chain. GLB export only includes
   textures in the active material's output path:

```python
# Connect Bake_Diffuse → Principled BSDF.Base Color
diff_node = nodes.new('ShaderNodeTexImage')
diff_node.image = diffuse_img
links.new(diff_node.outputs['Color'], principled.inputs['Base Color'])

# Connect Bake_Normal → Normal Map → Principled BSDF.Normal
norm_tex = nodes.new('ShaderNodeTexImage')
norm_tex.image = normal_img
norm_tex.image.colorspace_settings.name = 'Non-Color'
norm_map = nodes.new('ShaderNodeNormalMap')
links.new(norm_tex.outputs['Color'], norm_map.inputs['Color'])
links.new(norm_map.outputs['Normal'], principled.inputs['Normal'])
```

**Verification**: Import the exported GLB back into Blender — check that
`Material.use_nodes` shows TEX_IMAGE nodes with the bake images connected
to the BSDF. Without this wiring, GLB will be ~12MB; with proper wiring
including 2048² textures, ~35MB+.

The QuadRemesher addon has its own set of Blender 5.1-specific quirks documented separately.

## Better FBX Addon

The `better_fbx` addon fails to register in Blender 5.1 background mode:
```
ModuleNotFoundError: No module named 'bpy_types'
```
Non-fatal. Does not affect any pipeline operations. The error prints at every session start when addons are loaded (no `--factory-startup`).

## CLI: `--python-expr` vs `--python` and `bpy` Scope

When using `--python-expr`, `bpy` is NOT automatically available in the expression scope. Every `--python-expr` must start with `import bpy`:
```bash
# CORRECT:
blender --background --python-expr "import bpy; ..."

# WRONG (NameError: name 'bpy' is not defined):
blender --background --python-expr "bpy.ops.wm.save_as_mainfile(...)"
```

Prefer `--python script.py` with a launcher script over `--python-expr` for multi-stage batch pipelines.

## CLI: Working Directory with `--background`

When `--background` is used WITHOUT a blend file path, `os.getcwd()` is the user's home directory, NOT the project directory. When `--background blend_file.blend` IS specified, `os.getcwd()` is the blend file's directory. **Always `cd` to the target output directory before invoking Blender for batch pipelines.**

## Batch Pipeline Pattern (launcher.py)

For multi-stage batch runs, use a single launcher script with `--python` instead of per-stage `--python-expr`:

```bash
# Stage launcher pattern:
(cd "$OUTPUT_DIR" && blender --background --factory-startup --python launcher.py -- repair)
(cd "$OUTPUT_DIR" && blender --background "01_repair.blend" --factory-startup --python launcher.py -- adhesion)
```

The launcher routes via `sys.argv[-1]` to the correct stage function. This avoids `import bpy` scope issues with `--python-expr`.

## Voxel Remesh: Minimum Usable voxel_size

For human body models with fingers:
- `voxel_size=0.005` (5mm): **destroys fingers** — merges adjacent digits into blobs. Result: ~34K verts.
- `voxel_size=0.002` (2mm): **preserves fingers** — resolves ~2-3mm finger gaps. Result: ~218K verts (6.4x).
- Trade-off: smaller voxel = larger mesh, but QuadRemesher handles 218K fine as input.

## Adhesion Detection: Scaling Limit

KDTree-based face-pair detection in `adhesion.py` uses `find_range()` on every face, making it effectively O(N²) for dense meshes. Above ~100K faces, it becomes intractable (minutes to hours). **Skip adhesion for voxel-remeshed meshes >100K faces** — voxel remeshing already produces watertight, non-self-intersecting output.
