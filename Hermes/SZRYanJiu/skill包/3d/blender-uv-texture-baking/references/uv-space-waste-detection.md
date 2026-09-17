# UV space-waste detection + packed-parameter search

When a UV layout "looks wasteful" (a big contiguous blank area), don't eyeball it — measure, and
let the unwrap step fix itself. Every metric below is computed from the UV data; no model-specific
constants.

## Metrics (per layout)

- **Utilization U** = Σ |UV face area| / 1.0 (shoelace per face).
- **Largest empty square**: rasterize occupied cells (loop points + face centroids) on an analysis
  grid (256² worked at 161k faces), dilate ~2 cells to seal pinholes, then maximal-square DP over
  empty cells. Report side and area (normalized 0–1).
- **Island stats**: UV connectivity = faces sharing an edge whose END UVs match (<1e-6) → union-find.
  Gives island count, largest-island area/side, median island side.
- **Texel-density CV** = coefficient of variation of (UV area / 3D area) per face. smart_project
  with area_weight=0 already gives a baseline uniformity; re-packing must not degrade it.

## Waste criterion (self-referential, no tuned threshold)

`largest_empty_square_area ≥ largest_island_area` → the layout wasted a hole big enough to host the
biggest island. Measured: baseline 0.0566 vs island 0.0554 (flagged — and matches the hole a user
had independently complained about); every good candidate landed ≤0.10× the largest island. Clean
separation.

## The fix = bounded parameter search over the same islands

Smart UV Project's built-in packing leaves big gaps. `pack_islands(rotate=True, scale=True,
margin_method='SCALED', shape_method='CONCAVE')` re-packs the SAME islands much tighter
(measured 30.9% → 41–45% utilization) without touching island shapes (density CV unchanged).

Ladder: baseline (e.g. 66°, the project's seam decision) as-is, then baseline/75/82/89° each +
`average_islands_scale` + CONCAVE re-pack. Constraint: candidate density CV ≤ baseline CV; pick max
utilization among survivors; **re-run the winner once** so the mesh is left in that state.

## Pitfalls

- Fewer/bigger islands is NOT automatically better: 89° raised utilization but doubled density CV
  (rejected by the constraint), and 82° measured WORSE utilization than 75° (fragmentation without
  benefit). Measure each candidate; never assume a direction.
- Blender's bundled Python has **no PIL**. Draw layout PNGs with numpy + a bpy image
  (`bpy.data.images.new` → set `pixels` → `filepath_raw` + `save()`); sample each edge at ~12
  points and set pixels — don't attempt per-pixel line drawing.
- Gate the stage on a printed DONE marker (Blender -b exits 0 even when the script dies).
