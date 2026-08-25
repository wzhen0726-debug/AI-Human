# QR Semi-Automatic Pattern (Hermes / Background Session)

> Use when xremesh.exe cannot run from the current session (Hermes agent, SSH, service, any non-interactive Windows session).
> Verified 2026-07-30 on Blender 5.1 + QR Bridge 1.3.2.

## Why full automation fails from Hermes

xremesh.exe is a Qt GUI program (PE32+ GUI). It needs an interactive Windows window station (`winsta0\default`) to initialize QApplication and pump messages. Hermes runs in a background session without a desktop, so Qt deadlocks at ~21% progress.

## Pattern: Script + User Click + Script Resume

### Step 1 — Agent script (runs in Blender `--background` or Text Editor)

```python
import bpy, os, tempfile, time

# 1. Load high-poly
bpy.ops.wm.open_mainfile(filepath=HIGHPOLY_BLEND)

# 2. Select mesh
mesh = [o for o in bpy.data.objects if o.type == 'MESH'][0]
bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh

# 3. Export FBX to QR temp
QR_TEMP = os.path.join(tempfile.gettempdir(), "Exoside", "QuadRemesher", "Blender")
os.makedirs(QR_TEMP, exist_ok=True)
input_fbx = os.path.join(QR_TEMP, "inputMesh.fbx")
bpy.ops.export_scene.fbx(filepath=input_fbx, use_selection=True)

# 4. Write settings
settings = os.path.join(QR_TEMP, "RetopoSettings.txt")
retopo_fbx = os.path.join(QR_TEMP, "retopo.fbx")
progress = os.path.join(QR_TEMP, "progress.txt")
for p in (retopo_fbx, progress):
    if os.path.exists(p): os.remove(p)

with open(settings, 'w') as f:
    f.write('HostApp=Blender\n')
    f.write(f'FileIn="{input_fbx}"\n')
    f.write(f'FileOut="{retopo_fbx}"\n')
    f.write(f'ProgressFile="{progress}"\n')
    f.write('TargetQuadCount=250000\n')
    f.write('CurvatureAdaptivness=80\n')
    f.write('ExactQuadCount=0\n')
    f.write('UseVertexColorMap=0\n')
    f.write('UseMaterialIds=0\n')
    f.write('UseIndexedNormals=0\n')
    f.write('AutoDetectHardEdges=1\n')
    f.write('SymAxis=X\n')
    f.write('SymLocal=1\n')

# 5. Prompt user
print("\n" + "="*60)
print("MANUAL STEP REQUIRED")
print("="*60)
print("1. In Blender GUI, press N to open sidebar")
print("2. Click '四边重构' tab")
print("3. Set Quad Count = 250000")
print("4. Click 'One click ReTopo'")
print("5. Wait for completion (~1-2 min)")
print("="*60)
input("Press Enter when QR is done...")

# 6. Import result
if not os.path.exists(retopo_fbx):
    raise RuntimeError("retopo.fbx not found — did QR finish?")
bpy.ops.import_scene.fbx(filepath=retopo_fbx)

# 7. Continue with cleanup / save / export...
```

### Step 2 — User action (interactive Blender GUI)

- User clicks the QR button in Blender's N-panel
- xremesh.exe runs in the user's interactive session (Session 1) and completes normally

### Step 3 — Script resumes

- The script (still running in Blender's Text Editor or terminal) detects `retopo.fbx` and continues with import, cleanup, save, export.

## Key points

- The script must run **inside Blender GUI** (Text Editor → Run Script), not from `--background` or Hermes terminal.
- `input()` pauses Blender's Python console — this is fine in GUI mode.
- For a smoother UX, replace `input()` with a modal dialog or a file-watch loop with a "Waiting for retopo.fbx..." print every 5s.

## Alternative: User runs the whole script in GUI

If the user prefers zero Hermes involvement:
1. User opens Blender GUI
2. User opens the script in Text Editor
3. User clicks Run Script
4. Script does steps 1-4, prints instructions, waits
5. User clicks QR button
6. Script resumes automatically

This is the most reliable pattern for a zero-budget solo developer.
