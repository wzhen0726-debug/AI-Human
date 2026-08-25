# Quad Remesher Blender 5.1 API — Verified Working Patterns

Tested 2026-07-15 on Blender 5.1.0 with Exoside QuadRemesher addon (`bl_ext.user_default.quadremesher`).

## Operator Name

The addon registers as `bpy.ops.qremesher.remesh` — **NOT** `bpy.ops.quadremesher.remesh` as documented in older sources.

```python
# WRONG (old docs):
bpy.ops.quadremesher.remesh(target_count=250000, ...)

# CORRECT (Blender 5.1):
bpy.ops.qremesher.remesh()
```

## Parameter Setting

`bpy.ops.qremesher.remesh()` does NOT accept keyword arguments. All parameters are set via `bpy.context.scene.qremesher` property group:

```python
qr = bpy.context.scene.qremesher
qr.target_count = 250000       # Target quad count (default: 5000)
qr.symmetry_x = True           # X-axis symmetry (default: False)
qr.symmetry_y = False          # Y-axis symmetry
qr.symmetry_z = False          # Z-axis symmetry
qr.autodetect_hard_edges = True # Auto-detect hard edges (default: True)
qr.adaptive_size = 50.0        # Curvature adaptiveness 0-100 (default: 50.0)
qr.adapt_quad_count = True     # Adapt quad count to hit target (default: True)
qr.use_materials = False       # Use material boundaries for edge flow
qr.use_normals = False         # Use normals for edge flow
qr.use_vertex_color = False    # Use vertex color for density control
qr.painted_quad_density = 1.0  # Vertex color density multiplier
```

## Async Execution Pattern

`bpy.ops.qremesher.remesh()` is **asynchronous** — it starts an external QuadRemesher process and returns immediately. The external process:

1. Exports mesh to `%TEMP%/Exoside/QuadRemesher/Blender/inputMesh.fbx`
2. Writes `RetopoSettings.txt` (overwrites scene property settings!)
3. Writes `progress.txt` with float progress values (0.0 → 2.0 = complete)
4. Outputs result to `retopo.fbx`

**Must poll for completion** — the script must NOT exit until the external process finishes:

```python
import os, time

temp_dir = r'C:/Users/<user>/AppData/Local/Temp/Exoside/QuadRemesher/Blender'
progress_file = os.path.join(temp_dir, 'progress.txt')
retopo_file = os.path.join(temp_dir, 'retopo.fbx')

# Call remesh (async)
bpy.ops.qremesher.remesh()

# Poll until complete (5 min timeout)
for i in range(300):
    time.sleep(1)
    if os.path.exists(progress_file):
        with open(progress_file) as f:
            content = f.read().strip()
        try:
            if float(content) >= 2.0:
                break  # Complete
        except ValueError:
            pass
    if os.path.exists(retopo_file) and os.path.getsize(retopo_file) > 100000:
        break  # Result file exists and is substantial

# Import result
if os.path.exists(retopo_file):
    bpy.ops.import_scene.fbx(filepath=retopo_file)
```

## Symmetry Axis Selection (Critical Pitfall)

**The symmetry axis MUST match the model's left-right body axis, not front-back.**

Most Tripo AI models are oriented with:
- **X** = front-back depth (~0.17m for adult body)
- **Y** = left-right arm span (~0.97m in T-pose)
- **Z** = height (~0.97m)

For this orientation, use `symmetry_y=True` (left-right body symmetry). Using `symmetry_x=True` mirrors the front of the body to the back, creating a "Janus" double-sided model with duplicated arms and legs.

**How to determine the correct axis**:
```python
xs = [v.co.x for v in mesh.vertices]
ys = [v.co.y for v in mesh.vertices]
x_range = max(xs) - min(xs)
y_range = max(ys) - min(ys)

if y_range > x_range:
    qr.symmetry_y = True   # Y is left-right (arm span) — CORRECT for T-pose
    qr.symmetry_x = False
else:
    qr.symmetry_x = True   # X is left-right (uncommon but possible)
    qr.symmetry_y = False
```

**Always verify**: after remesh, the model should have ~equal vertex counts on +Y and -Y sides (for symmetry_y) and a single set of limbs, not doubled.

## QR Addon Not Installed — Manual Trigger Fallback (2026-07-16)

If `bpy.ops.qremesher.remesh()` fails with `ModuleNotFoundError: No module named 'quad_remesh'` (addon not in `scripts/addons/`), the QR standalone exe can be triggered manually:

1. Write `RetopoSettings.txt` manually (same format as shown above)
2. Export the mesh to `inputMesh.fbx` via `bpy.ops.export_scene.fbx(filepath=input_fbx, use_selection=True, mesh_smooth_type='FACE', bake_anim=False)`
3. Find `QuadRemesher.exe` in `C:/Program Files/Exoside/QuadRemesher/` or `C:/Program Files (x86)/Exoside/QuadRemesher/`
4. Run via `subprocess.run([qr_exe, '-settings', settings_path], timeout=300)`
5. Poll for `retopo.fbx` (same as addon workflow)
6. Import via `bpy.ops.import_scene.fbx(filepath=retopo_path)` — imports as `Retopo_<original_name>`

If no QR exe is found, reuse the previously generated `retopo.fbx` from a prior run (persists in temp folder). The retopo.fbx imports fine with Blender's built-in FBX importer — do NOT need Better FBX addon.

## Settings File Overwrite

`bpy.ops.qremesher.remesh()` writes its own `RetopoSettings.txt` based on `scene.qremesher` properties. Manual pre-writing of this file is NOT needed — the operator reads scene properties and writes the file correctly.

**Verified**: Scene property `target_count=250000` produced a 234K-face result (within expected range). Default `target_count=5000` produced only 7K faces.

## Blender 5.1 Compatibility Warning

The operator produces a non-fatal runtime error in Blender 5.1:
```
RuntimeError: expected class QREMESHER_OT_remesh, function cancel to return None, not set
```
This does NOT prevent the remesh from completing. The external process runs successfully.

## Concurrency / Batch-Run Warning

QR temp files are shared across invocations. Running two QR processes in rapid succession can cause file conflicts (stale `retopo.fbx` from previous run detected before new process finishes). **Wait at least 5 seconds between remesh calls** in batch mode, or clean `%TEMP%/Exoside/QuadRemesher/Blender/` before each run.

## Batch Testing Pattern

Use `cd $RD && blender --background --python launcher.py -- <stage>` to run stages in isolated directories. The launcher script routes to the correct stage function. **Always `cd` before each Blender call** so `os.getcwd()` resolves to the run directory. Use `--factory-startup` for stages that don't need addons (repair, adhesion, UV, bake, GLB) and omit `--factory-startup` for remesh (needs QuadRemesher addon).

The `better_fbx` addon (installed by user) fails to register in Blender 5.1:
```
ModuleNotFoundError: No module named 'bpy_types'
```
This is non-fatal — it does not affect QuadRemesher or any other pipeline stage. The error appears in every Blender 5.1 background session when addons are loaded.