# Auto-Rig Pro Smart in Background Mode

> Tested 2026-07-16/17 on Blender 5.1.0 with Auto-Rig Pro v3.76.22 (Chinese localization).

ARP's Smart auto-rigging (AI-based body marker detection + rig generation) was designed for interactive GUI use. Running it in `--background` mode requires three monkey-patches. The technique is reusable for any headless ARP automation.

## Prerequisites

- **ARP addon**: installed at `~/AppData/Roaming/Blender Foundation/Blender/5.1/scripts/addons/auto_rig_pro-master/`
- **AI inference binaries**: must be downloaded separately. Default path is `~/Documents/AutoRigPro/AI/inference/`. Contains: `inference_front.exe`, `inference_side.exe`, `inference_top.exe`, plus `.pth` model files and `info.dat`. Set the path via `prefs.preferences.ai_presets_path`.
- **Enable ARP in background**: `bpy.ops.preferences.addon_enable(module='auto_rig_pro-master')`

## The Three Required Patches

### Patch 1: Context Override (VIEW_3D area + WINDOW region)

ARP's internal functions access `bpy.context.area` directly (to set viewport filters, overlays, shading). In `--background`, `bpy.context.area` is `None`. Must override:

```python
# Switch to a screen that has VIEW_3D
bpy.context.window.screen = bpy.data.screens['Layout']

# Find VIEW_3D area and WINDOW region
area = None
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        area = a
        break
region = None
for r in area.regions:
    if r.type == 'WINDOW':
        region = r
        break

# Override context for ALL ARP operator calls
with bpy.context.temp_override(area=area, region=region):
    bpy.ops.id.get_selected_objects('EXEC_DEFAULT')
    bpy.ops.arp.guess_markers('EXEC_DEFAULT')
    bpy.ops.id.go_detect('EXEC_DEFAULT')
```

**Without region**: `bpy.ops.view3d.view_axis(type='FRONT')` fails with `poll() failed, context is incorrect`.

### Patch 2: _screenshot_char → Cycles instead of OpenGL

ARP's `guess_markers` calls `_screenshot_char()` which renders orthographic front/side/top views via `bpy.ops.render.opengl()`. This **fails in background mode** ("无法在背景模式下使用 OpenGL 渲染"). Must monkey-patch to use Cycles:

```python
import sys
# Find the ARP smart module in sys.modules (name has hyphen, can't import directly)
ars = None
for key, mod in sys.modules.items():
    if 'auto_rig_smart' in key and hasattr(mod, '_screenshot_char'):
        ars = mod
        break

def screenshot_patched(self):
    # ... replicate _screenshot_char logic but use:
    scn.render.engine = 'CYCLES'
    scn.cycles.samples = 1
    scn.render.resolution_x = 256
    scn.render.resolution_y = 256
    # Create flat gray material (0.8,0.8,0.8) on body_temp
    # Set dark background (0.04,0.04,0.04) in world
    # Use bpy.ops.render.render(write_still=True) instead of bpy.ops.render.opengl()
    # Camera: orthographic, same positions as original
    # Save JPGs to self.inf_path (AI inference directory)

ars._screenshot_char = screenshot_patched
```

**Critical**: The AI models were trained on Solid shading screenshots — gray model (0.8,0.8,0.8) on dark background (0.04,0.04,0.04). Using Cycles with materials/textures or white background produces garbage keypoints (all at 252/0 borders). Must replicate the solid-gray-on-dark-background look via a temporary flat gray Principled BSDF material.

### Patch 3: display_popup_message → print to console

ARP calls `display_popup_message()` on errors, which uses `bpy.context.window_manager.popup_menu()`. This **crashes Blender** (`EXCEPTION_ACCESS_VIOLATION` in `popup_menu_end`) in background mode. Must patch:

```python
ara = None
for key, mod in sys.modules.items():
    if 'auto_rig' in key and hasattr(mod, 'display_popup_message'):
        ara = mod
        break

def popup_patched(message, header=' ', icon_type=''):
    print(f"[ARP {header}] {message}")

ara.display_popup_message = popup_patched
```

## Model Orientation Detection (Critical)

ARP expects: **Z-up, arms along X, front facing -Y**.

Tripo AI models often export with arms along Y (arm span = Y dimension, body width = X dimension). This causes ARP's AI keypoints to map to wrong 3D positions — markers end up outside the mesh, ray-casting fails, and `go_detect` crashes with `TypeError: unsupported operand type(s) for -: 'NoneType' and 'float'`.

**Detection + fix**:
```python
xs = [v.co.x for v in mesh.data.vertices]
ys = [v.co.y for v in mesh.data.vertices]
dim_x = max(xs) - min(xs)
dim_y = max(ys) - min(ys)
if dim_y > dim_x * 2:
    # Arms along Y — rotate 90° CW around Z via bmesh
    # new_x = old_y; new_y = -old_x → face goes from +X to -Y (correct for ARP)
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    for v in bm.verts:
        old_x, old_y = v.co.x, v.co.y
        v.co.x = old_y
        v.co.y = -old_x
    bm.to_mesh(mesh.data)
    bm.free()
    mesh.data.update()
```

**⚠️ Do this rotation ONCE in the repair stage, NOT in the rig stage.** All subsequent stages (adhesion, remesh, UV, bake, rig) inherit the correct orientation. Rotating in the rig stage after baking causes the texture to be misaligned with the mesh, and requires a second rotation back after rigging — wasteful and error-prone. The user explicitly corrected this: "旋转做了好几次，优化旋转次数" (rotation done multiple times, optimize rotation count).

**Rotation direction matters**: There are two possible 90° rotations around Z. The correct one is CW (clockwise): `new_x = old_y; new_y = -old_x`. This maps:
- Arms: Y → X (correct — arms now extend along X)
- Face: +X → -Y (correct — face now faces -Y, toward ARP's front camera at -Y)

The other direction (CCW: `new_x = -old_y; new_y = old_x`) maps face to +Y — ARP's front camera would see the back of the model, causing garbage keypoints.

## ARP Smart Workflow (3 steps)

1. **`id.get_selected_objects`** — Duplicates + joins mesh into `body_temp`, prepares for detection. Requires active mesh selected. Sets `arp_smart_type='BODY'`.

2. **`arp.guess_markers`** — Takes screenshots → runs AI inference (`inference_front.exe` etc. via subprocess threads) → fetches keypoints from JSON output files (`front1_kp.py`, `kp_side.py`, `kp_top.py`) → places 3D marker empties (`root_loc`, `neck_loc`, `chin_loc`, `shoulder_loc`, `hand_loc`, `foot_loc`, `thigh_loc`, `knee_loc`, `elbow_loc`, `hand_tip_loc` + `_sym` variants for right side).

3. **`id.go_detect`** — Builds armature from markers, ray-casts mesh for body depth, computes skin weights. The most failure-prone step.

## Known Issue: go_detect shoulder ray-cast failure

Even after orientation fix, `go_detect` may fail with "找不到肩部,标记脱离网格?" (Can't find shoulder, marker detached from mesh?). The ray-cast from shoulder marker through the mesh body returns None. Setting `scn.arp_smart_depth = False` before `go_detect` changes the code path to use marker Y positions instead of ray-cast depths, but BOTH `shoulder_front` and `shoulder_back` can still be None.

**Solution (2026-07-16, improved)**: The root cause is AI edge-detection failures. When the AI can't detect a body part, it returns edge coordinates (252, 0) which pollute the averaged marker positions, placing markers outside the mesh. The fix is to **override marker positions from mesh geometry** after `guess_markers` but before `go_detect`. Use vertex-band center lookup at specific Z-height percentages, and **clamp all positions to the mesh bounding box** so markers never fall outside the mesh:

```python
def fix_marker_positions():
    body_temp = bpy.data.objects.get('body_temp')
    mesh = body_temp.data
    verts = mesh.vertices
    xs = [v.co.x for v in verts]; ys = [v.co.y for v in verts]; zs = [v.co.z for v in verts]
    min_x, max_x = min(xs), max(xs); min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    midx = (min_x + max_x) / 2; midy = (min_y + max_y) / 2
    H = max_z - min_z

    def clamp(val, lo, hi, m=0.02):
        return max(lo + m, min(hi - m, val))

    def set_marker(name, x, y, z):
        o = bpy.data.objects.get(name)
        if o:
            o.location = (clamp(x, min_x, max_x), clamp(y, min_y, max_y), clamp(z, min_z, max_z))

    def find_band_center(z_lo, z_hi, x_filter=None):
        band = [v for v in verts if z_lo <= v.co.z <= z_hi]
        if x_filter: band = [v for v in band if x_filter(v.co.x)]
        if not band: return midx, midy
        return (sum(v.co.x for v in band)/len(band), sum(v.co.y for v in band)/len(band))

    # Root at 42% height, center of vertex band
    z = min_z + H * 0.42
    bx, by = find_band_center(z - H*0.02, z + H*0.02)
    set_marker('root_loc', bx, by, z)

    # Shoulders at 80% height — find actual X from vertex band
    z = min_z + H * 0.80
    band = [v for v in verts if abs(v.co.z - z) < H*0.025]
    right_x = max(v.co.x for v in band) if band else max_x * 0.35
    left_x = min(v.co.x for v in band) if band else min_x * 0.35
    set_marker('shoulder_loc', right_x, midy, z)
    set_marker('shoulder_loc_sym', left_x, midy, z)

    # Hands at 58% height (T-pose), at 85% of max X
    z = min_z + H * 0.58
    set_marker('hand_loc', max_x * 0.85, midy, z)
    set_marker('hand_loc_sym', min_x * 0.85, midy, z)

    # ... elbows (55%), thighs (38%), knees (22%), feet (3%) + _sym variants
```

**Key improvements over v1**:
1. **Vertex-band center lookup** — instead of hardcoding `midx`/`midy`, compute the actual center of vertices at each Z-height band. This ensures markers are ON the mesh surface, not at bounding-box extremes.
2. **Clamp to bbox** — all marker positions are clamped to `[min+m, max-m]` so they never fall outside the mesh. The user corrected: "绑定点都不在模型上，仔细调整" (binding points not on the model, adjust carefully).
3. **Corrected Z-heights** — root 42% (was 45%), hands 58% (was 60%), feet 3% (was 5%) — tuned from actual T-pose human proportions.

After `fix_marker_positions()`, set `scn.arp_smart_depth = False` before `go_detect`. This successfully generates a 339-bone armature. Weights are NOT auto-bound by ARP in background mode — must manually run `bpy.ops.object.parent_set(type='ARMATURE_AUTO')` with context override afterward.

**Full working sequence**:
1. `patch_screenshot_for_background()` — patches 2+3
2. `bpy.ops.id.get_selected_objects('EXEC_DEFAULT')` — step 1
3. `bpy.ops.arp.guess_markers('EXEC_DEFAULT')` — step 2
4. `fix_marker_positions()` — override AI markers with geometry
5. `scn.arp_smart_depth = False`
6. `bpy.ops.id.go_detect('EXEC_DEFAULT')` — step 3 (now succeeds)
7. Manual weight binding: `parent_set(type='ARMATURE_AUTO')` with context override

**Result**: 223K-vert mesh → 339-bone armature + 67 vertex groups (auto-weights). GLB export with skins succeeds.

## Known Issue: ARP Rig Scale Mismatch (2x model size) — 2026-07-17

**Symptom**: The generated armature's bones are positioned at ~2x the model's coordinates. The model is 0.976m tall (Z[0.001, 0.976]), but the root bone appears at Z=0.896 (should be ~0.41) and the head bone at Z=1.485-1.762 (completely above the mesh). The skeleton is roughly 1.8x the model height.

**Root cause**: ARP's rig template is designed for a ~1.8m tall human. When markers are placed at correct proportions (root 42% of 0.976m = 0.41m), ARP scales the rig template to match a 1.8m interpretation. The rig template's bone lengths, offsets, and control shapes are all in 1.8m-proportioned space.

**Quick fix — scale armature to 0.5**:
```python
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
arm.scale = (0.5, 0.5, 0.5)
bpy.context.view_layer.update()
```

**Verification after scaling** (mesh height 0.976m):
- root_ref.x world Z: 0.448 (target ~0.41 — close)
- head.x world Z: 0.742 (target ~0.87 — slightly low but acceptable)

**⚠️ This is a non-uniform mismatch** — scale 0.5 makes root close but head is still 12% off. The rig template's internal proportions (spine length vs leg length ratio) differ from this particular model. For exact matching, the model should be scaled UP to ~1.8m before rigging, then the final GLB scaled back down. But scale-0.5 is a quick workaround that produces usable results.

**Better approach (untested)**: Scale the mesh to 1.8m height before ARP rigging (`mesh.scale = (1.8/0.976, 1.8/0.976, 1.8/0.976)`, apply scale), run ARP, then scale both mesh and armature back to original size. This ensures ARP's rig template matches the model at its designed scale.

## VERDICT: ARP abandoned for non-standard model sizes (2026-07-17)

After extensive debugging, ARP Smart was abandoned in favor of `scripts/rig_manual.py`
(manual rig from mesh geometry). The fundamental issue: ARP's rig template has FIXED
proportions for a ~1.95m human. Uniform scaling (0.5) compresses limbs and stretches
the spine, creating a "giraffe skeleton" (长颈鹿骨骼). The user explicitly corrected:
"我说差一半左右，你就真直接缩放一半？？那一半也没对上啊" and "骨骼更不对了...成了长颈鹿骨骼了".

The manual rig approach creates 18 bones directly at mesh vertex positions — no template,
no scaling, no mismatch. All 18 bones land exactly on the mesh, all 18 get auto-weights.
Use `references/manual-rig-from-mesh-geometry.md` instead.

ARP Smart is still viable for models that are already ~1.8m tall. For smaller/larger
models, use the manual rig.

```
~/Documents/AutoRigPro/AI/
├── info.dat
├── inference/
│   ├── inference_front.exe
│   ├── inference_side.exe
│   ├── inference_top.exe
│   ├── front_model.pth
│   ├── side_model.pth
│   ├── top_model.pth
│   ├── fingers_model.pth
│   └── fingers4_model.pth
```

The inference exes take JPG filenames as CLI args and output JSON keypoint files. They are standalone PyTorch-compiled binaries — no Python/GPU needed on the target machine.

## ARP Module Import in Python

The addon folder is `auto_rig_pro-master` (with hyphen). Python cannot import hyphenated module names directly. Instead, find it in `sys.modules` after enabling:

```python
for key, mod in sys.modules.items():
    if 'auto_rig_smart' in key:
        ars = mod  # This is the auto_rig_smart module
```
