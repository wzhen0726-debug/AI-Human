# Flattening surface bumps on cloth-covered high-poly (harmonic fill)

Companion to `geometric-anomaly-diagnosis.md`: that doc classifies the anomaly
(repair-introduced vs original-inherent). This doc covers the actual flattening
step for **original-inherent** bumps on clothing that the user wants removed
(e.g. Tripo chest "人字形" bumps: 56×21mm + 50×23mm, ~2.7mm high, single-layer cloth).

## Winner: Laplace harmonic fill (validated 2026-08-04)

Idea: don't estimate a reference surface at all. Fix the mesh OUTSIDE an ellipse
around the bump (boundary condition), let the interior vertex heights solve
`y(v) = mean(y(neighbors))` (Laplace equation). The solution is the unique
smooth surface matching the chest's real curvature at the boundary — no plane,
no quadric, no median window to tune, so it cannot carve natural curvature.

Three-step split is mandatory (Blender python lacks scipy; in-Blender Jacobi
timed out >600s on 965k verts):
1. `scripts/laplace_flatten_a_dump.py` — Blender: dump verts/edges + per-bump
   free-vertex sets to npz.
2. `scripts/laplace_flatten_b_solve.py` — SYSTEM python (scipy sparse `spsolve`):
   solve, save y per bump.
3. `scripts/laplace_flatten_c_apply.py` — Blender: apply, clamping outward pushes to 0.

### Critical: ellipse sizing
The free-region ellipse must extend **>=12-15mm past the bump footprint in all
directions** (bump #5 was 56×21mm → ellipses 112×68 / 108×70mm). If the boundary
ring crosses the bump's slope, the fill inherits the slope and residual height
remains. Sequence that showed this: ellipse=bump+3mm → 3mm residual; +12mm →
residual dropped sharply. When in doubt, go bigger (boundary on flat chest).
Aligned ellipses: get long-axis angle from PCA of the bump mask in the heightfield.

## Dead ends (do NOT retry — each tested 2026-08-04)
- **Flat plane fit to a ring** (35-55mm annulus, least squares): pushes max 12.4mm
  vs true bump 2.7mm → carved a −9.15mm dent. Chest curvature is not a plane.
- **Quadric (6-term) fit to annulus**: fit residual std 3.7mm, edge error 7.7mm —
  chest curvature is not quadric either.
- **Median-window push** (42/62/122mm kernels): kernels comparable to bump size get
  CONTAMINATED by the bump at the apex (pushes edges but not center → 3mm residual);
  large kernels still carve curvature. Median residual maps are also unreliable as a
  AFTER-metric (the median itself drops when the bump is removed → residual looks worse).
- **Cosine-radial falloff weighting**: wrong shape for ELONGATED bumps — falloff
  reaches 0 at the bump's long-axis tips. Weight by excess or use the ellipse mask.
- **Excess-based push + ring-fit reference**: "12mm bump" measured from a distant
  ring is mostly natural chest convexity, not defect. Don't trust large-ring references.

## Known residual artifact (unresolved, be honest about it)
After harmonic fill the bump volume is gone (vision-confirmed, no pits), but a
**high-frequency wrinkle ring** remains visible at the ellipse boundary under soft
lighting: inside is harmonic-smooth, outside keeps natural cloth wrinkles — a
frequency mismatch the eye reads as a "patch". Mitigations tried (feather band
smoothing λ=0.45/40it, Taubin 60 passes, outside-band transition smoothing):
reduced but did NOT eliminate it. Likely acceptable for downstream QR retopo +
baking (QR rewires topology), but flag it for the user's GUI check.

## Verification protocol
- Vertex diff vs pre-flatten model: verts with >1mm deviation OUTSIDE the target
  ellipses must be 0.
- Non-manifold / flipped normals: must not increase vs pre-flatten (the model may
  have pre-existing non-manifold edges — diff against baseline, expect 0 NEW).
- Render the region (Workbench, material shading, camera on -Y axis, lens ~100)
  and judge with vision_analyze BEFORE/AFTER — numeric residuals alone misled us
  repeatedly this session.
