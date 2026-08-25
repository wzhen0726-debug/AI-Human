# Simplified Pipeline Batch Testing Workflow

## Critical Pitfalls

### 1. `--python-expr` vs `--python`
`--python-expr` runs an inline Python string. `bpy` is NOT automatically imported in this scope — you must add `import bpy` at the start of every `--python-expr`. Prefer `--python script.py` instead, which runs a full script file with its own imports.

### 2. Working directory matters
When using `--python script.py` with `--background` (no blend file), `os.getcwd()` is the user's home directory. When using `--background blend_file.blend`, `os.getcwd()` is the blend file's directory. **Always `cd` to the target run directory before invoking Blender** to ensure output files land in the right place.

### 3. Launcher script pattern
Use a single launcher script that accepts a stage name as argument, rather than inline `--python-expr` strings. The launcher handles all imports internally and uses `os.getcwd()` for output paths.

```python
# launcher.py pattern
STAGE = sys.argv[-1]  # repair|adhesion|remesh|uv|bake|glb
RD = os.getcwd()
sys.path.insert(0, SCRIPTS)

if STAGE == "repair":
    bpy.ops.import_scene.gltf(filepath=GLB)
    import repair
    obj = repair.get_main_mesh()
    repair.repair_pipeline(obj, ...)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RD, "01_repair.blend"))
# ... etc for each stage
```

Invoke from batch script:
```bash
(cd "$RD" && "$BLENDER" --background --factory-startup --python "$LAUNCHER" -- repair)
```

### 4. Verify consistency across runs
After batch runs, verify vertex count, BBox, UV, and texture presence are identical across all runs. A valid pipeline produces bit-for-bit identical geometry.

## Quad Remesher Async Pattern

Quad Remesher runs an external process. The Blender operator returns immediately after starting it. You MUST poll for completion:

```python
bpy.ops.qremesher.remesh()  # starts external process, returns immediately

# Poll progress.txt until "2" (complete) or retopo.fbx appears
temp_dir = r'C:/Users/.../Exoside/QuadRemesher/Blender'
for i in range(300):  # 5 min timeout
    time.sleep(1)
    # Check progress.txt value >= 2.0
    # Check retopo.fbx exists and >100KB
    if done: break

# Import result
bpy.ops.import_scene.fbx(filepath=retopo_path)
```

## Blender 5.1 API Changes

See `references/blender51-api-migration.md` for the full migration guide. Key changes from this session:

| Old API | Blender 5.1 API |
|---------|-----------------|
| `bpy.ops.quadremesher.remesh(...)` | `bpy.ops.qremesher.remesh()` + set `scene.qremesher.*` properties |
| `cycles.bake.use_cage = True` | `scene.render.bake.use_cage = True` |
| `bpy.ops.export_scene.gltf(export_colors=...)` | Remove `export_colors` parameter |
| `bpy.ops.mesh.vertices_smooth(xray=...)` | Remove `xray` parameter |
| `bmesh.ops.triangulate()` + face access | Re-call `ensure_lookup_table()` after triangulate |