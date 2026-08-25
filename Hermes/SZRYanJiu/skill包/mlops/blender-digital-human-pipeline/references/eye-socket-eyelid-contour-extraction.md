# Eyelid Contour Extraction (替代3DDFA, 2026-08-20)

## Problem: 3DDFA contour is eye SLIT, not eye socket boundary

The 3DDFA eyelid contour (`eyelid_contour.json`) is the **eye slit** (眼裂, the narrow opening between upper/lower eyelids, ~26.8×9.7mm almond shape). The user wants the **eye socket boundary** (眼窝边界) — the actual eyelid margin (睫毛根部深色线) which is larger and may extend further down/outward.

**Key diagnostic**: check if the model's eye is texture-painted or has real geometric folds. Tripo AI models often have painted eyes on smooth geometry (no real socket depression). In this case, geometric extraction (radial gradient, curvature) WILL fail — there's no fold to detect.

### Verification: is the eye geometry real or painted?

- Check vertex count near iris center: < 20 vertices at r<3mm = painted eye (no real eyeball geometry)
- Check radial y-profile: monotonic y(r) with no local minimum = no socket rim fold
- Check if the model has a real eye hole (open boundary edges in eye region)

## Semi-automatic eyelid marker workflow (when geometric extraction fails)

**When**: geometry is smooth (painted-on eye), automatic extraction fails, and user wants precise boundary aligned to the texture's painted eyelid line.

**Prerequisite**: 3DDFA center_3d is accurate (0.6mm from nearest vertex on this model). The config's IRIS_L may be wrong (6mm off) — use `load_3ddfa_centers()` from the pipeline, NOT `eye_socket_config.IRIS_L`.

### Step 1: Place markers on input model

Script: `place_eyelid_markers.py` in the eye socket scripts directory.

Design:
- 12 markers per eye, evenly spaced along the initial 3DDFA eyelid contour (arc-length resampled from 6 to 12 points)
- Each marker is an Empty (SPHERE, 2.5mm) with **Shrinkwrap constraint** (NEAREST_SURFACE, target=model mesh) — stays on surface during drag
- `show_in_front=True` for X-ray visibility
- Naming: `LM_01_外眼角_outer_canthus_L` through `LM_12_下睑外_lower_outer_L`
- Separate collections `LM_L` and `LM_R` with color coding (red/blue)
- Output: `models/01A_markers_eyelid.blend`

**Blender 5.1 pitfall**: Shrinkwrap constraint type is `'NEAREST_SURFACE'` (NOT `'NEAREST_SURFACE_POINT'` which doesn't exist in 5.1).

### Step 2: User drags markers in GUI

User opens the blend in Blender GUI, switches to front view (Numpad 1), and drags each marker to align with the **painted eyelid margin** (睫毛根部那圈深色线) on the texture. The Shrinkwrap constraint ensures markers stay on the model surface. User only adjusts x/z in front view; y is auto-resolved.

### Step 3: Read markers back and generate contour

Script: `read_eyelid_markers.py`

- Reads all marker positions from `01A_markers_eyelid.blend`
- Generates `eyelid_contour_manual.json` in the same format as `eyelid_contour.json`
- Computes width/height/aspect/center for each eye
- Outputs to `screenshots/3ddfa/eyelid_contour_manual.json`

### Step 4: Run pipeline with manual contour

Point `EYELID_CONTOUR_JSON` to the manual contour file, then run `run_eye_socket.py` as normal. The `load_eyelid_contour()` function reads any JSON with the same structure.

## 3DDFA center vs config IRIS_L: known bug

- `iris_3ddfa.json` → `L.center_3d` = `(-0.0358, -0.1058, 1.6711)` — **0.6mm accuracy** (nearest vertex 0.6mm)
- `eye_socket_config.IRIS_L` = `(-0.0241, -0.1163, 1.6517)` — **6mm off** (nearest vertex 6mm)
- `run_eye_socket.py` correctly uses `load_3ddfa_centers()` which reads `center_3d` from DDFA_JSON
- Diagnostic scripts that import `IRIS_L` from `eye_socket_config` directly will get wrong positions
- Fix: always use `load_3ddfa_centers()` or check `center_3d` from iris_3ddfa.json

## Blender 5.1 API quirks (relevant to this workflow)

- `Matrix @ numpy.ndarray` — NOT supported. Use manual multiplication: `wverts[:,i] = mat[i][0]*verts[:,0] + mat[i][1]*verts[:,1] + mat[i][2]*verts[:,2] + mat[i][3]`
- Shrinkwrap constraint type enum: `'NEAREST_SURFACE'`, `'PROJECT'`, `'NEAREST_VERTEX'`, `'TARGET_PROJECT'` (NOT `'NEAREST_SURFACE_POINT'`)
- `bpy.scene` removed in 5.1, use `bpy.context.scene`
- Quick face data: `mesh.polygons.foreach_get('loop_start', arr)` and `mesh.polygons.foreach_get('loop_total', arr)` for batch access

## Vision API usage policy (user preference)

- **Minimize vision API calls** — they are expensive (kimi-k3 via nexlink, paid per use)
- Preferred: quantitative analysis (PIL pixel analysis, numpy, geometry measurements) over vision
- When needed: tell user WHAT to check in Blender GUI, user checks it themselves (more accurate + cheaper)
- Vision only for: qualitative "is there/isn't there" questions that can't be answered quantitatively
- Geometry position judgments: use world-coordinate bbox calculations, NOT vision