# Eye socket: verification-render calibration, UV残留 root cause, rim sizing (v38–v41)

> Companion to `eye-socket-and-eyeball-integration.md`. Captures 2026-08-18~19 lessons that are
> independent of the socket-shape history: how to keep the VALIDATION path honest, and how UV
> residuals / margin inflation actually manifest. Search triggers: 白弧带 / 黑斑块 / 棋盘格 /
> UV=(0,0) / 验证渲染 / 迭代循环 / rim半径 / margin.

## A. Calibrate the verification render BEFORE judging the mesh (the 477-round lesson)
An auto-iteration loop (run pipeline → render → vision → repeat) ran 477 rounds with vision
reporting "黑斑块 + 白缝隙" every round. The mesh was fine (UV colors correct, 0 double geometry,
0 open/non-manifold edges). Root cause: **the verification render script had NO lights** — EEVEE
rendered near-black, vision could not see the socket, and kept hallucinating defects. Adding
three-point lighting + world/env is what finally made vision reports meaningful.

Rules:
- Before trusting ANY vision verdict, verify the render itself: scene has ≥1 light, a world/env
  with nonzero strength, and the material link is live (Image Texture → Principled BSDF Base Color).
  A dark/empty render poisons every downstream vision call — the loop looks "stuck" when the bug
  is in the validator, not the product.
- An auto-iteration loop that re-runs the SAME code with no parameter/code change is pure spin.
  Each round must inject a real edit, or stop. 477 identical rounds = zero progress.

## B. UV=(0,0) residual loops = white-arc band (distinct from the bm.verts.new() case)
`eye-socket-and-eyeball-integration.md` section H covers new vertices from `bm.verts.new()`
defaulting to UV=(0,0). This session found a SECOND, subtler cause: the UV-assignment pass only
covered faces with `center.y < fc.y < center.y + 0.02` (bowl interior). Faces on the FRONT side of
the eye center (eyelid residual skin, `fc.y < center.y`) were never touched — leaving **1651 (L) /
2044 (R) loops at UV=(0,0)**. On an 8K texture UV(0,0) = RGB(0.88,0.68,0.56) (bright), vs ~0.4
skin tone, so those loops rendered as a bright white arc along the opening rim = the "白弧带".

Fix: a pre-pass BEFORE the main UV assignment sweeping the whole socket region (dxz<25mm,
`|y−center.y|<15mm`) that overwrites any loop with `uv.length < 0.01` (≈(0,0)) to avg_uv. Fixed
10358 (L) / 10239 (R) loops in one shot.

Rule: after any UV-assignment change, verify COVERAGE, not just the mean. Check the loop UV
histogram for residual (0,0) or extreme (0/1) values — a correct-looking avg can hide thousands of
unassigned loops. The pipeline log line `u=[0.0000,1.0000] v=[0.0000,1.0000]` is the tell: some
loops sit exactly at texture corners.

## C. Input-inherent vs pipeline-introduced: render the INPUT model for comparison
When vision flags an artifact (white arc, flap, fold, seam), do NOT assume the pipeline caused it.
Render the INPUT model (`01_highpoly_repair.blend`) with the SAME lighting + camera and compare.
This session proved the white arc / lid fold / horizontal eyeball seam were all present in the
input model (open-eye painted scan) — inherent features, not pipeline defects. Also diff
face-center multisets between input and output to prove "no faces added/removed outside the
intended region".

Rule: "is this artifact my bug or the model's nature?" → render input vs output side by side.
Cheap, decisive, kills blind debugging.

## D. PIL luminance fallback when vision_analyze 503s (Gemini free-tier overload)
When Gemini vision returns HTTP 503 (overload), do not stall — quantify the render directly with PIL:
```python
a = np.array(Image.open(shot).convert("RGB"))
lum = a.mean(axis=2)
dark_pct   = (lum < 60).mean()*100   # black-patch detector
bright_pct = (lum > 200).mean()*100  # white-arc detector
rgb_mean   = a[cy-r:cy+r, cx-r:cx+r].mean(axis=(0,1))  # skin-tone check
```
This session used it to confirm: dark 0% (black patches gone), bright 8-15% (expected — the eye
fissure shows the background; eyeball not yet placed), skin RGB≈(197,153,134) normal. Same
PIL-pixel spirit as the red/blue annotation extraction in the parent doc, applied to luminance.

## E. rim radius: measure ring0 INSIDE the pipeline; margin params inflated the opening
Two measurement traps:
1. A post-hoc `check_rim.py` using a `dxz ∈ [10,25mm], |y−center.y|<3mm` vertex window MIXED IN
   brow/cheek skin vertices (false "24mm" outliers). The accurate way is to measure ring0 (the
   open-boundary ring) inside `make_eye_cup` while it still exists — after the bowl seals the hole
   there are no open edges left to walk. Add a `rim半径: [min,max]mm avg=` print right after the
   Laplace relax.
2. `load_eyelid_contour` margins (margin_x=2, outer_extra=4, inner_extra=1.5, margin_z=1) inflated
   the opening from the true 3DDFA fissure (26.8×9.7mm → ~13.4mm half-width) to a 15-19mm rim.
   Setting all four to 0 shrank the rim to 3.9-12mm (avg 8.3mm), matching the almond fissure.
   **User rejected zero margin** ("开口并不符合眼睑") — the rim became too tight, losing the
   chamfer band's transition room and making the opening visibly mismatched to the eyelid.
   **Correct value is intermediate** — try margin_x=1.0, outer_extra=2.0 (half of original)
   rather than zero. Record the user's preferred mm value after GUI review.

Rule: rim/opening size must be measured against the 3DDFA contour data
(`eyelid_contour.json` has width_mm/height_mm), not eyeballed. Margins are per-model knobs; record
the actual width/height mm at each value.

## F. better_fbx `ModuleNotFoundError: No module named 'bpy_types'` is HARMLESS
Every headless `blender.exe --background --python ...` run prints a `bpy_types`
ModuleNotFoundError from the Better FBX addon failing to register. It is noise, not a failure
signal — the script runs to completion (exit 0) regardless. Do not treat it as an error or try to
"fix" it.

## G. Diagnostic scripts must validate their OWN units (the false-alarm lesson)
`diagnose_geometry2.py` reported "大量 +Y 面" because it treated xz coordinates (meters) as mm,
miscategorizing the region and producing a false alarm. The actual file had only L=3 / R=0 +Y faces.
Lesson: a diagnostic script is itself code — sanity-check its units and thresholds before trusting
its output to declare a product bug.

## H. User screenshot attachments: check file size before calling vision
When the user pastes a screenshot into Hermes, the composer may save a **placeholder stub** (an 8KB
PNG containing only the text `[response interrupted]`) instead of the real screenshot — e.g. when
the user's actual paste raced a response interruption. vision_analyze on the stub "succeeds" and
describes the stub text, so you burn retries analyzing the wrong image.

Rule: before vision_analyze on a user-attached screenshot, `ls -la` the file. A real Blender GUI
screenshot is typically 200KB-2MB; anything <20KB is suspect. If suspicious, list the
composer-images directory and pick the largest recent PNG — the real screenshot is usually there
under a slightly earlier timestamp.
