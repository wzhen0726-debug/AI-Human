# QR Rim Sharpness at Eye Sockets — Why Guide Curves and Sharp-Edge Marking Both Fail

> Date: 2026-08-24. Session: QR re-run on eye-socket high-poly + rim sharpening attempts.

## The problem

User feedback: "低模上的眼窝交界处不够锐利" — after QR, the eyelid rim (eye socket edge) looks
soft/rounded instead of crisp. Quantitative check confirmed: QR rim band deviation
(mean 0.19-0.25mm, max 1.4mm) is small in absolute terms, but the **visual impression** is still
"dull" because the rim is where the eye meets the face — any softness there reads as "staring".

## What was tried and FAILED

### 1. QR GuidesFile (guide curves) — NO measurable improvement

Added `GuidesFile="path/to/rim_guides.fbx"` to RetopoSettings.txt and re-ran QR (52s, same face count).
Result: rim deviation essentially unchanged (L: 0.192→0.192mm mean; R: max 1.0→1.4mm — slightly worse).
Guide curves do not force quad alignment at the rim in any useful way for this geometry.

**Root cause**: QR treats guide curves as soft hints, not hard constraints. With 14万 quads
spread over a full head, the eye rim gets ~19-32 vertices per side — not enough density for the
guide to bite.

### 2. Post-QR sharp-edge marking via bmesh — visually no effect

Marked 44 rim-adjacent edges as sharp (`e.smooth = False`) where adjacent-face normal angle > 12°.
Saved and rendered. Result: no visible difference — the quads are simply too large (mean rim-edge
length ~2.5-3mm) for sharp-edge flags to create a visual crease.

**Root cause**: Sharp-edge rendering only splits normals; it cannot create geometry that isn't
there. With 3mm quads at the rim, the fold itself is undersampled — you can't sharpen what
doesn't exist geometrically.

## The real bottleneck: rim vertex density

Measured on QR output (02_qr_150k.blend, 14.3万 quads):
- Rim band (±3mm from rim contour): L=19 vertices, R=32 vertices
- Rim faces are ~3mm edge length; eye opening height is ~12mm → only ~4 quad rows span the rim
- Eyelid front-most point shifts 0.7-1.0mm between high-poly and QR (within tolerance, but enough
  to blur the crease)

## FINAL SOLUTION (2026-08-24, vision-verified)

**Low-poly rim bevel (0.5mm) with edge weights — WORKS.**

After 5 failed approaches, the working solution is a post-QR Bevel modifier on rim-adjacent
edges with `limit_method='WEIGHT'` and per-edge `bevel_weight_edge` attributes:

1. Select rim edges with the **nearest-edge + tangent-filter method** — for each point of the
   rim contour (`eyelid_contour_manual.json`), take the closest edge (point-segment distance)
   within an adaptive threshold (0.4× local median edge length, floor 1mm), AND reject edges
   whose direction makes >35° with the local contour tangent. **Do NOT select by distance
   band alone** ("midpoint within 3mm"): the band catches 2-3 staggered rows of stray edges
   (measured 138), and distance-only nearest-edge still catches edges crossing the contour
   at 44-77° (measured 14 of 25). Distance+tangent leaves only edges that hug the lid margin
   (measured 14, all tangent <32°). Full analysis:
   `references/mixamo-rest-compensation-retarget.md` §2.
2. Set `bevel_weight_edge` attribute to 1.0 on selected edges, all others explicitly 0
   (see Blender 5.1 API note below; write attributes AFTER bm.to_mesh, never before)
3. Add Bevel modifier: `width=0.0005` (0.5mm), `segments=2`, `limit_method='WEIGHT'`
4. **Apply the modifier BEFORE UV unwrap** — UV ops rebuild the mesh and destroy
   edge attributes. Order: QR → rim bevel → apply bevel → UV → bake.
5. Verify per-edge, not by count: print each weighted edge's (length, distance to contour,
   tangent angle, hug/stray class) — the user inspects weighted edges in the GUI sidebar
   and will spot stray ones the totals hide.

Vision-verified result: rim edges sharp, folds clearly visible, dramatic improvement
over the "blurry smooth" version. Face count 143,308 → 143,717 after bevel application.

Script: `02QuadRemesher拓扑/scripts/rim_bevel.py`

### Why the other 5 approaches failed (quick reference)

| Approach | Result | Why it failed |
|---|---|---|
| Sharp-edge marking | No visual effect | 3mm quads too large; can't sharpen geometry that isn't there |
| Local subdivide (blind) | Topology destroyed | Subdivide produced slivers/triangles/poles — chaotic edge flow |
| QR MaterialIds boundary | Sharp but jagged | QR forced edge loops at material boundary → sawtooth artifacts |

> **补充（2026-09-09）**：MaterialIds 边界的"锯齿"根因是 **xremesh 非确定**——同参两跑结果差很多，
> QR 在 rim 环降采样时对材质归属随机。若目标是**材质分区贴 rim**（不是几何锐利度），
> 正解是 QR 后几何校正 rim 邻域面归属（与 xremesh 随机性解耦）。
> 眼窝碗面识别用 make_eye_cup 的 v44tag 拓扑标记（边界=rim），不用几何投影。
> 完整方法：`references/qr-eye-socket-material-partition.md`
| QR GuidesFile (curves) | No measurable change | Guides are WIP in QR 1.0 — not implemented as hard constraints |
| Rim ring + bridge | Sharp but unnatural | Ring floated on surface; bridge created harsh disconnected geometry |

### Normal-map-only (Option C) also tested — FAILED

Baking with increased ray distance (0.1) did NOT capture the rim crease — the normal map
stayed flat at the rim because the low-poly rim had no geometric fold to capture.
**Geometry must exist before normals can show it.**

## Recommendation for next session

**Use the rim bevel approach** (`rim_bevel.py`). It is the only verified working solution.
Do NOT retry GuidesFile, sharp-edge marking, blind subdivision, or material-ID boundaries —
all are proven dead ends for eyelid rim sharpness.

## Verification script

`scripts/compare_lid_front.py` measures eyelid front-most point (y) at eye-center z-height band
for both high-poly and QR output — use it to quantify any rim-sharpening attempt objectively.
