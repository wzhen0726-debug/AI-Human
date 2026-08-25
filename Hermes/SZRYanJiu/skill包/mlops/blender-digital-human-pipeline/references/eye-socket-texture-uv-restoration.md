# Eye Socket Rim Fitting & Texture-Eye UV Restoration (v41–v43, 2026-08-19/20)

> Continues `eye-socket-and-eyeball-integration.md`. Covers: shrinking the rim to the real eyelid contour, ring0 relaxation tuning, radial contour projection, and restoring the painted eye details (lashes/iris/pupil) from the texture onto the rebuilt bowl. Search triggers: 睫毛 / 眼睛细节丢了 / rim 不贴眼睑 / 暗环 / 眼窝UV / avg_uv / 贴图眼睛.

## Key insight: on painted-eye models the texture IS the eye
Tripo-class models paint the whole eye (lashes, eyeliner, iris, pupil, socket shadow) into the basecolor texture. Confirmed by cropping the eye-region UV block and vision-checking it (26% dark pixels = lash strokes). Consequences:
- Deleting the eye-region faces (`make_eye_socket` flood-fill) deletes the ONLY geometry whose UVs point at the painted eye.
- Giving the rebuilt bowl a uniform `avg_uv` (single skin-color point) erases all of it → user sees "眼睛里是肉色皮肤、没有睫毛".
- Conversely, dark samples around the rim are often MISPLACED LASHES, not errors — see the v42b caution below before filtering anything "dark".

## v41: rim must match the real eyelid contour (margin → 0)
The 3DDFA almond contour (26.8×9.7mm) is loaded with margin params (`margin_x_mm`, `margin_z_mm`, `outer_extra_mm`, `inner_extra_mm`) that inflate it. Original margins (+6mm total) made the rim 15–19mm vs the true fissure 6.5–13.8mm radius. Fix: drive margins to 0 so rim ≈ contour (avg 8.3–8.7mm).
- **Measurement rule**: rim radius can ONLY be measured inside `make_eye_cup` while ring0 exists (print it there). Post-hoc measurement fails two ways: skin-vertex sampling contaminates with brow/cheek verts (24mm outliers); open-edge ring finding fails because the bowl seals the hole (no open edges). Two diagnostic scripts were wasted before this was established.
- If the zero-margin opening proves too small for the eyeball later, fall back to margin_x=1mm — one-line revert.

## v42: ring0 relaxation + radial projection back onto the contour
Two knobs, both needed:
1. **Laplace relaxation sweep on ring0**: 0 iterations = starburst topology collapse (verts tunnel to center, mesh tears); 12 iterations × weight 0.3 is the plateau (jump avg 0.44mm; 3/6/9 show diminishing returns). Relaxation alone shrinks/distorts the ring off the contour.
2. **Radial projection back onto the 3DDFA contour**: after relaxation, each ring0 vert keeps its own angle θ, radius set to r(θ) from a densely-sampled (16 pts/segment) angle→radius interpolation table of the contour.
- **Failed approach**: nearest-contour-POINT projection clusters multiple verts onto the same discrete point → jump max 6.8mm (worse than before). Always project radially by angle, never snap to discrete points.
- End state: rim L avg 8.7mm / R avg 8.6mm, jump avg ~0.5mm, still wrong=0.

## v42b caution: "filter dark UV samples" was partly the WRONG direction
The lower-lid dark-patch "fix" sampled skin UVs from the lower-lid zone and discarded samples whose texture brightness < 0.40. That removed genuine dark patches, BUT a later diagnosis showed many of those dark samples were the painted lashes/eyeliner mapped to the wrong place — the real fix was restoring correct mapping (v43), not filtering. **Rule: before discarding "bad" UV samples, verify what they actually sample in the texture.** A dark sample may be correct content at the wrong position.

## v42b rendering pitfalls (validation infrastructure)
- **Workbench `shading.light='STUDIO'` affects only the viewport, NOT render output.** A Workbench/scene-without-lights render comes out 68–77% dark pixels. For verification renders use EEVEE + explicit lights + world background.
- **AREA vs SUN light energy units differ**: AREA 120/40/60 looks correct; the SAME numbers on SUN lights blow the image out (forehead pure white). Copy the validated recipe verbatim: three AREA lights (Key 120 at (0,-1,0.5), Fill 40 at (0.5,0.3,0), Rim 60 at (0,1,0.3), each aimed at face center via `look.to_track_quat('-Z','Y')`) + world Background Color (0.6,0.6,0.6) Strength 0.8 (setting only Strength without Color leaves a black background).
- Vision judgment of eye protrusion from a side view is unreliable (reported "蛙眼/exophthalmos" while quantitative depth was normal). For protrusion, measure world coords: cornea front pole y vs brow-front-most y / cheek-front-most y. On this model cornea sat 16mm BEHIND the brow front = normal socket depth.

## v43: restoring the painted eye onto the bowl (capture-before-delete + IDW grid)
Working recipe (validated: bowl center samples pupil dark 0.09, brightening outward; lashes reappear):
1. **Before** `bmesh.ops.delete` of the eye-region faces, capture every loop's `(dx, dz, u, v)` from faces to be deleted (filter 0.01<uv<0.99). ~1200 samples per eye. Store in a module-level dict keyed by side (index invalidation + mode switches make passing objects fragile; coordinate-snapshot pattern, same lesson as ring0_coords).
2. In `make_eye_cup`, build a 40×40 IDW lookup grid over ±16mm: for each grid node, weights = 1/(dist²+1e-10) over all samples, gridU/gridV = weighted mean. Bilinear interpolation at lookup.
3. Assign bowl faces' loop UVs from `lookup(fc.x-cx, fc.z-cz)` instead of avg_uv. Chamfer band (15–18mm) keeps nearest skin-UV inheritance.
- This works because the painted eye is a function of XZ position — the rebuilt bowl occupies the same XZ region, so XZ→UV back-mapping recovers lashes at the lid margin, iris toward the center.

## v43b: lookup-grid clamping bug = dark smudge ring around the eye
First version applied the grid to ALL faces with dxz<21mm, but the grid only covers ±16mm. Faces at 18–21mm (original CHEEK skin) got clamped to the grid's dark edge values → a dark arc "下睫毛印在脸颊" (dxz 18–20mm brightness 0.28 vs 0.43 normal).
Fix — zone the assignment explicitly:
- dxz ≤ 12mm (bowl body = rim 8.7 + chamfer 3): eye-texture grid mapping
- 12–15mm: clean skin avg_uv
- 15–18mm: chamfer band, skin-UV inheritance
- >18mm: ORIGINAL skin UV untouched (never overwrite)
Re-measured: 18–20mm band back to 0.41/0.42 brightness, ring gone, cheek clean.
- **General rule**: any position→value lookup table must have its APPLICATION domain no wider than its BUILD domain; clamping a grid silently smears edge values into regions that should never be touched. Zone the assignment explicitly; never let a fallback branch overwrite geometry that should keep its original data.

## Diagnostic pattern that broke the case open: dxz-bucketed UV-sampled brightness
To localize a UV anomaly around the eye, bucket faces by dxz (2mm buckets), average their loop UVs, sample the texture at that UV, and print per-bucket RGB/brightness. One run shows the whole radial profile: pupil-dark center → brightening skin → (bug) dark ring at 18–20mm → normal cheek. Replaces vision-guessing for "where is the UV error". Same shape as the earlier face-center-multiset diff trick, applied to UV space.

## Eyeball re-fit after rim changes
After the rim/eye-socket geometry changed (v42), the old `EYE_PUSH_BACK=0.022` (tuned on the pre-v42 socket) left the ball slightly proud; bump to 0.0235 (+1.5mm back) and vision confirmed the improvement. **Rule: any time socket geometry changes, re-tune eyeball knobs — they are anchored to socket measurements, not absolute truths.** Also re-run `run_eyeball.py` after every `run_eye_socket.py` change before verifying.

## Remaining open items (session-end state)
- Bowl still shows stretched bands at the lower lid / outer canthus in vision checks (IDW smoothing blurs fine lash strokes; a direct per-vertex nearest-sample or higher-res grid may sharpen — untested).
- The MetaHuman eyeball is a simple gray iris disc in these renders; lash visibility in final composites depends on the 0.5–1mm rim margin around the ball.
- User's annotated screenshots repeatedly failed to land on disk (composer-images missing the file) — when vision_analyze returns `media file not found`, check the path with ls FIRST and ask the user to re-attach instead of re-calling vision on the same missing path.
