# AI Texture Color Bleed Fix

> Verified 2026-07-29 on Tripo AI high-poly (8192×8192 basecolor)

## Problem

Tripo AI high-poly textures have skin-colored pixels bleeding into clothing
regions — especially at collar, inner thighs, and cuffs. This is NOT a bake
ray-penetration issue; the high-poly texture itself is defective.

## Detection

Sample UV-mapped pixels at problem regions:

| Region | Z range | X range | Skin % | Clothing % |
|--------|---------|---------|--------|------------|
| Collar | 0.72-0.82 | <0.1 | 55.2% | 21.6% |
| Groin | 0.3-0.45 | <0.08 | 58.9% | 15.3% |

If >50% of sampled pixels in a clothing area are skin-colored, the texture
is defective.

## Fix Script (system Python, NOT Blender Python)

```python
import numpy as np
from PIL import Image
from scipy import ndimage

img = Image.open('highpoly_tex.png')
arr = np.array(img)

# 1. Identify clothing (dark pixels)
r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
dark_mask = (r < 0.15*255) & (g < 0.15*255) & (b < 0.15*255)

# 2. Dilate clothing region (include boundary transition)
dark_dilated = ndimage.binary_dilation(dark_mask, iterations=10)

# 3. Find skin pixels within dilated clothing zone
skin_mask = (r > 0.4*255) & (g > 0.25*255) & (b > 0.15*255) & (r > g)
bleed = skin_mask & dark_dilated

# 4. Get clothing mean color
dark_mean = np.mean(arr[dark_mask], axis=0).astype(np.uint8)

# 5. Replace all bleed pixels with clothing mean color
fixed = arr.copy()
fixed[bleed] = dark_mean

# 6. Smooth transition edges
from scipy.ndimage import gaussian_filter
transition = ndimage.binary_dilation(bleed, iterations=3) & ~bleed
for c in range(3):
    blurred = gaussian_filter(arr[:,:,c].astype(float), sigma=1)
    fixed[:,:,c] = np.where(transition, blurred.astype(np.uint8), fixed[:,:,c])

# 7. Save
Image.fromarray(fixed).save('highpoly_tex_fixed.png')
```

## Result

- Before: 229,644 bleed pixels in clothing zone
- After: 2,674 bleed pixels (98.8% reduction)

## Integration with bake pipeline

1. Run this fix on the high-poly texture BEFORE baking
2. Load the fixed texture into the high-poly material:
   ```python
   new_img = bpy.data.images.load('highpoly_tex_fixed.png')
   node.image = new_img
   ```
3. Bake normally with `cage_extrusion=0.005, max_ray_distance=0.01`

The small cage/ray values prevent any residual penetration, while the texture
fix eliminates the source of the skin-colored bleed.

## Reverse direction: dark clothing bleeding INTO skin — fix the BAKED diffuse

> Verified on a baked 4K diffuse (dark vest over skin; dark smudges on skin at
> collar / straps / cuffs).

Same defect class as above, opposite direction. Fix it on the baked PNG right
after the Diffuse bake, then `img.reload()` so the packed blend and the
embedded-FBX texture carry the fixed pixels. Do NOT treat it as a one-off
"fixed texture" file with an if-exists hook in the bake script — clean/fresh
re-runs lose it and the bleed comes back.

Judge (derive everything from the image itself, no hard-coded regions):

1. `empty` = near-zero pixels (unused UV space / margins) — excluded from all
   candidates.
2. Garment blob(s) = connected components of content pixels with luminance < 48
   passing a size floor, e.g. `max(largest * 0.15, dark_total * 0.005)`.
3. Candidate = `lum < 95` AND NOT inside any garment blob AND distance to the
   garment ≤ ~18 px AND not `empty`.
4. Replace candidates with the nearest skin color (distance-transform index of
   the skin mask) + a ~2 px Gaussian transition. Back up the file before
   writing.

Three traps (each cost a full round-trip):

- **Skin-fraction / window-majority judges reject the real bleed.** The bleed
  clings to the clothing edge, so a 40 px window there is ≈50% dark and any
  "mostly skin" test discards it (measured: 74 px detected vs ~13k actual).
  Trust luminance + distance-to-garment instead.
- **Excluding only an eroded "core" of the garment eats the garment's outer
  ring** — the replaced boundary band reads as jagged / moth-eaten in renders.
  Exclude the garment's FULL connected component.
- **The post-fix recount must reuse the same exclusions** (recompute the blob on
  the fixed image). Without the blob term it counts the entire garment and
  reports a bogus 7-digit "remaining" number.

Verification:

- Render the model with the original and the fixed texture from the same camera,
  then pixel-diff. Expect changes confined to the skin↔clothing boundary line
  (~0.2% of the frame); face, garment interior, and large areas must be zero-diff.
  Vision before/after descriptions contradicted each other on this — the diff is
  the objective judge.
- Scope is "light touch": facial features (brows/hair), garment interior, and
  anything far from the garment stay untouched.

## Locating the artifact (mesh space) and the "no visible change" follow-up

Texture space is the wrong frame for LOCATING or JUDGING this defect: UV islands
are scattered, so the texels behind a 3D smudge usually do NOT sit near the
garment's blob in the image; and a 3D region bounding box mixes skin and
garment faces, so its raw luminance percentiles prove nothing (a box over the
collar/chest reads mostly garment — "54% dark" is the vest itself, not bleed).
Cropping the texture around a 3D region's UV bbox is also useless — the bbox
covers most of the sheet. Sample the texture THROUGH the mesh instead; this
list is exactly what the user sees in the viewport:

1. Per-face UV-centroid sample: `img[(1-v)*H, u*W]`, luminance from RGB.
2. Classify: skin `lum > 105`, dark `lum < 80`, drop near-zero samples (UV-empty).
3. BFS connected dark clusters over face adjacency; a SMALL cluster (tens of
   faces) whose neighborhood is >60% skin faces is residual bleed — large
   clusters are the garment itself.
4. Report cluster face counts + 3D centroids. After a correct fix only a few
   tiny residues remain (verify against this list, not against texture crops).
   Script: `scripts/mesh_space_texture_residue_scan.py`.

When the user reports "no visible change / do I need to re-run?":

- Quantify first: replaced-texel count + render-diff %. On an already
  mostly-clean bake a CORRECT fix is objectively tiny (thin boundary band
  only) — state the numbers and what was checked; never imply a dramatic
  visual fix that the user can't see.
- Regenerated files on disk are NOT what an open Blender session shows — the
  app holds the old image/file in memory. The answer to "do I need to
  re-run?" is: no — reopen the file (or reload the image) to see it.
- If the user still sees a specific spot, ask for it, then sample that region
  in mesh space (steps 1-3) before widening the mask; their eyes are the
  acceptance criterion, but the mask must be tuned on measured face samples.

## v2: mesh-guided statistical spot cleanup (hands-off, no hard-coded thresholds)

> Verified 2026-09 on the same asset: dark red-brown spots on toes / hands /
> strap edges (2-6 mm), invisible to the boundary-band fix because they sit far
> from any garment.

Add this as a second stage after the boundary fix, in the same baked-diffuse
step (mesh is loaded in-scene; pass the low-poly to the function):

1. Per-face UV-centroid color → luminance. Neighborhood radius = 4 × median
   nearest-neighbor face-center distance (auto, tracks face density).
2. dev = face lum − median(neighborhood lum). Threshold =
   max(k·1.4826·MAD(|dev|), |dev| P99.5) — **both from the model's own data**.
   Never a fixed number: with the MAD term alone (σ≈1.7 on a heavy-tailed
   distribution) one gets thr≈7 and 379 noise "clusters"; with the percentile
   term it lands at the real defect scale (~40).
3. Dark side only (`dev < -thr`) catches dye/marking intrusions; the bright
   side is dominated by legitimate features (palms, nose highlights) — skip or
   gate separately.
4. Cluster the anomalies over the neighborhood graph, then GREEDY-SPLIT any
   cluster whose 3D diameter exceeds 2.5% of model height into sub-blocks
   (chains across toes/crevices fuse into one big cluster otherwise, and
   dropping whole clusters loses the fix). Face-count cap ≈ 0.15% of N.
5. Guards (all data-derived): skip faces above 80% of the bbox height (head:
   brows/lips/eyes are statistically identical to defects); require the
   cluster's own median color to lie OUTSIDE the skin color ellipse
   (Mahalanobis, mu/cov from the bright-warm faces) so darker-skin shading
   survives; require the neighborhood to contain ≥3 skin-ellipse faces.
6. Replacement = median color of the neighborhood's skin-eligible faces (NOT
   the whole neighborhood — defect clusters usually sit in toe clefts / along
   seams where the raw neighborhood median is dark). Fill each anomalous face's
   UV triangle by rasterization + ~2 px feather. Run the whole stage TWICE
   (second pass re-detects weaker spots now that neighbors were cleaned:
   feet residue 141→40→13 faces across passes).

Verify objectively: re-run the mesh-space residue scan (previous section) on the
fixed texture — the count of anomalous faces in the target region should drop
near zero — plus a render pixel-diff (face/garment interior must be zero-diff).

## Texture vs geometry: the flat-material discrimination render

When a reported line/spot shows no face-level texture anomaly in mesh space, do
NOT keep tuning texture masks — determine its nature instead: render the same
camera twice, once textured and once with every material slot swapped to a
plain white Principled BSDF. Artifacts that persist on the flat-white render are
GEOMETRY (seam ridges, shell overlaps, pinched toes) and cannot be fixed by any
texture stage — report them as geometry, don't silently ignore them. Artifacts
that vanish are texture-class and belong in this reference's pipeline. (Seen in
production: shorts-hem "dark seam / white line" = geometry-class; toe-tip
red-brown spots = texture-class.)
