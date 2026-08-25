# Landmark-Based Retopology — Technique Detail

Reference for sub-workflow B of `blender-digital-human-pipeline`. Captures the non-obvious
decisions and bugs found while building `mp_v2_final.py` (iterating through 12 versions).
Read before modifying the landmark-retopology pipeline.

## Problem

Shrinkwrap wraps a template mesh onto a target surface but does NOT guarantee that specific
template vertices land on specific target features — a mouth-corner vertex can slide onto
the cheek, an eye vertex onto the nose. For animation-ready topology (MetaHuman), this breaks
the rig. The fix is a two-stage process: Shrinkwrap for bulk fit, then an anchor-point
iteration that forces pre-selected template vertices onto pre-detected target landmarks.

## Inputs

- **Target**: high-poly mesh in a `.blend` (scan head as `Scan_Head`, or Tripo GLB imported).
  Scan head carries `rotation_euler.x = 90°`; the template is rotated the same way so both
  share orientation (face toward -Y, top toward +Z after rotation).
- **Template**: MetaHuman `MH_Head_01.obj`, ~8.2K verts, pure quads. This is the
  "good-topology low-poly" the user provides.
- **MediaPipe model**: `face_landmarker.task` (Face Landmarker, 478 points). Input must be
  resized to 256×256 RGB.
- **Template landmark index**: `template_landmarks.json` — 21 vertex indices on the template
  (12 facial + 9 head). Built by `detect_template_landmarks.py` (MediaPipe on the template
  render) or `detect_template_geo.py` (geometric heuristics), then hand-verified in Blender.

## Pipeline (mp_v2_final.py)

1. **6-direction render** (±X, ±Y, ±Z), 512×512, WORKBENCH engine, Sun light energy 5.0.
   Camera distance = max(bbox) + 0.5m, look-at the bbox center.
2. **MediaPipe detection** on all 6 (resized to 256×256, BGR→RGB). Keep the view with the
   most landmarks — only the face-on view detects anything (back/side/top detect nothing).
3. **2D→3D mapping** for 12 facial landmarks: build a camera-space ray from the NDC pixel,
   transform to world then to target-local, `ray_cast` onto the target. If forward ray
   misses, retry the negative direction.
4. **Geometric estimation** for 9 non-facial points (ears, back-of-head, top, back-neck):
   axis-aligned rays from outside the bbox. **These are imprecise (50–200mm error) and must
   NOT enter the alignment or anchoring — validation only.**
5. **Template import + rotate** (90° X to match target). **Centroid-align using ONLY the 12
   facial points** — mixing in the imprecise geometric points drags the centroid off by
   ~100mm. Uniform scale from mean of 3-axis bbox ratios.
6. **Shrinkwrap ×4**: rounds 1–2 `NEAREST_SURFACEPOINT`, rounds 3–4 `PROJECT` (all axes,
   both directions). Each round followed by Corrective Smooth (2 iters, factor 0.15) to
   prevent tearing.
7. **Anchor iteration ×20** — the key step:
   - `alpha = 0.3 + 0.7 * (iter/19)` — ramp from gentle to full pull.
   - For each of the 12 facial anchors: `v.co = v.co.lerp(target_local, alpha)`.
   - For every non-anchor vertex: Laplacian smooth toward neighbor centroid, factor 0.3.
   - Usually converges (<0.1mm) within 10 iterations.
8. **Surface correction**: one light `NEAREST_SURFACEPOINT` Shrinkwrap + Corrective Smooth
   (1 iter, 0.1), then re-snap anchors to target (Shrinkwrap pulls them off again).
9. **Validate**: per-anchor world-space distance; KDTree (sampled) for overall surface
   distance — report mean and `%<1mm`.

## Bugs that cost real iterations

### Bug 1 — MediaPipe left/right is IMAGE-space, not anatomical
MediaPipe names `left`/`right` from the viewer's perspective (mirror). idx 33 is on the
image's left = the person's RIGHT eye; idx 263 is image-right = person's LEFT eye. Naively
mapping idx 33 → template `left_eye_outer` (anatomical, +X side) sends each eye to the
opposite side. **Fix**: swap every left/right pairing — idx 33 → `right_eye_outer`, idx 263
→ `left_eye_outer`, and the same swap for mouth corners, brows, eye inners.
Symptom before fix: 60–130mm anchor error. After fix: 0.0mm.

### Bug 2 — Centroid alignment contaminated by geometric points
Including the 9 imprecise geometric landmarks (ears/back/top, 50–200mm error) in the
centroid computation shifts the initial alignment by ~100mm. **Fix**: centroid and scale use
ONLY the 12 MediaPipe facial points (`t_idx_face`); geometric points are matched into a
separate list for validation only.

### Bug 3 — Shrinkwrap alone leaves features misplaced
Shrinkwrap has no concept of vertex correspondence. **Fix**: the 20-round anchor iteration
above. Without it, facial anchors sit 60–180mm off; with it, 0.0mm.

### Bug 4 — 12 core anchors pass metrics but CONCAVE features still misfit visually
**Symptom**: After the v1 pipeline (`scan_to_template_fit.py`), the 12 facial anchors read
0.0mm and overall surface distance reads mean 0.44mm / 94.7%<1mm — but visual QA shows:
- **Eye sockets float**: the template's eye-region vertices wrap onto the brow ridge /
  cheekbone (the nearest convex surface) instead of sinking into the socket concavity.
  Raycast probe: eye-socket template vertices shoot forward (-Y) and hit nothing within 50mm
  — they're suspended in front of the socket, not inside it.
- **Nose tip/lip penetrate**: `NEAREST_SURFACEPOINT` pulls thin-wall vertices (lip, nose ala)
  to the *opposite* lip's interior / the nasal cavity interior, causing the template mesh to
  cut through the target's lip/nose volume.

**Root cause**: Shrinkwrap `NEAREST_SURFACEPOINT` finds the nearest surface point globally,
with no notion of "this vertex should stay on the outside of this lip" or "this vertex should
sink into this socket." 12 sparse anchors pin only the eye corners / mouth corners / nose tip
— the *between* vertices (eye-socket rim, lip line, nose ala) are left to Shrinkwrap's
nearest-surface logic, which fails on every concave or thin-wall feature.

**Fix (v2 — `scan_to_template_fit_v2.py`)**: two changes, both required:
1. **Dense contour anchors** — map 104 MediaPipe contour points (not just 12) onto the
   target surface and match each to its nearest template vertex within 2cm. This pins the
   full eye-socket rim (32 pts), lip line (40 pts, outer+inner), nose ala (12 pts), and
   brows (20 pts) — so the between-vertices are also anchored, not left to Shrinkwrap.
   Template sparsity caps real coverage: ~57 effective anchors out of 104 attempted
   (8280-vert MetaHuman has no vertex within 2cm of some contour points).
2. **Shrinkwrap order: all-NEAREST (NOT PROJECT-first)** — ⚠️ see Bug 5 before using PROJECT.
   All 4 rounds use `NEAREST_SURFACEPOINT`. Earlier versions used PROJECT-first to sink
   concave vertices, but this caused severe left/right asymmetry and was reverted. Concave
   features are handled by the dense contour anchors, NOT by PROJECT Shrinkwrap.

**Result**: same 0.0mm anchors, 95.7%<1mm (≈ v1), but visual QA shows sockets correctly
sunk, nose tip covered, lip penetration gone — **only when Shrinkwrap is all-NEAREST**.
With PROJECT-first, one side of the face distorts (see Bug 5). **Surface-distance metrics
do NOT distinguish v1 from v2** — the metrics are fooled by the KDTree sampling target
interior vertices (mouth/throat) as "nearest" to lip-region template vertices, so v1's lip
penetration reads as low distance. Visual QA is the only reliable gate for concave features.

### Bug 5 — PROJECT-mode Shrinkwrap causes left/right face asymmetry
**Symptom**: After v2 with PROJECT-first Shrinkwrap, the left face looks correct but the
right face is severely distorted — nose tip displaced, lower eyelid collapsed, mouth corner
stretched. Quantitatively: left/right eye Y-coordinate delta = 12.3mm, left/right lip
Z-delta = 8.3mm (should be <1mm for a symmetric fit).

**Root cause**: `PROJECT` mode (all axes, both directions) projects each template vertex
along ±X/±Y/±Z onto the target surface. On an asymmetric target surface (nose protrudes
more on one side, cheekbone height differs), this sends one side's vertices to the wrong
target surface (e.g., a right-eye vertex projects through the nose and lands on the left
nasal surface). `NEAREST_SURFACEPOINT` does not have this failure mode — it finds the
nearest surface point globally, which respects locality.

**Fix**: use `NEAREST_SURFACEPOINT` for ALL 4 Shrinkwrap rounds. Concave features (eye
sockets, lips) are handled by the dense contour anchors (Bug 4 fix), not by PROJECT mode.
After the PROJECT→NEAREST revert, left/right symmetry restored: eye Y-delta 0.9mm, lip
Z-delta 0.8mm.

**Lesson**: never use `PROJECT` Shrinkwrap on a face with any surface asymmetry. Always
quantify left/right symmetry post-fit (`scripts/diag_asymmetry.py` compares +X/-X vertex
Y and Z means in eye/nose/mouth regions; deltas >2mm indicate a problem). If concave
features misfit with all-NEAREST, the answer is MORE contour anchors, not PROJECT mode.

### Bug 6 — Eyebrow contour points have bad 2D→3D mappings
**Symptom**: the 20 brow contour points (right_brow + left_brow) have a Y-range of 21.7mm
within each group — some points map 25mm forward of the median, landing on the nose bridge
or forehead instead of the brow. These bad anchors pull the template's forehead/temporal
region out of place.

**Fix**: remove `right_brow` and `left_brow` from the `MP_CONTOURS` set entirely. The 12
core points already include `right_brow`/`left_brow` (single vertices), which is enough.
Also filter `nose_ala` to 9 points (remove mp278, mp280 which map to the cheek). Final
contour set: 81 points (32 eye + 40 lip + 9 nose-ala), yielding ~52 effective anchors.

**Lesson**: never trust surface-distance metrics alone for faces. Always render the
fit-overlay (grey target + red template wireframe) from front, side, and 3/4 views and
eyeball the eye sockets, nose, and lips before declaring a fit good.

## 2D→3D raycast math (reference)

```
NDC:        nx,ny = (px/w)*2-1, 1-(py/h)*2     # Y flipped: image top → camera +Y
cam-space:  ray_cam = (nx*tan(fov/2), ny*tan(fov/2), -1), normalized
world:      ray_world = cam.matrix_world.to_3x3() @ ray_cam
target-local origin: sm.inverted() @ cam_pos
target-local dir:    (sm.inverted().to_3x3() @ ray_world).normalized()
hit, loc, *_ = target.ray_cast(origin_local, dir_local, distance=2.0)
# fallback: retry -dir_local if forward misses
world_point = sm @ loc
```

## Coordinate conventions

- Blender world: Z up, Y front/back, X left/right.
- Scan `Scan_Head`: `rotation_euler.x ≈ 90°`; after rotation face → -Y, top → +Z.
- Template `MH_Head_01.obj`: originally face → +Z; apply 90° X to match scan.
- MediaPipe image: (0,0) top-left, x right, y down.
- NDC: x ∈ [-1,+1] left→right, y ∈ [-1,+1] down→up after flip.

## MediaPipe index → template landmark map (post-mirror-fix)

| Landmark | MediaPipe idx | Template vertex |
|----------|---------------|-----------------|
| nose_tip | 1 | 7883 |
| right_eye_inner | 133 | 4395 |
| right_eye_outer | 33 | 7219 |
| left_eye_inner | 362 | 2791 |
| left_eye_outer | 263 | 2772 |
| right_mouth_corner | 61 | 6600 |
| left_mouth_corner | 291 | 2299 |
| chin | 199 | 8023 |
| forehead | 10 | 7694 |
| nose_bridge | 6 | 7878 |
| right_brow | 105 | 4274 |
| left_brow | 334 | 72 |

(Template indices live in `template_landmarks.json` and are specific to `MH_Head_01.obj`;
re-run `detect_template_landmarks.py` if the template file changes.)

## Known limitations

- MediaPipe detects only front-facing faces; a head with no front face geometry fails.
- Geometric landmarks (ears/back/top) remain the weak point even with KDTree+extremum
  detection (ears 27–55mm, back 30mm, top 7mm) — acceptable because they're validation-only,
  not used in fitting. Ear error is dominated by template-vertex-index mismatch (the template's
  ear vertices don't correspond to the detected ear extremes), not detection error.
- Template topology is fixed (MetaHuman); extreme-proportion targets (children, non-human)
  fit poorly.
- No material transfer in the current pipeline.
- Overall surface fit on a 2.97M-vert scan target: mean 0.441mm, 94.7% within 1mm (vs
  0.265mm / 99.7% on the lower-res blend-resident Scan_Head). The higher vertex count means
  more surface micro-detail the template can't match; 94.7%<1mm is the practical floor for
  this template density.
- **12-core-anchor variant (`scan_to_template_fit.py`) passes surface-distance metrics but
  FAILS visual QA on concave features**: eye sockets float (vertices wrap to the brow ridge
  instead of sinking in), nose tip/lip penetrate (Shrinkwrap pulls thin-wall vertices to the
  opposite lip's interior). Always render fit overlays and eyeball eye/nose/mouth before
  shipping. If the 12-anchor result shows these problems, escalate to the contour-anchor
  variant (`scan_to_template_fit_v2.py`) — see Bug 4 and the Contour-Anchor section below.

## MediaPipe contour index sets (for dense anchoring)

104 points across 7 groups. `left`/`right` are IMAGE-space (mirror) — idx 33 = person's right
eye, idx 263 = person's left eye, same convention as the 12 core points.

| Group | Count | Indices |
|-------|-------|---------|
| right_eye (person) | 16 | 33,7,163,144,145,153,154,155,133,173,157,158,159,160,161,246 |
| left_eye (person) | 16 | 362,382,381,380,374,373,390,249,263,466,388,387,386,385,384,398 |
| outer_lip | 20 | 61,185,40,39,37,0,267,269,270,409,291,375,321,405,314,17,84,181,91,146 |
| inner_lip | 20 | 78,191,80,81,82,13,312,311,310,415,308,324,318,402,317,14,87,178,88,95 |
| nose_ala | 11 | 49,131,134,51,3,248,281,278,279,280,440 |
| right_brow (person) | 10 | 70,63,105,66,107,55,65,52,53,46 |
| left_brow (person) | 10 | 300,293,334,296,336,285,295,282,283,276 |

These come from the canonical MediaPipe face mesh. To use: for each index, run the same
2D→3D raycast as the 12 core points, then find the nearest template vertex within 2cm
(KDTree on template verts). Template sparsity (8280 verts) means only ~45/104 match — that
is expected and still enough to pin the concave rims.

## v2 contour-anchor pipeline (scan_to_template_fit_v2.py)

1. Steps 1–3: same as v1 (6-view render, MediaPipe, 2D→3D for 12 core + 104 contour points).
2. Step 4: same centroid-align + scale (12 core points only — contour points are NOT used
   for centroid, only for anchoring).
3. **Step 4b (new)**: build a KDTree on the template's 8280 verts; for each contour 3D
   point, `kd.find` → nearest template vertex; if within 2cm, register as an anchor
   `(vert_idx, target_local_pos)`. Dedup (one vertex may match multiple contour points —
   keep the closest). Yields ~57 effective anchors.
4. **Step 5 (all-NEAREST, NOT PROJECT)**: Shrinkwrap ×4, all rounds = `NEAREST_SURFACEPOINT`.
   ⚠️ Do NOT use PROJECT mode — it causes left/right asymmetry (Bug 5). Concave features are
   handled by the contour anchors, not by Shrinkwrap mode. Each round + Corrective Smooth.
5. **Step 5b**: anchor iteration ×30 (up from 20 — more anchors need more iterations to
   settle without tearing). Same `alpha` ramp and Laplacian smooth as v1.
6. Step 5c: same surface correction + re-snap anchors.
7. Step 6: validate anchors (all 0.0mm) + KDTree surface distance + **render fit overlay**
   for visual QA.

**Match-rate gotcha**: outer_lip matches only ~8/20, nose_ala ~4/11, brows ~2/10 — the
template has no vertex within 2cm of many contour positions (lips are dense in MediaPipe,
sparse in MetaHuman). This is fine; the matched subset still covers the rim adequately. Do
NOT lower the 2cm threshold to force more matches — you'll grab wrong vertices from adjacent
features.

## Verification recipe

After running, open the output `.blend` and confirm:
1. 12 facial anchor vertices sit exactly on the target's eyes/nose/mouth/brow/chin.
2. **Render the fit overlay** (`render_verify.py` / `render_verify_v2.py`): grey target +
   red template wireframe, from front/side/3/4 views. Eyeball eye sockets (sunk in, not
   floating?), nose tip (covered, not penetrating?), lips (no cross-penetration?). This is
   the ONLY reliable gate for concave features — surface-distance metrics are fooled by
   target-interior vertices (mouth/throat) and will read low distance on penetrating lips.
3. Ear region: no obvious penetration or twist.
4. Back of head: natural draping.
5. If v1 (`scan_to_template_fit.py`) shows socket/lip/nose problems in the overlay, escalate
   to v2 (`scan_to_template_fit_v2.py`) — the contour anchors + PROJECT-first Shrinkwrap
   fix exactly these. Do not try to tune v1's Shrinkwrap parameters; the 12-anchor design
   cannot solve concave features.
6. Re-run KDTree surface-distance check if mesh was edited by hand.

## Adapting to a different target (e.g., Tripo instead of scan)

`mp_v2_final.py` currently opens `人头对齐_个人使用勿动.blend` and grabs `Scan_Head`. To
retarget a Tripo GLB: import the GLB, orient it (see sub-workflow A's orientation step), name
the object, and point the pipeline at it instead of `Scan_Head`. The landmark index file is
template-specific, not target-specific, so it carries over unchanged.

For OBJ targets already in Z-up / face-(-Y) orientation (e.g., `Scan_Head_Lv5.obj` exported
from Blender), use `scan_to_template_fit.py` instead — it imports the OBJ directly, centers
to origin, and skips rotation. **Verify orientation first** with a 6-view render + MediaPipe
probe (only the face-on view should detect 478 landmarks); if the best view is not `-Y` or
the model is Y-up, rotate before fitting. If v1's visual QA shows eye-socket/lip/nose
problems (concave features), switch to `scan_to_template_fit_v2.py` (contour anchors +
PROJECT-first Shrinkwrap) — see Bug 4 and the v2 section above.

## Picking v1 vs v2 (scan_to_template_fit vs _v2)

- **Start with v1** (`scan_to_template_fit.py`) — simpler, 12 anchors, fast.
- **Always render the fit overlay** after v1. If eye sockets are sunk, nose/lips clean →
  done, ship it.
- **Escalate to v2** (`scan_to_template_fit_v2.py`) only if the overlay shows socket float,
  nose/lip penetration. v2 is ~same runtime; the only cost is more anchors to settle.
- **Do NOT tune v1's Shrinkwrap parameters** to fix concave features — the 12-anchor design
  fundamentally cannot solve them. The fix is structural (more anchors + PROJECT-first), not
  a parameter tweak.

## Improved geometric landmark detection (replaces naive ray estimation)

`scan_to_template_fit.py` replaces the axis-aligned-ray geometric estimation with a
KDTree + local-extremum approach that dramatically improves the 9 non-facial landmark
positions (validation-only, still not used in alignment/anchoring):

| Landmark | Old (ray) error | New (KDTree+extremum) error | Method |
|----------|----------------|-----------------------------|--------|
| top_of_head | 113.7mm | 6.9mm | Z-max region center (top 3cm), exclude hair spikes |
| back_of_head | 184.6mm | 30.1mm | Y-max region center (back 3cm) |
| back_neck | — | 46.6mm | Y-max AND Z-min region (back-bottom intersection) |
| ears (6 pts) | 69–95mm | 27–55mm | Eye-Z height ±6cm, X-extremum side, 3 Z-strata (top/mid/bottom) |

Implementation: sample the target's vertices (~200K via step), build a KDTree, take the
local region around each axis extreme, and pick the centroid or X-outmost point within a
Z-stratum. These remain validation-only — the 12 MediaPipe facial points still drive
alignment and anchoring — but better geometric points make the validation report trustworthy
enough to spot real misalignments vs. detection noise.

## Blender 5.1 API quirks (background mode)

- `bpy.context.scene.display.shading.show_wire` raises `AttributeError` in 5.1 — wrap in
  `try/except`. The workbench wireframe toggle moved; use object color
  (`obj.color = (r,g,b,a)`) + `display.shading.color_type = 'OBJECT'` for overlay rendering
  instead.
- `--factory-startup` avoids slow addon loads (better_fbx, MACHIN3tools, B2RUVL) and their
  unrelated tracebacks. The `better_fbx` addon throws `ModuleNotFoundError: No module named
  'bpy_types'` on startup — harmless, but noisy; `--factory-startup` suppresses it.
- After `wm.obj_import`, the imported object keeps its OBJ `o` name (e.g.,
  `Male_Body_Morphs`), not a sanitized name. Set `obj.name = "Scan_Head"` explicitly so
  downstream scripts and `bpy.data.objects.get("Scan_Head")` work.
- `wm.obj_import` on a ~500MB / 2.97M-vert OBJ takes ~4s; the full fit (import + 6 renders +
  MediaPipe + 4 Shrinkwrap + 20 anchor iters + validate) runs in ~3–5 min.
- `Object.ray_cast(origin, direction, distance=2.0)` — in Blender 5.1 the `distance` argument
  is **keyword-only**; passing it positionally raises `TypeError: required parameter "distance"
  to be a keyword argument`. Always use `distance=`. This bit the post-fit diagnostic probe
  (`diag_depth.py`) that checks whether eye-socket vertices are floating in front of the socket.

### Bug 7 — sys.argv doesn't pass custom args to Blender scripts
Blender's `--background --python script.py 4` does NOT pass `4` to the script via `sys.argv` —
Blender consumes it as a file to open (`ERROR Cannot read file "4"`). **Fix**: use an
environment variable instead — `AUTOCHECK_ROUNDS=4 blender --background --python script.py`,
read via `int(os.environ.get('AUTOCHECK_ROUNDS', '4'))`. This is the only reliable way to
parameterize a Blender background script without writing a temp config file.

### Bug 8 — json.dump crashes on Vector / numpy types
`json.dump` raises `TypeError: Object of type Vector is not JSON serializable` when the report
dict contains `mathutils.Vector` or `numpy.float64` values (e.g., anchor target positions,
distances from `kds.find`). **Fix**: coerce everything to `float()` before dumping —
`{k: float(v) for k, v in report.items()}` and `bool(passed)` for booleans. Do not store raw
Vector objects in any dict that will be JSON-serialized.

## Penetration detection is unreliable (do not gate on it)

The `auto_check_pipeline.py` penetration check (bmesh-normal-based raycast: shoot along
vertex normal 5mm forward; if no hit, shoot backward; backward hit = inside = penetration)
**gives 45–58% false-positive rates** on a known-good v2 fit. The bmesh vertex normals after
4 rounds of Shrinkwrap + Corrective Smooth are inconsistent (some point inward on concave
regions like eye sockets and lip creases), causing the backward-ray to "find" the target
surface even when the vertex is correctly on the outside.

**Do NOT use penetration rate as a pass/fail gate.** The reliable gates are:
1. Left/right symmetry deltas (eye Y <3mm, mouth Z <3mm) — catches PROJECT-mode damage.
2. Anchor max error (<0.5mm) — catches anchor drift.
3. Overall surface distance (mean <0.6mm, <1mm >95%) — catches gross misfit.
4. **Visual QA on rendered overlays** — the ONLY reliable gate for concave-feature
   penetration. Surface-distance metrics are fooled by target-interior vertices (mouth/throat)
   reading as "near" to lip-region template vertices.

If the auto-check loop fails ONLY on penetration rate while passing everything else, the fit
is likely good — deliver it with a note that penetration was not reliably measurable and the
user should visually confirm eye/lip/nose regions.

## Parameter tuning has a ceiling — don't expect iteration to fix structural issues

Four rounds of different parameters in `auto_check_pipeline.py` all produced nearly identical
metrics:

| Round | sw_rounds | anchor_rounds | smooth_factor | smooth_iters | mean (mm) | <1mm% |
|-------|-----------|---------------|---------------|-------------|-----------|-------|
| 1 | 4 | 30 | 0.15 | 2 | 0.444 | 94.4 |
| 2 | 6 | 40 | 0.12 | 3 | 0.442 | 94.7 |
| 3 | 5 | 35 | 0.20 | 2 | 0.442 | 94.4 |
| 4 | 6 | 50 | 0.10 | 3 | 0.444 | 94.7 |

Symmetry, anchor error, and ear distance were also flat across rounds. **Lesson**: once the
pipeline is structurally correct (all-NEAREST Shrinkwrap, contour anchors, correct orientation),
tuning Shrinkwrap rounds / anchor iterations / smooth factor yields diminishing returns within
±0.3mm. The remaining ~5.3% of vertices outside 1mm is a structural floor set by template
sparsity (8280 verts) vs target density (2.97M verts) — the template simply has no vertex to
pin in every surface micro-detail. To meaningfully improve beyond 94.7%<1mm, you'd need a
denser template or a different algorithm (e.g., quad-remesh the target and transfer
attributes), not parameter tuning.
