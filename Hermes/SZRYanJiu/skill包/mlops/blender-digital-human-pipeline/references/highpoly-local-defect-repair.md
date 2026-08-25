# High-Poly Local-Defect Repair Discipline (2026-08-04)

Hard-won lesson from a full day of failed bump/dent repairs on the Tripo T-pose high-poly. Read this BEFORE touching any user-flagged visual defect on a high-poly mesh.

## The failure pattern (do not repeat)

1. User flags a bump/dent/hole on the chest/belly in Blender GUI.
2. Agent builds a ring-reference push/smooth: for each defect vert, average a neighborhood and lerp the vert toward it.
3. New artifact appears (symmetric twin pits on both pectorals, belly dents).
4. Agent stacks another fix on top → more artifacts. Repeat 4+ times.
5. Revert to clean pipeline; original defect is still there because it was **original AI geometry**, not a repair-induced defect.

## Root causes of the new artifacts

- **2D projected distance for the reference ring**: using `sqrt((x-cx)²+(z-cz)²)` (XZ-plane) to collect the "normal surface" reference makes left and right pectorals overlap in projection. Each side's reference ring contains the other side's verts → both get pulled into symmetric pits. **Always use true 3D Euclidean distance** `sqrt((x-cx)²+(y-cy)²+(z-cz)²)`.
- **No diagnosis before repair**: the "defects" (collar-ridge thickness ~7.6mm above surround, chest wrinkle line) were present in the raw model and survive adhesion + QR unchanged. Smoothing them is fighting the source mesh.
- **Stacking repairs**: once a fix produces a new artifact, the only safe move is full revert to the clean pipeline (rotate → weld → non-manifold fix → overlap removal → adhesion → final weld), never another local patch.

## Correct procedure

1. **Diagnose against the raw model first.** Load raw GLB, apply the SAME rotation as the repaired mesh (coords must be in the same frame — a rotated-vs-unrotated KD-tree compare returns garbage ~50-90mm everywhere), build a KD-tree of raw verts, and for each vert in the flagged zone compute nearest-point distance. `raw_dist ≈ 0.2mm` (weld threshold) means untouched original geometry. `raw_dist >> 1mm` means a prior repair step moved it.
2. **Only repair if it is repair-induced.** Original AI geometry (clothing folds, collar thickness, chest wrinkles) should be left for QR — QR retopologizes it into clean quads. The 2026-08-04 run proved this: the chest "crack" the user flagged on the QR mesh was `raw_dist` 0.4-1.0mm from the raw high-poly, i.e. faithfully preserved source geometry.
3. **If you must push/smooth**: 3D-distance ring, inner radius ~15mm (excludes the defect itself), outer radius ~35-40mm, push toward ring average, strength ≤0.5, few iterations, then re-verify against raw. If minY stops improving across iterations, the feature is structural — stop.
4. **Verify with a render + the user's eyes.** Numeric minY improvement ≠ visual fix. The user checks in Blender GUI; their word over metrics.

## What actually worked in the pipeline

- Clean 01 pipeline (no sculpt, no Taubin, no global Laplacian): rotate (foot_score + nose protrusion) → adaptive remove_doubles → non-manifold fix → overlap-face removal (same-direction coplanar only; opposite-direction clothing-body layers are kept — deleting them tears holes) → adhesion pipeline → final weld. Result: chest/belly verts match raw within 0.2mm.
- Belly "hole" = 3,459 inward-facing normals in a small zone → local `normal_flip()` on just that zone fixed it (0 remaining, nm unchanged). Localized normal flips are safe; GLOBAL `normals_make_consistent` on 1.9M faces flips correct faces and is forbidden (see SKILL.md pitfalls).
- QR: 193万 tris → 141,923 faces, 100.0% quads, 283,836 tris-equivalent (≤300k), ~54s via headless xremesh. Non-manifold 4.
