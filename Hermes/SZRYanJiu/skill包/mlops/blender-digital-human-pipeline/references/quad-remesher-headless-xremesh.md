# Quad Remesher Headless (Background) Execution — xremesh.exe Direct Call

> Verified 2026-07-29 on Blender 5.1 + Quad Remesher Bridge 1.3.2 (汉化版 GJJ).
> QR produced 86,542 quads from a 1.93M-face Tripo high-poly in ~90 seconds.

## Problem: `bpy.ops.qremesher.remesh()` cannot run in `--background`

`QREMESHER_OT_remesh.execute()` returns `{'RUNNING_MODAL'}` and relies on
`context.window_manager.event_timer_add(0.3, window=context.window)` +
`modal_handler_add(self)`. In `--background` mode there is no window, so the
operator is cancelled immediately (`cancel called!!!` in console) after only
exporting the input FBX — no remeshing ever happens.

## Addon enable quirk

```python
import addon_utils
try:
    addon_utils.enable('bl_ext.user_default.quadremesher')
except KeyError:
    pass  # KeyError is EXPECTED — operators + scene.qremesher register anyway
```

- `'quadremesher'` (short name) fails with "No module named 'quadremesher'".
- `'bl_ext.user_default.quadremesher'` raises `KeyError: bpy_prop_collection[key]`
  from its own register() UI code, BUT `bpy.ops.qremesher.remesh` and
  `bpy.context.scene.qremesher` are both registered and usable. Catch and continue.

## Solution: call `xremesh.exe` directly via subprocess

QR's operator is just a wrapper around an external engine. You can drive it
yourself in 3 steps:

### 1. Export the high-poly as FBX to the QR temp dir

```python
import os, tempfile
QR_TEMP = os.path.join(tempfile.gettempdir(), "Exoside", "QuadRemesher", "Blender")
os.makedirs(QR_TEMP, exist_ok=True)
input_fbx = os.path.join(QR_TEMP, "inputMesh.fbx")

bpy.ops.object.select_all(action='DESELECT')
high_poly.select_set(True)
bpy.context.view_layer.objects.active = high_poly
bpy.ops.export_scene.fbx(filepath=input_fbx, use_selection=True,
                         use_mesh_modifiers=False, mesh_smooth_type='OFF',
                         bake_anim=False, path_mode='AUTO')
```

### 2. Write RetopoSettings.txt

```python
settings_file = os.path.join(QR_TEMP, "RetopoSettings.txt")
retopo_fbx    = os.path.join(QR_TEMP, "retopo.fbx")
progress_file = os.path.join(QR_TEMP, "progress.txt")

# Remove stale outputs so the wait-loop doesn't exit early
for f in (retopo_fbx, progress_file):
    if os.path.exists(f): os.remove(f)

with open(settings_file, 'w') as f:
    f.write('HostApp=Blender\n')
    f.write(f'FileIn="{input_fbx}"\n')
    f.write(f'FileOut="{retopo_fbx}"\n')
    f.write(f'ProgressFile="{progress_file}"\n')
    f.write('TargetQuadCount=140000\n')     # Adjust to hit ≤300K triangles. 1 quad ≈ 2 tris.
    f.write('CurvatureAdaptivness=80\n')      # 0-100, higher = denser quads in high-curvature areas
    f.write('ExactQuadCount=0\n')              # 0 = adapt_quad_count True
    f.write('UseVertexColorMap=0\n')
    f.write('UseMaterialIds=0\n')
    f.write('UseIndexedNormals=0\n')
    f.write('AutoDetectHardEdges=1\\n')
    # SymAxis=XYZ + SymLocal=1  if symmetry needed — SEE WARNING BELOW before enabling
```

### 3. Launch xremesh.exe and poll for retopo.fbx

**CRITICAL**: Set `cwd=engine_dir` so xremesh can find its DLLs (`xremeshlib.dll`,
`Qt5Core.dll`, etc). Without this, the engine may start but fail to compute.

```python
import subprocess, time
QR_ENGINE = r"C:\Users\<user>\AppData\Roaming\Blender Foundation\Blender\5.1\extensions\user_default\quadremesher\EngineWin\xremesh.exe"
engine_dir = os.path.dirname(QR_ENGINE)

proc = subprocess.Popen([QR_ENGINE, "-s", settings_file],
                        cwd=engine_dir,  # CRITICAL: ensures DLL loading
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

start, timeout = time.time(), 900
while time.time() - start < timeout:
    if os.path.exists(retopo_fbx):
        time.sleep(2)   # let the writer finish
        break
    if os.path.exists(progress_file):
        print(open(progress_file).read().strip())   # e.g. "0.7547"
    time.sleep(5)
else:
    proc.kill(); raise TimeoutError("xremesh timed out")

proc.terminate()
try: proc.wait(timeout=5)
except Exception: proc.kill()
```

### 4. Import the result

```python
bpy.ops.import_scene.fbx(filepath=retopo_fbx)
qr_obj = bpy.context.active_object
# Name comes in as "Retopo_<original_name>" — select by that prefix, NOT by
# face count, because the high-poly is still in the scene.
```

## Pitfalls

- **Do NOT identify the QR output by "lowest face count" alone if other low-poly
  objects may exist** — QR names its output `Retopo_<inputname>`. Filter on the
  `Retopo_` prefix first, fall back to face count.
- **xremesh.exe needs VC++ runtimes** — the EngineWin folder ships
  `Windows_Patch_vcredist_x64.exe`; QR's modal operator auto-launches it after
  20s of no progress file. In headless mode, if no `progress.txt` appears within
  ~20s, install the redist manually.
- **The progress file lags** — it may sit at 0.96 for a while at the end. Wait
  for `retopo.fbx` itself, not for progress==1.0.
- **Result deviation & triangle ceiling**: TargetQuadCount=140000 produced 134,674 quads (269,334 triangles) on a resized (1.81m) Tripo model. **Always verify `quads*2+tris ≤ 300000`** — the user's ceiling is 30万三角面 (Mixamo safe limit). If the model was resized/scaled, QR allocates more faces — tune TargetQuadCount down accordingly. ExactQuadCount=0 (adaptive) is recommended; exact mode is slower and less robust. **Tuning history**: 250000→470K tri (too many), 150000→307K tri (still over on resized model), 140000→269K tri (correct).

- **ZED camera conflict (2026-07-30)**: ZED.exe blocks xremesh startup — kill ZED before QR (`taskkill /F /T /IM Zed.exe`). ZED auto-restarts; kill repeatedly during long runs. See `zed-camera-xremesh-conflict.md`.

- **~~Hermes/background-session stall at ~21% (2026-07-30)~~** — **DISPROVEN (2026-07-31)**: The ~21% stall is caused by **input mesh fragmentation** (unwelded duplicate vertices + open boundary edges), NOT by Qt/session/window-station issues. `subprocess.Popen([engine, "-s", settings], cwd=engine_dir)` works perfectly from Hermes `--background` Blender. The same engine, same session, same settings succeeds when given a clean (welded) mesh. The earlier "Qt GUI needs interactive session" hypothesis was wrong — xremesh's batch path (`-s` flag) does not depend on interactive Window Station. **Correct fix**: always weld the mesh before exporting FBX (see next bullet).

- **Input mesh fragmentation deadlock (2026-07-31)**: If xremesh stalls at ~21% even in an interactive session, the root cause is a **fragmented input mesh** (unwelded duplicate vertices + open boundary edges). xremesh's preprocessing tries to stitch the fragments and enters pathological computation. Diagnosis: `remove_doubles` on the source mesh reports hundreds of thousands of merged verts; `is_manifold` edges equal boundary edges. Fix: weld vertices (`bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.0001)`) and fill residual holes (`edgeloop_fill`) before exporting FBX. Verified: 172,285 welded verts / 516,960 boundary edges → 11 boundary edges, QR completes in 90s. See `qr-input-mesh-welding.md`.

- **SymAxis=X symmetric retopo breaks asymmetric textures (2026-08-01, user decision)**: Writing `SymAxis=X` forces the QR output to be perfectly L/R mirrored (verified: 70,732 = 70,732 verts per side, 100% symmetric). The stated reason was "Mixamo auto-rig detects bones better on symmetric meshes". **But if the source model's clothing texture is itself asymmetric, mirrored topology + original asymmetric texture = misaligned bake.** The mirrored quads sample UV positions designed for the unmirrored layout. User rejected the result: "我不需要对称啊，对称后的纹理都不对了". **Default to NO SymAxis for AI-generated models with real textures.** Mixamo tolerates <5mm asymmetry fine (71,163 vs 70,092 verts post-QR is harmless). If bone placement comes out lopsided later, symmetrize the WEIGHTS after binding instead of the topology before it. See `qr-symmetry-decision.md`.

- **Local geometric anomaly repair pitfalls (2026-08-03)**: Chest/belly bump/dent repair using XZ-projection reference planes caused symmetric double pits. Correct approach: 3D Euclidean distance reference, diagnose before repair, verify vs original model. See `local-geometric-anomaly-repair.md`.

## Working script

A complete runnable implementation lives in the project at
`test02/mvp_pipeline/scripts/02_qr_remesh.py` (loads high-poly blend → FBX →
settings → xremesh → import → save).

> Related: `script-file-health-audit.md` — if the QR driver script "errors out" before
> ever reaching xremesh (SyntaxError at import, read_file shows it as binary), check for
> file-encoding corruption first; the logic is fine.
