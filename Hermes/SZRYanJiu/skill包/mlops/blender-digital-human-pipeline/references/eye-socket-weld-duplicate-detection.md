# Eye Socket Weld & Duplicate-Vertex Detection (v46i lessons)

Context: 01A眼窝管线 v46i — merged chamfer band + bowl into continuous rings, eye socket faces
live INSIDE the high-poly mesh object (not a separate object), so integrity checks must be
LOCAL (region around each eye center, ~30mm radius).

## False-positive duplicate detection (the trap)

Symptom: grid-hash duplicate check (round co to 0.1mm) reports dozens of "duplicate vertices"
at the bowl bottom; welding them destroys the pole fan.

Root cause math: the bowl's last ring shrinks to ~10% of rim radius. For rim avg radius 11.8mm
→ last ring ≈ 1.2mm radius, M=84 verts → **adjacent vertex spacing ≈ 2π·1.2/84 ≈ 0.09mm**.
A 0.1mm hash cell is LARGER than the spacing, so normal adjacent ring vertices collapse into
the same cell and get flagged as duplicates. R eye (M=74, slightly different radius) hit it too.

Diagnostic that disambiguates (pure measurement, NO welding):
- For each flagged pair print exact distance + radial distance from eye center + direction
  (radial vs tangential component of the connecting vector).
- Classification: dist < 0.02mm → true duplicate (weldable); dist > 0.05mm → adjacent ring
  vertex (NEVER weld). In v46i all "duplicates" 1-2mm from center measured 0.10-0.12mm →
  all adjacent ring verts. Real seam duplicates sit at the rim/chamfer outer edge
  (16-20mm from center in this model).
- Attribute blame via the `v44tag_<side>` face layer: pair touches a tagged face → new
  structure's fault; otherwise high-poly-native (pre-existing, not yours to fix).

Correct check implementation: `mathutils.kdtree.KDTree.find_range(co, 0.00001)` (0.01mm),
dedupe pairs with idx>i, report count + how many involve tagged faces + bowl pole fan health
(pole = vertex within 0.5mm radial of center at max depth; must link exactly M triangle fans).

## Weld rules

- Weld threshold MUST be < theoretical min adjacent spacing at the densest ring
  (2π·r_last/M). For this model: never above ~0.05mm; 0.0001 (0.1mm) is already too big at
  the bowl bottom. If the check used a coarse grid, its hit list is NOT a weld list.
- Local weld pattern: `bmesh.ops.remove_doubles(bm, verts=<region verts>, dist=...)` then
  `bm.to_mesh(me); me.update(); bpy.ops.wm.save_mainfile()`. NOTE: `bmesh.update_edit_mesh()`
  in OBJECT mode silently no-ops/errors — code after it never runs and the file is NOT saved
  (v46i lost a save this way; the log just ended with "Blender quit"). Always verify the
  blend file mtime after save, and re-open the saved file for the verification pass so you
  test on-disk data, not in-memory state.
- If a bad weld corrupts structure (pole fan count drops, e.g. 74→58 tris): do NOT try to
  re-weld smarter — re-run the pipeline to regenerate the eye socket cleanly, then re-check
  with the KD-tree method.

## Global-vs-local check scope

The output blend contains ONE mesh object (high-poly with eye socket faces merged in).
A whole-mesh integrity scan reports only the high-poly's pre-existing issues (e.g. ~48k
dup verts from Tripo import) and says nothing about the eye socket. Always scope checks to
the eye region and compare against tagged-face attribution.
