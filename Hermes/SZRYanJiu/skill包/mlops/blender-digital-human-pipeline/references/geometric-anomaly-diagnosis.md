# Geometric anomaly diagnosis: original-vs-repair comparison

**Rule**: any local anomaly (bump, dent, uneven patch) on the repaired high-poly must be classified BEFORE any fix: is it repair-introduced or original-inherent? The classifier is a front-surface heightfield comparison between the repaired model and the RAW model.

## Why
Blind smoothing/flattening/Laplacian on an unclassified anomaly has produced new deformations (symmetric double-pits) worse than the original defect. If the anomaly exists in the raw AI mesh, the repair pipeline is NOT allowed to "fix" it without explicit user confirmation — it is a feature of the asset, not a bug.

## Recipe (Blender background)
1. Load RAW glb → run the same rotation-correction (`repair.rotate_to_standard`) → transform_apply, so both models share the standard orientation (Z-up, -Y forward, T-pose).
2. Load the repaired 01 blend.
3. Build a **front-surface heightfield** over the suspect bounding box on each model:
   - grid: `X0..X1, Z0..Z1`, cell ≈ 4mm
   - per cell keep the most-outer vertex (`min Y`, since front faces -Y)
4. Print a deviation map relative to the **border ring average** of the region (the ring excludes the suspected feature itself): `+` = >3mm raised, `=` >1.5mm, `.` flat, `,`/- = dents.
5. Per-cell compare raw vs repaired: `diff = |Y_raw(cell) - Y_repair(cell)|`.

## Interpretation
- `max/avg diff` sub-mm (observed: max 0.73mm, avg 0.03mm over 1200 cells) → **original-inherent**, repair did not cause it. Stop repairing; report to user.
- diff concentrated only inside the anomaly region → repair-introduced; locate the exact cells/verts, then design a targeted fix.

## Verification after any geometric fix
- Count verts deviating >1mm from the original OUTSIDE the target region → must be 0.
- Render the region and confirm with vision (vision_analyze), never bbox numbers alone.

## Pitfalls
- XZ-plane distance for ring/reference selection mixes left/right features (e.g. left+right pecs) and pulls healthy surface into symmetric artifacts. Use 3D Euclidean distance for reference-region selection.
- One wide smoothing pass hides the cause. Use small bounded regions + small steps + compare-to-original after each step.
