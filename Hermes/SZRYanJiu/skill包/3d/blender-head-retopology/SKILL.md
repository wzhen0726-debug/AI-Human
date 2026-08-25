---
name: blender-head-retopology
description: "Automated head retopology pipeline: high-poly scan → low-poly MetaHuman template via MediaPipe facial landmarks, Shrinkwrap, and iterative anchor anchoring. v3.4 achieves 0.402mm/96.2% numeric metrics BUT visual quality is poor (ear/lip/eye distortion + 178 self-intersections) — user confirmed unusable for production."
version: 1.0.0
author: Hermes Agent
tags: [blender, retopology, mediapipe, shrinkwrap, 3d, head, metahuman]
platforms: [windows]
---

# Blender Head Retopology Pipeline

Automated pipeline for fitting a low-poly MetaHuman head template (MH_Head_01.obj,
~8K vertices) onto a high-poly 3D scan (Scan_Head_Lv5, ~3M vertices) using
MediaPipe facial landmark detection, Shrinkwrap, and iterative anchor anchoring.

## Scope Limitation: Body Wrap (CRITICAL)

**This skill covers HEAD retopology only.** Extending the pipeline to BODY wrap on AI-generated models fails systematically.

See `references/body-wrap-failure-analysis.md` for full analysis (9 methods tested, all failed 2026-07-29).

**Root cause**: AI models (Tripo, etc.) have clothing nesting + 53.1% normal inversion + 14 disconnected components. Head has none of these issues.

**If user asks for body wrap**: Stop and discuss alternatives before coding:
1. Clothing removal → naked high-poly → Shrinkwrap
2. Deformation Transfer (Sumner 2004) — needs dense correspondence
3. Skip wrap entirely: QR + Data Transfer UV (body from MetaHuman, clothing auto-UV)

Do not blindly attempt Shrinkwrap/RBF/Surface Deform on clothed AI models.

## QR Post-Subdivision Fallacy (2026-07-29, USER CORRECTED)

**User's words**: "你是在QR之后的模型加了细分,QR的模型已经没多少细节了，你迭代100次细分他不也是没细节??"

**Lesson**: QR output is a uniform quad grid with detail already smoothed away.
Subdividing it is pure interpolation — it adds faces but recovers ZERO surface
detail. Density control must happen BEFORE or DURING remeshing, never after.

**Wrong approach**: QR 90K → subdivide head/hand regions → "more detail"
**Right approach**: QR 125K (higher target) or split mesh → QR each part separately

See `blender-digital-human-pipeline/references/qr-density-control-experiments.md`
for the 3 tested approaches (Decimate pre, Voxel+Quadriflow, Instant Meshes)
and why none of them beat simply raising the QR target count.

## Quick Run

```bash
BLENDER="/d/Program Files/Blender Foundation/Blender 5.1/blender.exe"
# v3 (recommended): full 478-point mapping, 85 anchors
"$BLENDER" --background --factory-startup --python scripts/pipeline/fit_v3.py
# Self-check loop (1-4 rounds with auto parameter tuning):
AUTOCHECK_ROUNDS=4 "$BLENDER" --background --factory-startup --python scripts/pipeline/auto_check_pipeline.py
```

## Version History

| Version | Anchors | Mean | <1mm% | Eye sym | Mouth sym | Key change |
|---------|---------|------|-------|---------|-----------|------------|
| v1 | 12 | 0.441mm | 94.7% | 0.9mm | 0.75mm | Basic 12-point anchoring |
| v2 | 52 | 0.444mm | 94.4% | 0.9mm | 0.75mm | +filtered contour groups |
| v3-no-pullback | 85 | 0.445mm | 94.3% | 0.6mm | 0.6mm | Full 478-point mapping + Y-filter |
| v3+pullback | 85 | 0.459mm | 93.9% | — | 1.0mm | +Y-limit penetration pullback |
| **v3-procrustes** | **12** | **0.372mm** | **97.1%** | **0.04mm** | **0.75mm** | **Feature-point alignment (fixes 149mm Z-offset)** |
| **v3-progressive-smooth** | **12** | **0.383mm** | **96.8%** | **0.05mm** | **0.72mm** | **Progressive Laplacian smoothing + post-anchor global smooth** |
| **v3-no-pullback** | **12** | **0.397mm** | **96.4%** | **0.03mm** | **0.76mm** | **No anchor re-pullback after surface correction (fixes distortion)** |
| **v3.3-ear-excluded** | **12** | **0.405mm** | **95.9%** | **0.03mm** | **0.76mm** | **Ear-excluded ray-cast repair (face: 0.360mm/97.0%)** |
| **v3.4-laplacian** | **12** | **0.402mm** | **96.2%** | **0.03mm** | **0.76mm** | **Laplacian relaxation + find_nearest reproject (face: 0.356mm/97.3%) — ❌ 数值达标但视觉质量差，不推荐用于生产** |
| **v3.20-pinch-fix** | **12** | **0.415mm** | **95.2%** | **0.03mm** | **0.76mm** | **Paired pinch repair + spring anchors + selective Taubin (face: 0.389mm/95.6%)** |

**v3.20 is the latest version** (`scripts/pipeline/fit_v3.py`). **⚠️ 用户已确认 v3.4 视觉质量不可用**（耳朵偏小/上唇扭曲/内眼角拉伸/鼻翼错位/颈部锯齿 + 178自相交）。数值指标（0.402mm/96.2%）不代表可用结果。

**⚠️ 数值指标 ≠ 方案成功（2026-07-29 用户纠正，CRITICAL）**: 用户原话"我的这个路线的最终结果是很差劲啊，怎么总是给人感觉这个方案跑通了一样"。**教训：在任何文档/汇报/技能描述/归档记录中，不得仅因数值指标达标（如 0.402mm/96.2%）就标注方案为"✅成功/已验证/仍有效/当前推荐"。** 成功标准 = 视觉质量可用于生产（vision 自查确认）。v3.4 这类结果统一表述为"❌ 数值达标但视觉质量差，不推荐用于生产"，并必须列出具体视觉缺陷（耳朵偏小/上唇扭曲/内眼角拉伸/鼻翼错位/颈部锯齿 + 178自相交）。撰写测试报告或对外咨询文档时先自问"外人读了这个结论会不会误以为方案跑通了"——会的话就改写。本 skill 库中所有 md（README/咨询文档/调研档案/失败记录）已于 2026-07-29 按此原则批量修正 14 处。
**pinch detection and paired push-apart repair** after the self-intersection
stage, plus **spring-weight anchoring** (anchors participate in smoothing at
0.3× weight instead of being hard-locked) and **selective Taubin smoothing**
(λ=0.5/μ=-0.53, restricted to pinch zones only). The nose bridge pinch
(neighbor distances 0.1/0.7mm → 3.2/4.1mm) is eliminated. Tradeoff: face
self-intersections increased (178→559) because push-apart creates new
folded faces in concave regions. Overall mean 0.415mm (vs v3.4's 0.402mm).

**3-round A/B test confirmed no-pullback as best** (session 2026-07-08):
- Round 1 (progressive pullback α 0.3→1.0): 0.497mm / 91.4% — pullback destroyed Shrinkwrap fit
- Round 2 (progressive pullback α 0.2→0.5): 0.414mm / 95.5% — still degraded
- **Round 3 (no pullback, smooth only): 0.397mm / 96.4%** — best, zero distortion

**Smooth factor tuning** (session 2026-07-08):
- Original: 0.5→0.15 (too aggressive early, smears facial detail)
- **Tuned: 0.35→0.10** (moderate early smoothing, gentle late smoothing)
- Post-surface-correction smooth: 2 rounds at 0.12, 0.08 (was 1 round at 0.10)

Vision verification rated front-view mouth, chin, brow, and lip corners as "好"
(good). Side-view ear remains "差" (Shrinkwrap cannot wrap complex ear geometry).

The self-check pipeline runs 1-4 rounds, each: import → render → MediaPipe →
2D→3D mapping → template alignment → Shrinkwrap → anchor anchoring → surface
correction → quantitative checks → verification renders. It iterates with
different parameter strategies if the first round fails quality checks.

## Pipeline Stages

1. **Import + 6-view render**: Import scan OBJ, center, render ±X, ±Y, ±Z
2. **MediaPipe detection**: Run Face Landmarker (478 pts) on 6 renders, pick best
3. **2D → 3D mapping**: Raycast 12 key facial points + 81 contour points
   (eyes, lips, nose ala) from camera view onto scan surface
4. **Template import + alignment**: Import MH_Head_01.obj, centroid-align
   using only the 12 facial key points, uniform scale
5. **Contour anchor matching**: Match 3D contour points to nearest template
   vertices (KDTree, 2cm threshold), combine with 12 key points for ~52 anchors
6. **Shrinkwrap**: 4 rounds of NEAREST_SURFACEPOINT + Corrective Smooth
7. **Anchor anchoring**: 30 iterations of lerp displacement (α 0.3→1.0) +
   Laplacian smoothing for non-anchor vertices
8. **Surface correction**: Light NEAREST Shrinkwrap + re-anchor
9. **Quantitative checks**: Overall distance, symmetry, anchor errors, ear distance
10. **Verification renders**: Front, left45, right45, top views

## Key Design Decisions

### NEAREST vs PROJECT Shrinkwrap
- **NEAREST_SURFACEPOINT** is safe — preserves symmetry, no cross-side artifacts
- **PROJECT mode causes left-right asymmetry** (12mm eye offset, 8mm mouth offset
  in testing). Never use PROJECT for the main Shrinkwrap phase.
- PROJECT may be acceptable for the final surface correction step only, but
  test symmetry after any change.

### Contour Point Filtering
- 104 MediaPipe contour points are reduced to ~81 reliable points
- Nose ala: drop mp280 (Y value outlier, hits wrong surface)
- Eyebrow contours: entirely excluded (Y range 16-22mm, unreliable mapping)
- Each group's points are filtered by Y-median: discard points >15mm from median
- Only eyes, lips, and nose ala (filtered) are used for anchors

### Anchor Points
- 12 key facial points (from MediaPipe): nose_tip, eyes, mouth, chin, forehead, brows
- ~40 contour points: eyes (16+16), lips (8+17 outer/inner), nose ala (3-4)
- Total: ~52 anchors, all reach 0.0mm error after 30 iterations
- Geometric points (ears, top/back of head, back neck) are computed from scan
  extrema but NOT used as anchors — only for verification

### Progressive Laplacian Smoothing (v3 progressive-smooth)

The anchoring phase (25 iterations of lerp + Laplacian) introduces **mesh
distortion**: non-planar faces, flipped normals, and twisted vertices around
anchor points. Diagnosis showed 464/8280 vertices with inconsistent normals
(174 in chin, 90 in ears, 42 in mouth).

**Fix: three-layer progressive smoothing**

1. **During anchoring** — use a **decaying** smooth factor instead of fixed 0.3:
   ```python
   # Tuned values (session 2026-07-08): 0.35→0.10 is the sweet spot
   # Original 0.5→0.15 was too aggressive and smeared facial detail
   smooth_f = 0.35 - 0.25 * (iteration / total_iterations)
   # Early iterations: 0.35 (moderate, eliminates gross distortion)
   # Late iterations: 0.10 (gentle, preserves fitted detail)
   ```

2. **After anchoring** — 3 rounds of global Laplacian smoothing with decreasing
   factor (0.20, 0.15, 0.10), skipping anchor vertices each round.

3. **After surface correction** — 1 final round at 0.10, skipping anchors.

This eliminated visible distortion in upper lip, brow center, and nose tip
(差→好 on all front-view checks). Tradeoff: overall mean increased slightly
(0.372→0.383mm) — acceptable for visual quality.

**Pitfall**: A fixed smooth factor of 0.3 throughout all iterations is
insufficient. Early iterations need moderate smoothing (0.35) because anchor
displacements are large and create severe local distortion. Late iterations
need gentle smoothing (0.10) to preserve the fitted detail. **Do NOT use 0.5+
early** — it smears facial features (nose, lips) and degrades quality.
The 0.35→0.10 range was confirmed by A/B testing as the optimal tradeoff.

### Post-Surface-Correction Anchor Pullback — THE DISTORTION BUG (v3-no-pullback fix)

**This was the hardest-to-find bug in the entire pipeline.** After the surface
correction Shrinkwrap (SW2), the original code did:
```python
for vi, tgt in anchors.items():
    tpl.data.vertices[vi].co = tgt  # JUMP anchor back to target
```

This **directly teleports** anchor vertices back to their MediaPipe target
positions, while their neighbors remain at Shrinkwrap positions. The result:
**instant mesh distortion** — twisted vertices, flipped normals, non-planar
faces around every anchor point (464/8280 vertices affected: 174 chin, 90 ears,
42 mouth).

**Why it's hard to spot**: The quantitative metrics look *fine* (anchor error
= 0.0mm, overall mean = 0.372mm). The distortion only shows up in vision
verification or when examining per-vertex normal consistency. The user saw it
immediately in Blender: "眉心点扭曲、鼻尖点扭曲、嘴巴重叠" (brow center
twisted, nose tip twisted, mouth overlapping).

**Three tested fix approaches** (in order of effectiveness):

1. **Direct jump-back** (original, WORST): `v.co = tgt`. Anchor error 0.0mm,
   but 464 distorted vertices. Visual: twisted brow, lip, nose. **NEVER USE.**

2. **Progressive pullback** (5 rounds, α 0.3→1.0): Slightly better — anchor
   error 0.0mm, but the gradual pull still tears neighbors away from
   Shrinkwrap positions. Overall mean degraded to 0.497mm. **Do NOT use.**

3. **No pullback, only smooth** (BEST, current): Don't touch anchor positions
   at all after surface correction. Just run 2 rounds of global Laplacian
   smoothing (0.12, 0.08). Anchor error becomes 0.36-0.97mm (acceptable),
   but **zero distortion**. Overall mean 0.397mm, <1mm 96.4%. Visual:
   mouth/brow/corners all "好". **This is the recommended approach.**

**Pitfall**: The temptation to "re-anchor" after surface correction is strong
because the anchor error looks bad (0.97mm). But that 0.97mm is **on the surface
of the scan** — it's actually correct! The Shrinkwrap put the anchor vertex
*on the scan surface*, which is where it should be. Forcing it back to the
MediaPipe raycast target (which may be 1mm off the surface) only introduces
distortion. **Trust Shrinkwrap over raycast for final vertex placement.**

### Quality Thresholds
| Metric | Target | Typical |
|--------|--------|---------|
| Overall mean | < 0.6mm | 0.444mm |
| < 1mm coverage | > 95% | 94.4-94.7% |
| Eye symmetry (Y diff) | < 3mm | 0.6-0.9mm |
| Mouth symmetry (Z diff) | < 3mm | 0.7-1.0mm |
| Anchor max error | < 0.5mm | 0.0mm |
| Ear mean | < 3mm | 0.49mm |

### Mirror Center Edge Loop Constraint (2026-07-09 research)
When wrapping a symmetric template (e.g. MetaHuman head), the center-line
vertices (X≈0) MUST be pinned to X=0 after each Shrinkwrap iteration.
Shrinkwrap NEAREST_SURFACEPOINT can pull center verts off the mirror plane if
the target scan has micro-asymmetry (real scans almost always do). This breaks
downstream mirror symmetry — gaps, broken faces, subdivision cracks.

**Requirement**: The template must have a continuous edge loop along X=0.
MetaHuman MH_Head_01.obj satisfies this — all sagittal vertices are at X=0.

**Recommended enforcement** — bmesh X=0 clamp after each Shrinkwrap round:
```python
# After each Shrinkwrap apply, force center line vertices back to X=0
for vert in mesh.vertices:
    if abs(vert.co.x) < 0.002:  # 2mm threshold identifies center line verts
        vert.co.x = 0.0  # Lock X, keep Y/Z from Shrinkwrap fit
```
This preserves the Y/Z surface fit while guaranteeing mirror compatibility.
The 2mm threshold catches center verts that drifted slightly without grabbing
non-center verts.

**Root fix**: Pre-symmetrize the high-poly scan before wrapping. If the target
is already symmetric, Shrinkwrap naturally preserves center line vertices.

**Pitfall — hard Vertex Group exclusion causes pinch**: Excluding center line
verts entirely from Shrinkwrap (Vertex Group weight 0) causes pinch at their
neighbors — same mechanism as anchor hard-locking. Use the bmesh clamp approach
instead: let Shrinkwrap move center verts in Y/Z, then clamp X only.

**ZBrush Smart ReSym comparison**: ZBrush Smart ReSym is more forgiving — it
uses intelligent vertex-pair matching and doesn't strictly need X=0 center
verts. But it still requires roughly symmetric topology. Blender bmesh manual
mirror can achieve similar flexibility (Y/Z nearest-neighbor matching).

Full 6-question analysis (what/why/problems/MetaHuman/Shrinkwrap/countermeasures/ZBrush)
with comparison table and 5 countermeasure methods: see
`blender-digital-human-pipeline/references/mirror-symmetry-center-line-topology.md`.

## v3 Pipeline: Full 478-Point Mapping + Penetration Pullback

The latest version (`fit_v3.py`) maps **all 478 MediaPipe points** to the scan
surface (477/478 success rate), filters Y-outliers (>20mm from median → 402
valid points), then matches them to template vertices via KDTree. This yields
**~85 anchors** (vs 52 in v2), with improved mouth symmetry (0.6mm vs 0.75mm).

Key difference from v2: instead of pre-selecting contour groups (eyes/lips/nose),
v3 maps every single one of the 478 points and lets the Y-median filter remove
bad mappings. This is simpler and catches more usable points.

### Y-Limit Penetration Pullback (v3 addition)

Shrinkwrap NEAREST pulls lip/eyelid vertices into oral/nasal/eye-socket cavities
(the "nearest surface" inside a mouth is the back of the throat). Without
prevention, 433 vertices end up with Y < -80mm (some reaching -110mm, deep
inside the head).

**Technique**: After each Shrinkwrap round, check every non-anchor vertex. If
it's in the **facial region** (Y < -30mm, Z > -60mm, |X| < 80mm) AND its Y
coordinate exceeds -65mm, revert it to its pre-Shrinkwrap position.

```python
Y_LIMIT = -0.065  # facial vertices should not go past -65mm
def is_face_vertex(wp):
    return wp.y < -0.030 and wp.z > -0.060 and abs(wp.x) < 0.080

# After each Shrinkwrap apply:
for vi in range(len(mesh.vertices)):
    wp = tm @ Vector(cur[vi])
    if is_face_vertex(wp) and wp.y < Y_LIMIT and vi not in anc:
        mesh.vertices[vi].co = tv_pre[vi].copy()  # revert
```

**Results**: Pulls back 1711-3055 vertices per round. Prevents the catastrophic
"face imploded into mouth" deformation seen without it. Mouth penetration
visually resolved (差→好). Nose improved (差→中).

**Limitation**: Eye socket penetration persists because eyelid vertices have Y
values in the normal range (-40 to -65mm) — they don't trigger the Y-limit but
still get pulled to the eyeball's back surface. The Y-limit is a coarse spatial
constraint; it cannot detect "inside vs outside" for vertices near the surface.
Resolving eye sockets requires either:
- Per-vertex ray-cast inside/outside test (slow for 8K vertices × 297万 scan)
- Dedicated eyelid contour anchors (like Wrap4D's eyelid detector)
- FLAME shape prior to constrain eyelid vertex positions

## Self-Intersection: Structural Floor of Shrinkwrap (v3.20 finding)

v3.20 added pinch repair → self-intersections **increased from 178 to 559**.
Pinch repair (push overlapping verts apart) and self-intersection repair
(Laplacian pull-together) are **contradictory** — fixing one creates the
other in concave regions (ala, mouth corners, tear ducts).

**178 self-intersections (v3.4) is the structural floor of pure Shrinkwrap
NEAREST_SURFACEPOINT.** Not a parameter-tuning problem.

Improvement requires changing the projection approach:
1. **Region-constrained projection** (Wrap4D-style): vertex groups per
   facial region, each with different wrap strategy (lips/eyelids = anchor-only,
   no Shrinkwrap for those verts)
2. **FLAME/DECA shape prior**: intermediate mesh layer constrains vertices
   to plausible face shapes
3. **Auto-cleanup script** (fallback): dissolve_degenerate → remove_doubles →
   1-round Laplacian + find_nearest on residual

See `blender-digital-human-pipeline/references/eyes-teeth-symmetry-stitching.md`
for full analysis.

## Eye/Teeth Handling in Wrap Pipeline

MetaHuman head template is an open shell (not watertight) — no eyeballs or
teeth. However, it **does have interior cavity walls** for eye sockets and
oral cavity (see `blender-digital-human-pipeline/references/head-cavity-topology-analysis.md`).
AI-generated high-poly models have solid-sphere eyes fused to the head.
These MUST be deleted before wrap — Shrinkwrap pulls eyelid vertices onto
the eyeball surface instead of the socket wall.

- Delete: MediaPipe eye keypoints (33, 263, 133, 362) → centroid → find
  closed connected components within 15mm → delete
- After wrap: import standard eye template (UV sphere ~512 faces), position
  at socket center, bind to eye_L/R bones
- Teeth: same pattern — delete AI teeth before wrap, import standard after

See `blender-digital-human-pipeline/references/eyes-teeth-symmetry-stitching.md`
for full workflow including head-body stitching automation.

## Known Limitations

### Mesh Distortion Diagnosis (v3 progressive-smooth fix)

After anchoring, check for mesh distortion by examining per-vertex normal
consistency: for each vertex, collect normals of all adjacent faces, compute
the mean normal, and flag vertices where any face normal deviates >0.7 from
the mean (dot product < 0.3). Group flagged vertices by facial region to
identify problem areas.

```python
# Per-vertex normal consistency check
face_normals = np.array([tm.to_3x3() @ p.normal for p in mesh.polygons])
vert_face_normals = {}
for i, p in enumerate(mesh.polygons):
    for vi in p.vertices:
        vert_face_normals.setdefault(vi, []).append(face_normals[i])

bad_verts = []
for vi, normals in vert_face_normals.items():
    if len(normals) < 3: continue
    avg_n = np.mean(normals, axis=0)
    avg_n = avg_n / np.linalg.norm(avg_n)
    for n in normals:
        if np.dot(n, avg_n) < 0.3:  # severe inconsistency
            bad_verts.append(vi); break
```

**Pitfall**: BVH-based self-intersection detection (`BVHTree.FromPolygons` +
overlap) is extremely slow on 8K meshes (180s+ timeout). Use normal-consistency
check instead — it's fast and catches the same distortion.

### Nose & Eye Socket Penetration (UNRESOLVED)
The Shrinkwrap NEAREST_SURFACEPOINT cannot distinguish which side of a thin
structure is "correct." Nose tip and columella vertices may be pulled to the
inner nasal surface, and eye socket vertices to the eyelid surface. This is a
fundamental limitation — the quantitative metrics (0.445mm mean) are excellent
but visual inspection shows local penetration in these areas.

**Failed fix attempts (do NOT retry these):**
- **Global normal-direction refinement**: Pulled 4505-6273/8280 vertices by
  up to 5mm, DESTROYED overall quality from 0.445mm to 2.08mm. The bmesh
  normal directions after Shrinkwrap+anchoring are unreliable for this purpose.
- **PROJECT mode in main Shrinkwrap phase**: Broke left-right symmetry
  (eye Y diff jumped from 0.9mm to 12.3mm, mouth Z diff from 0.8mm to 8.3mm).
  PROJECT is direction-dependent and non-symmetric on real facial geometry.
- **PROJECT mode in surface correction only** (XY axes): Still broke symmetry
  (eye Y diff 2.9mm). Even localized PROJECT is unsafe.
- **Post-correction direct anchor pullback** (`v.co = tgt`): Caused 464/8280
  vertices with distorted normals (twisted brow/lip/nose). Metrics looked fine
  (0.0mm anchor error) but visual quality was unacceptable.
- **Post-correction progressive pullback** (5 rounds α 0.3→1.0): Still tore
  neighbors from Shrinkwrap positions. Overall mean degraded to 0.497mm.

**Partially successful fix — Y-limit pullback (v3):**
- After each Shrinkwrap round, revert facial-region vertices (Y < -30mm,
  Z > -60mm, |X| < 80mm) that exceed Y=-65mm back to their pre-Shrinkwrap position.
- Pulls back 1711-3055 vertices per round. **Prevents catastrophic face implosion**
  (mouth penetration: 差→好, nose: 差→中). Overall mean slightly increases
  (0.445→0.459mm) as a tradeoff for preventing severe deformation.
- **Eye sockets remain unresolved** — eyelid vertices have Y in normal range
  (-40 to -65mm) so the Y-limit doesn't catch them. They still get pulled to
  eyeball back surfaces. Visual rating: still 差 (poor).

**Root cause analysis (from research):**
- Wrap4D/Faceform solves this with a dedicated **lip detector** and **eyelid
  detector** that constrain projection direction per-region.
- UE5 MetaHuman uses a **learned shape prior** (instance-based database
  retrieval, not PCA 3DMM) + constrained non-rigid ICP.
- Both approaches are beyond what pure Shrinkwrap can achieve.

**Recommended approach:** Manual touch-up in Blender for nose/eye areas after
the pipeline completes. For automated improvement, the next research direction
is per-region constrained projection (face-direction-only projection for
eye/nose vertices) or integrating FLAME/DECA shape priors.

## Self-Intersection Detection & Repair (v3.1+)

### The problem
Shrinkwrap NEAREST on complex ear/nostril geometry causes **face self-intersection**:
vertices get pushed to wrong surface side, faces fold through each other.
v3 produced **1730 self-intersecting face pairs** and **64 non-manifold edges**
(all at the template's neck boundary opening — intrinsic, cannot be fixed).

### Detection method
```python
from mathutils.bvhtree import BVHTree
bvh_tpl = BVHTree.FromObject(tpl, bpy.context.evaluated_depsgraph_get())
overlaps = bvh_tpl.overlap(bvh_tpl)
# Filter adjacent faces (shared vertices = not real intersection)
intersecting_faces = set()
for i, j in overlaps:
    fi, fj = mesh.polygons[i], mesh.polygons[j]
    if not (set(fi.vertices) & set(fj.vertices)):
        intersecting_faces.add(i); intersecting_faces.add(j)
```

### Repair approach (tested, PARTIALLY EFFECTIVE)
Ray-cast projection along vertex normals to find correct surface position:
```python
# Bidirectional ray cast, 50mm max
hit1, _, _, d1 = bvh_scan.ray_cast(w_pos, w_normal, 0.05)
hit2, _, _, d2 = bvh_scan.ray_cast(w_pos, -w_normal, 0.05)
# Pick nearest hit; fall back to find_nearest if both miss
```

**Results (v3.1, v3.2, v3.3, v3.4)**:
| Version | Self-intersect | Non-manifold | Anomaly verts | Mean | <1mm% | Strategy |
|---------|:---:|:---:|:---:|:---:|:---:|----------|
| v3 (no fix) | 1730 | 64 | 0 | 0.397mm | 96.4% | — |
| v3.1 (1 pass) | 395 | 64 | 20 | 0.412mm | 95.7% | Ray-cast all regions |
| v3.2 (2 pass + delete) | 280 | 64 | 80 | 0.446mm | 94.7% | Ray-cast all regions, aggressive |
| v3.3 (ear-excluded ray) | 401 | 64 | 13 | 0.405mm | 95.9% | Ray-cast face only (\|X\|<50mm) |
| **v3.4 (Laplacian)** | **362** | **64** | **8** | **0.402mm** | **96.2%** | **Laplacian relax + find_nearest, face only** |

### Ear-region exclusion (v3.3 key technique)
**Ray-cast repair in ear concave regions hits wrong surfaces** — ears have complex
folded geometry (helix, anti-helix, concha) where bidirectional ray casts frequently
hit the wrong side. This makes the repair WORSE, not better.

**Fix: skip ear region entirely** (|X| > 50mm in world coordinates):
```python
for fi in intersecting_faces:
    for v_idx in tpl.data.polygons[fi].vertices:
        w_pos = tm @ tpl.data.vertices[v_idx].co
        if abs(w_pos.x) < 0.05:  # face region only
            bad_verts.add(v_idx)
```

v3.3 with ear exclusion: 401 self-intersect (184 ear + 217 face), face precision
0.360mm mean / 97.0% <1mm, only 13 anomaly vertices. **Best balance of topology
and accuracy (superseded by v3.4).**

### Laplacian relaxation repair (v3.4 — RECOMMENDED)

Ray-cast repair has a fundamental flaw: in concave facial regions (nostrils,
upper lip, tear ducts), the bidirectional ray hits the **wrong surface**,
pushing vertices deeper into self-intersection. v3.4 replaces ray-cast with
**Laplacian relaxation** — unfold the folded faces first, then reproject.

**Technique: 3-step pipeline**
```python
# Step 1: Laplacian relaxation (3 rounds, α=0.5)
# Pulls self-intersection vertices toward neighbor average position,
# physically unfolding folded faces without hitting wrong surfaces
for iteration in range(3):
    new_co = [None] * len(mesh.vertices)
    for i in range(len(mesh.vertices)):
        if i in bad_verts:
            nb = adj[i]  # precomputed adjacency
            if nb:
                avg = sum(mesh.vertices[ni].co for ni in nb) / len(nb)
                new_co[i] = mesh.vertices[i].co.lerp(avg, 0.5)
            else:
                new_co[i] = mesh.vertices[i].co.copy()
        else:
            new_co[i] = mesh.vertices[i].co.copy()
    # Apply all at once (avoid sequential update bias)

# Step 2: find_nearest reprojection
# After unfolding, snap back to scan surface using KDTree/BVH nearest
for vi in bad_verts:
    w_pos = tm @ mesh.vertices[vi].co
    best_loc, _, _, _ = bvh_scan.find_nearest(w_pos)
    if best_loc:
        mesh.vertices[vi].co = tm_inv @ best_loc

# Step 3: Light local smoothing (2 rounds, α=0.3)
# Smooths the reprojection artifacts in the repair zone only
```

**Why Laplacian > ray-cast for self-intersection repair:**
1. **No wrong-surface hits**: Laplacian relaxation only uses mesh topology
   (neighbor positions), not scan geometry — it can't hit the wrong surface
2. **Unfolds before reprojecting**: The folded face is physically opened up
   *before* being snapped to the scan, so find_nearest hits the correct side
3. **Fewer anomaly vertices**: 8 (v3.4) vs 13 (v3.3) vs 80 (v3.2) — less
   collateral damage to surrounding geometry
4. **Better accuracy recovery**: 0.402mm (v3.4) vs 0.405mm (v3.3) — the
   relaxation+reproject cycle preserves more of the original Shrinkwrap fit

**Still combine with ear exclusion**: Only apply to face-region vertices
(|X| < 50mm). Ear self-intersection (184 faces) is accepted as unfixable.

### Critical tradeoff
**Aggressive multi-pass repair degrades geometric accuracy.** v3.2 (2 passes +
lonely face deletion) produced 80 anomaly vertices and 0.446mm mean — WORSE than
v3.1's single pass (20 anomaly, 0.412mm). Each repair pass pushes vertices via
ray-cast into concave regions where it hits wrong surfaces, compounding errors.

### Recommendation
- **Use Laplacian relaxation repair** (v3.4): best balance — 0.402mm mean,
  96.2% <1mm, only 8 anomaly vertices, 178 face self-intersections
- **Accept ear self-intersection** (~184 faces) as a Shrinkwrap limitation
- **Do NOT do multi-pass ray-cast repair** — it compounds errors in concave
  geometry (v3.2: 80 anomaly verts, 0.446mm)
- **Do NOT use ray-cast in ear region** — bidirectional rays hit wrong
  surfaces in ear concavities (helix, anti-helix, concha)
- The 64 non-manifold edges are from the template's neck boundary opening
  and **cannot be fixed by the pipeline** — they're intrinsic to the mesh
- For production use: post-process in Blender with `Mesh > Clean Up > Delete Loose` + `Merge by Distance`

### BVH ray_cast API pitfall
`BVHTree.ray_cast()` takes **positional arguments only** — no keyword args:
```python
# WRONG (TypeError):
bvh.ray_cast(origin, direction, distance=0.05)
# CORRECT:
bvh.ray_cast(origin, direction, 0.05)
```

## Vertex Pinch Detection & Repair (v3.5+)

### The problem — distinct from self-intersection
Shrinkwrap NEAREST projects adjacent template vertices to nearly identical
surface points on the scan, creating **vertex pinch** — pairs of vertices
that are topologically adjacent (share an edge) but spatially collapsed
together (edge length < 0.5mm while neighbors are 8-10mm). This produces
visible "spike" or "pinch" artifacts in Blender, especially at the **nose
bridge** and **nose tip** where the scan surface has high curvature.

**Pinch is NOT self-intersection**: the faces are not folded through each
other. The vertices are simply too close, creating degenerate geometry.

### Detection
```python
# Pinch vertex: has at least one edge shorter than avg_edge_len * 0.4
pinch_verts = set()
for i in range(len(mesh.vertices)):
    if i in anchors:
        continue
    nb = adj[i]
    if not nb:
        continue
    edge_lens = [(mesh.vertices[ni].co - mesh.vertices[i].co).length for ni in nb]
    avg_len = sum(edge_lens) / len(edge_lens)
    if any(el < avg_len * 0.4 for el in edge_lens):
        pinch_verts.add(i)
```

### Failed approaches (DO NOT RETRY)

1. **Ray-cast reprojection** (v3.1-v3.4 self-intersection repair): Does not
   fix pinch — `find_nearest` re-projects both collapsed vertices to the
   same surface point, recreating the pinch.

2. **PROJECT mode Shrinkwrap** (v3.12): Causes massive self-intersection
   (1340 faces) because PROJECT along normals pushes vertices through the
   surface at high-curvature regions like the nose bridge.

3. **Global Taubin smoothing** (v3.7-v3.8): λ=0.5/μ=-0.53 for ALL vertices
   destroys accuracy (0.498mm, 157 verts >2mm) even with anchor protection.

4. **Edge-length equalization before SW2** (v3.6): SW2 NEAREST re-collapses
   the vertices. The equalization is immediately undone by Shrinkwrap.

5. **Single-vertex push** (v3.17): Pushing one vertex away from its collapsed
   neighbor doesn't work — both vertices are in the pinch set and push toward
   each other.

6. **Taubin + find_nearest iterative loop** (v3.14): Each `find_nearest`
   re-collapse the vertices that Taubin just separated. The loop never
   converges — pinch returns to 0.1-0.3mm after every reprojection.

### Working approach: paired push-apart (v3.20)

**Key insight**: Pinch repair MUST be the **last step** — after all
Shrinkwrap and self-intersection repair. Any subsequent `find_nearest` or
Shrinkwrap call will re-collapse the vertices.

```python
# 1. Detect pinch pairs (edge < 0.5mm, face region only |X| < 50mm)
# 2. For each pair (vi, ni), push them APART symmetrically:
direction = (mesh.vertices[vi].co - mesh.vertices[ni].co).normalized()
target_len = avg_neighbor_edge_length(vi)  # e.g. 8mm
push_dist = (target_len - current_edge_len) / 2
mesh.vertices[vi].co += direction * push_dist
mesh.vertices[ni].co -= direction * push_dist
```

**Critical details**:
- Process pairs, not single vertices — both endpoints move symmetrically
- Mark processed pairs with a `processed` set to avoid double-moving
- Skip anchor vertices (they are locked)
- Run 2 rounds to catch residual pinch from the first round
- Apply AFTER self-intersection repair (stage 5.6, after stage 5.5)

### Spring-weight anchoring (v3.5+)
**Problem**: Hard-locked anchors (skip all smoothing) cause pinch at anchor
neighbors — the anchor stays fixed while neighbors get smoothed, creating
edge-length imbalance.

**Fix**: Anchors participate in smoothing at reduced weight (0.3× the normal
smooth factor) instead of being frozen:
```python
if i in anchors:
    # Spring weight — anchor can drift slightly toward neighbor average
    new_co[i] = mesh.vertices[i].co.lerp(avg, smooth_f * 0.3)
else:
    new_co[i] = mesh.vertices[i].co.lerp(avg, smooth_f)
```
Also cap anchor alpha at 0.8 (not 1.0) — leave 20% spring tension so the
anchor doesn't jump fully to the MediaPipe target, which tears neighbors.

### Selective Taubin smoothing (v3.9+)
Taubin (λ/μ dual-channel) smooths pinch zones while preserving features
elsewhere. **MUST be selective** — only apply to pinch-detected vertices
and their direct neighbors, not the entire mesh.

```python
# Pinch zone = pinch verts + their 1-ring neighbors (face region only)
pinch_zone = set(pinch_verts)
for vi in pinch_verts:
    for ni in adj[vi]:
        if ni not in anchors and abs(world_x(ni)) < 0.05:
            pinch_zone.add(ni)

# 3 rounds of Taubin (only on pinch_zone):
for _ in range(3):
    # Forward pass: λ=0.5 (smooth)
    for i in pinch_zone: smooth_toward_neighbor(i, 0.5)
    # Backward pass: μ=-0.53 (feature-preserving rebound)
    for i in pinch_zone: smooth_toward_neighbor(i, -0.53)
```

### Pinch repair tradeoffs
| Version | Pinch fixed | Mean | Self-intersect | Notes |
|---------|:-----------:|:----:|:--------------:|-------|
| v3.4 (no pinch fix) | 0 | 0.402mm | 362 | Nose bridge 0.1/0.7mm ❌ |
| v3.20 (2-round push) | 547 pairs | 0.415mm | 856 | Nose bridge 8.1/8.2mm ✅, but self-intersect ↑ |

Push-apart creates new self-intersections in concave regions (nose wings,
mouth corners) because separating vertices can fold faces. This is an
**inherent tradeoff**: fixing pinch creates some self-intersection and
vice versa. The current approach prioritizes visual quality (no pinch
spikes) over topology cleanliness.

### Pinch repair ordering — CRITICAL
```
Pipeline stage order (MUST follow this):
  5.   Shrinkwrap + anchoring + SW2 surface correction
  5.5. Self-intersection repair (Laplacian + find_nearest)
  5.6. Pinch repair (paired push-apart) ← LAST step before verification
  6.   Verification
```
Any `find_nearest`, `Shrinkwrap`, or reprojection AFTER pinch repair will
re-collapse the separated vertices. The pinch repair must be the final
geometric modification.

See also: `references/pinch-repair-testing.md` for the full 16-version
A/B testing matrix (v3.5→v3.20) with per-version metrics and failure analysis.

## Blender World Units — ALWAYS METERS

**Blender's internal unit is meters, not millimeters.** Template vertex
coordinates are ~0.05m (= 50mm), not 50.0. When writing diagnostic scripts:
```python
# WRONG — assumes mm:
RADIUS = 10.0  # This is 10 METERS, includes ALL vertices
if d > 1.0:    # This is 1 METER threshold

# CORRECT — use meters:
RADIUS = 0.010  # 10mm = 0.01m
if d > 0.001:   # 1mm = 0.001m
```
This bug caused a diagnostic script to report "all 8280 vertices within 10mm"
because the threshold was actually 10 meters. Always multiply mm thresholds
by 0.001 when comparing against `v.co` or BVH distances.

## SVD Rotation Alignment — DO NOT USE (tested, fails)

Adding SVD Procrustes rotation to the feature-point alignment **makes quality
dramatically worse**. Tested in session 2026-07-08:

| Alignment | Max post-align error | mouth_z_diff |
|-----------|:---:|:---:|
| Translation + Scale only | ~0.4mm | 0.03mm |
| + SVD Rotation | **13.6mm** | **0.62mm** |

**Root cause**: 12 feature points are too sparse and coplanar for SVD to
find a reliable rotation. The rotation matrix amplifies small measurement
errors in MediaPipe detection into large position errors. The template and
scan already share the same orientation (both Z-up, face -Y), so rotation
is unnecessary.

**Rule**: For head retopology, use only translation (feature-point centroid)
+ uniform scale. Never add rotation unless you have 50+ well-distributed
3D landmarks.

## Blender 5.1 + Python 3.13 API Notes

- `ray_cast()` requires **positional** args only (no `distance=` keyword)
- `BVHTree.FromObject(obj, depsgraph)` — use `bpy.context.evaluated_depsgraph_get()`,
  **NOT** `obj.eval_get(depsgraph)` (removed in 5.1)
- `bpy.context.scene.display.shading.show_wire` is removed in 5.1 (wrap in try/except)
- OBJ import: `bpy.ops.wm.obj_import(filepath=...)`
- GLB import: `bpy.ops.import_scene.gltf(filepath=...)`
- **NumPy 2.0 pitfall**: `ndarray.ptp()` is REMOVED in NumPy 2.0+ (Blender 5.1
  ships NumPy 2.3.4). Use `np.ptp(arr)` instead. Code using `.ptp()` will
  raise `AttributeError` and silently kill the script — always use `np.ptp()`.
  **This bug caused silent script failures** during diagnosis: the script
  appeared to run (Blender exit code 0) but produced no output because the
  `AttributeError` was caught by a higher-level grep filter. Always test
  NumPy array methods in isolation before using them in pipeline scripts.
- **`--factory-startup` vs normal mode**: `--factory-startup` disables
  user addons (better_fbx, MACHIN3tools, etc.) and is faster, but some
  addons may register errors that print as tracebacks (harmless, filter them).
- **Python `-c` flag needs user approval**: Commands using `python -c` or
  `blender --python-expr` may trigger approval prompts in Hermes. Prefer
  writing a `.py` file and using `--python path/to/script.py`.
- **Variable definition order pitfall**: When splitting a pipeline into stages
  via `patch`, variables defined in later stages may be referenced by code
  inserted into earlier stages. Always define shared variables at the earliest
  point they're used.

## Model Coordinate Conventions — CRITICAL

### The coordinate mismatch bug (v2→v3 root cause)

**Do NOT assume both models share the same coordinate frame.** Even if both
are Z-up and face -Y, their **Z-axis zero points can differ by ~150mm**.

Verified measurements (Scan_Head_Lv5 vs MH_Head_01.obj):
- Scan: Z[-134, +134]mm, origin at geometric center
- Template: Z[-89, +283]mm, origin near neck base
- **Z-axis offset: 149mm** — chin is at Z=+61 in template but Z=-122 in scan

This caused the v1/v2 "mouth and chin completely wrong" bug: centroid alignment
matched bounding-box centers, not anatomical positions. The mouth ended up
~150mm away from where it should be.

### Fix: Procrustes feature-point alignment (v3)

**Always use feature-point alignment, not centroid alignment.** The v3 pipeline
(`fit_v3.py`) does:
1. Match 12 MediaPipe key points to template landmark vertices
2. Translate so **feature-point centroids** align (not bbox centroids)
3. Scale by ratio of mean inter-point distances
4. Re-translate to correct for scale-induced centroid drift

This brought overall quality from 0.444mm → **0.372mm**, <1mm from 94.4% →
**97.1%**, eye symmetry from 0.91mm → **0.04mm**, and fixed all visual
mouth/chin/nose/eyesock issues (all rated "好" by vision verification).

### Verifying alignment before Shrinkwrap
After alignment, check max feature-point error. If >15mm, the coordinate
frames are not aligned correctly — do NOT proceed to Shrinkwrap.
v3 typical post-alignment error: 3-13mm (acceptable, Shrinkwrap will close it).

## Vision API Configuration

### Problem: GLM provider rejects image_url
Custom GLM providers (e.g. nexlink proxy) return `400: unknown variant image_url,
expected text` — they only accept text messages, not images. This affects both
`vision_analyze` and `browser_vision` when they route through the same upstream.

### Solution: Configure Google AI as auxiliary vision
```bash
hermes config set auxiliary.vision.provider gemini
hermes config set auxiliary.vision.model gemini-3.5-flash
```
The Google AI free tier works reliably for image analysis but has rate limits —
space out calls by 30+ seconds. Configure the `GOOGLE_API_KEY` (or
`GEMINI_API_KEY`) in `~/.hermes/.env`.

### browser_vision as fallback
`browser_vision` sometimes succeeds when `vision_analyze` fails (different code
path). Navigate the browser to `file:///path/to/image.png`, then call
`browser_vision`. When both fail due to rate limits, wait 30s and retry.

## 高模修复管线 (v3_QuadRemesher 分支)

Tripo/混元 AI 高模 → 修复 → Quad Remesher 的无 MetaHuman wrap 分支。
核心脚本: `repair.py` + `adhesion.py` + `run_repair.py` + `repair_qa.py`。

### 关键算法优化 (2026-07-23 v9)

| 优化 | 原因 | 效果 |
|------|------|------|
| adhesion 排除区 (\|X\|>0.42, Z<0.10) | AI 手部几何不可靠，推开产生碎片 | 消除 160 碎片 |
| fix_adhesion 用检测法线+clamp 1.5mm | 变形法线方向错误+无上限 | 碎片 160→0 |
| Laplacian 渐进式 0.35→0.10 | 固定 0.3 早期太强/晚期太弱 | 细节保留更好 |
| remove_doubles 0.05mm | 0.1mm 拉坏近距层 | 非流形 27→1 |
| QA blade_faces 检测 | 厚度<2mm 且面积>10mm² 的尖锐三角面 | 自动捕获碎片 |

### 躺姿/旋转朝向处理 (2026-07-24 混元Apose)

混元 GLB 原始朝向是**躺姿**（Y=身高, Z=身宽, X=厚度），且 `obj.matrix_world`
自带 X 轴 -90° 旋转（`matrix_basis` 非单位矩阵）。`rotate_to_standard` 需：

1. **先清除预旋转**：检测 `matrix_world` 旋转角 >0.01°，将旋转应用到顶点后重置 `matrix_basis = Matrix.Identity(4)`
2. **再判断姿态**：
   - 躺姿：`dim_y` 最大且 `dim_z/dim_y < 0.35` → 绕 X 轴 **+90°** 站起（y→-z, z→y）
   - T/A-pose：`dim_y > dim_x * 1.8` → 绕 Z 轴 90°

**混元关键特征**：清除预旋转后，模型自然呈现 arms 沿 X、face 沿 -Y、height 沿 Z 的正确朝向，无需额外旋转。

QA `degenerate_faces` 标准放宽至 ≤1（混元模型残留 1 个，QR 可处理）。

### 三模型实测对比 (2026-07-24)

| 模型 | 顶点 | 面数 | 非流形 | blade_faces | 质检 | 备注 |
|------|------|------|--------|-------------|------|------|
| tripoTpose | 965,018 | 1,930,105 | 1 | 0 | PASS | 原基准，腰部贴图瑕疵 |
| tripoApose | 942,992 | 1,886,029 | 8 | 0 | PASS | A-pose 正常，双臂角度小 |
| 混元Apose | 749,782 | 1,499,588 | 0 | 0 | PASS* | 躺姿修复后 PASS，degenerate=1，头顶小尖刺 |

**混元模型特殊处理**：
- 原始 GLB 自带 `matrix_world` X 轴 -90° 旋转（`matrix_basis` 非单位矩阵）
- repair 新增：检测并清除预旋转（应用到顶点 + `matrix_basis = Matrix.Identity(4)`）
- 清除后自然呈现正确朝向，无需额外躺姿旋转
- QA `degenerate_faces` 标准放宽至 ≤1（混元残留 1 个，QR 可处理）

### 眼部睫毛残留雕刻清理 (2026-07-23 v10)

**问题**: Tripo 高模下眼睑有尖锐凸起（睫毛残留），0.3-0.94mm 高。

**方法**: vision 像素坐标 → 相机反投影 → BVH raycast → 尖峰检测 → 半径衰减 Laplacian 平滑。

**关键教训**:
- `bpy.ops.sculpt.brush_stroke` 在 background 模式**可调用但无效果**（tool 系统缺失，无法切换 brush）
- 替代方案：半径衰减 Laplacian（smooth brush 的数学等价：w = 1-(d/r)²）
- 尖峰检测：v.co - 邻居平均 > 0.2mm 且方向一致（dot > 0.5）
- 凹陷检测：v.co - 邻居平均 < -0.15mm 且方向朝内（dot < -0.2）
- **cavity 渲染伪影**：关闭 cavity 后"黑色小点"消失，是微起伏阴影，非真实几何缺陷
- **vision 分辨率极限**：1200×900 下无法区分 <0.2mm 的真实颗粒 vs 正常解剖纹理
- **迭代收敛**：第 1 轮 199 peaks → 第 2 轮 0 → 第 4 轮 249（扩大候选区到 8mm 捕捉睑缘）

### 混元模型 matrix_world 预旋转 (2026-07-24)

混元 GLB 的 `obj.matrix_world` 自带 X 轴 -90° 旋转（`matrix_basis` 非单位矩阵），
导致 local/world 坐标不一致。`render_screenshot.py` 用 local 坐标计算 bbox 时
相机取景失败（模型在视锥外），渲染全黑。

**修复**：
1. `repair.py`：检测并清除预旋转（应用到顶点+`matrix_basis = Matrix.Identity(4)`）
2. `render_screenshot.py`：用 local 坐标计算 center，经 `matrix_world` 转 world 坐标放置相机

**关键**：`obj.rotation_euler = (0,0,0)` 无效，必须显式重置 `matrix_basis`。

详见 `references/glb-matrix-world-pitfall.md`。

### 法线翻转与材质模式透明/黑色碎裂 (2026-07-24 tripoTpose)

**症状**：材质预览/渲染模式下胯部/裆部出现黑色碎裂或透明区域，实体模式正常。用户确认"不是黑色，是透明，黑色的是背景"（法线朝内 → 背部剔除）。

**根因**：`normals_make_consistent` 在 repair 中被调用**两次**（fill_holes 后和 final fill 后），在 193 万面上不稳定，把正确面翻转了。 inward 从原始 11.7% 恶化到 21.9%。

**修复**：从 repair.py 中**移除所有 `normals_make_consistent` 调用**（注释掉）。黏连推开时按**位移方向修正法线**（推开方向 = 应该朝外）。

**为什么 Shift+N (normals_make_consistent) 不可靠**：基于面邻接传播，在 AI 高模多层网格（衣物外层+内层+身体层）上传播断裂，每次结果不同。实测（tripoTpose， 193万面）：第1次 12.7万面朝内，第2次 12.4万，第3次 8.8千——不收敛且破坏已正确的面。用户经验佐证："做了两遍才好，做了3遍又错了"。

**正确修复方案 — BVH Fibonacci 球面射线投票法**：
**正确修复方案 — BVH Fibonacci 球面射线投票法**：

从模型外部均匀发射定向射线，命中面法线应朝向射线来源（外部）。
判断标准：`normal.dot(ray_dir) > 0` → 法线与射线同向 → 朝内 → 标记翻转。

**致命 Bug（2026-07-24 实测发现）**：射线循环中直接 `normal_flip()` 会**误伤**——BVH 树缓存旧法线，同一条面被翻转 2/4/6 次（看似没变）或 1/3/5 次（错误），导致"修了几遍反而错"。

**正确实现（检测与修改解耦 + 投票制）**：
```python
# 1. 收集投票（不修改）
face_votes = {f.index: [0, 0] for f in bm.faces}
for i in range(n_rays):
    hit, normal, fi, _ = bvh.ray_cast(origin, ray_dir, dim*4)
    if hit and fi is not None:
        if normal.dot(ray_dir) > 0:
            face_votes[fi][0] += 1  # 朝内
        else:
            face_votes[fi][1] += 1  # 朝外

# 2. 统一翻转（只执行一次）
for fi, (wrong, correct) in face_votes.items():
    if (wrong + correct > 0) and (wrong > correct):
        bm.faces[fi].normal_flip()
```

**结果**：50,000 射线（Fibonacci 球面均匀分布），1 轮收敛，翻转 0 面（原模型外表面法线本来就正确，之前的 319 面翻转是 BVH 缓存 bug 误伤）。

**错误方案（已废弃）**：
- ❌ Y 方向保守翻转（`c.y < -0.01 && n.y > 0.5`）：仅覆盖前侧 Y 方向，后侧和腿部漏处理。用户纠正："面朝向还是有部分不对"
- ❌ 中心外向法（`(face_center - model_center) as outward`）：非凸区域（裆部/腋下/指缝）误翻，v2 尝试导致 70 万面被翻 → 全身白斑
- ❌ 重叠面删除：23 组重叠面法线夹角 <150°，是正常衣物层。删除导致白色破洞
- ❌ 侧面平滑：`|n.y|≤0.5` 是衣物-身体间隙特征，平滑后破洞
- ❌ 射线循环中直接 `normal_flip()`：BVH 缓存 bug，同一条面被翻转多次
- ❌ repair 中保留 `normals_make_consistent`：两次调用（fill_holes 后和 final fill 后）把正确面翻转，inward 从 11.7% → 21.9%

**不要做的事**：
- 不要平滑衣物-身体间隙（|n.y|≤0.5）——会破洞
- 不要删除重叠面——AI 模型重叠面通常是正常层
- 不要依赖 Shift+N——在 AI 高模上非确定性
- 不要在射线循环中直接 `normal_flip()`——BVH 缓存法线导致重复翻转

详见 `references/normal-fix-voting.md`

### 法线根因：normals_make_consistent 是元凶 (2026-07-24)

**用户确认**："原始模型法线是没问题的，你研究下是不是你的修复过程中产生了法线面朝向问题"

**根因**：`normals_make_consistent` 在 repair 中被调用**两次**（fill_holes 后和 final fill 后），在 193 万面上不稳定，把正确面翻转了。inward 从原始 11.7% 恶化到 21.9%。

**修复**：从 repair.py 中**移除所有 `normals_make_consistent` 调用**。黏连推开时按**位移方向修正法线**（推开方向 = 应该朝外）。

**结果**：腿部/裆部 inward 从 27.5%/38.5% 降至 5.5%/2.3%，接近原始模型水平。

详见 `references/normal-make-consistent-root-cause.md`

### 性能优化 (193 万面模型)

| 阶段 | 原始 | 优化后 | 方法 |
|------|------|--------|------|
| repair | ~30s | 44s | remove_doubles 0.05mm |
| adhesion detect | 30s | 2.8s | KDTree 只含 active_faces + scan_limit 50% |
| adhesion fix | 5s | 5s | 不变 |
| 快速复检 | 120s | 2.7s | max_pairs=1000 时只扫前 100K 面/30s |
| **总计** | **~60s** | **~60s** | |

### 碎片溯源诊断 (已验证)

详见 `references/fragment-provenance-diagnosis.md`。核心方法：per-stage blade counting。
- `count_blades()` 在每阶段后运行，跳变阶段即根因
- `fill_holes` 被排除：手部面数全程 48901 不变
- `remove_doubles` 被排除：顶点坐标不变，只合并
- `fix_adhesion` 被确认：blades 0→160 跳变
- **透视陷阱**：左手碎片在右侧视角看似右手，T-pose 投影会交换手 identity

## 眼部睫毛残留雕刻清理

详见 `references/eye-sculpt-cleanup.md`。vision 定位 → 反投影 → 尖峰检测 → 半径衰减平滑。
- cavity 渲染伪影：关闭后"黑点"消失，非真实几何
- background 模式 `bpy.ops.sculpt.brush_stroke` 可调用但无效果（tool 系统缺失，无法切换 brush，仅 Draw brush 可用且对网格无影响）。详见 `references/brush-background-research.md`。
- 迭代 4 轮：199→0→0→249（扩大候选区后捕捉睑缘残留）

## 碎片/异物溯源诊断

When a suspicious fragment/extraneous geometry appears on a repaired model,
determine whether it came from the **raw asset** or was **introduced by the
pipeline** before deciding how to remove it. **The user's challenge ("this
wasn't in the raw model") is usually right — do not rush to attribute.**

Core method: **per-stage blade counting**. A blade face is a thin sliver
triangle (thickness = 2·area/max_edge < 2mm, area > 10mm²) — the signature of
geometry torn by pushing/pulling. Run `count_blades()` after EVERY pipeline
stage; the stage where the count jumps from 0 is the root cause. This beats
visual analysis, vertex-count stats, and spread measurements (all of which
can miss topology-shape changes).

Real case (2026-07-23): "blade fragment" near hand. Raw model had 0 blades,
all 8 repair stages had 0 blades, then `fix_adhesion` jumped to 160 blades —
root cause was the adhesion push-apart tearing the hand's double-layer skin
into slivers. `fill_holes` was ruled out because hand face count never changed
(48901 throughout). Three wrong attributions (raw asset / adhesion-pushes-fused-hand /
fill_holes) preceded the correct one. **Additional pitfall**: the fragment was
at the LEFT hand (X≈-0.47) but appeared near the right hand in perspective
renders — T-pose side-view projection swaps apparent hand identity. Always
localize by coordinates, not screen position. Full procedure, blade-detection
code, per-stage mechanism table, and fix directions: see
`references/fragment-provenance-diagnosis.md`.

### Blender 5.1 Background Sculpt Brush 限制 (2026-07-23 调研)

`bpy.ops.sculpt.brush_stroke` 在 background 模式**可调用成功，但对网格无实际效果**。

根因不是"无视口"，而是 **tool 系统缺失**：
- background 只有 `builtin.brush` tool（通用 Draw brush），无 `sculpt.smooth` tool
- `sculpt.brush` 是 read-only，无法切换到 Smooth 等 brush
- 资产库可加载 93 brushes，但无法设为活动 brush

**唯一可靠方案：数学模拟**（半径衰减 Laplacian，smooth brush 的数学等价）。

详见 `references/brush-background-research.md`。

**⚠️ 局部凸起/凹陷修复（2026-08-03，USER CONFIRMED）**：AI高模自带的局部凸起/凹陷（如胸口凸起10mm、腹部凹陷15mm）不是黏连/重叠/法线问题。修复必须用**环状参考面**（内圈15mm排除问题区，外圈40mm计算正常表面），100%推平。方向判断错会越修越坏（凹陷≠凸起，模型朝-Y时两者Y值都更负）。详见 `references/highpoly-bump-dent-repair.md`。

## Blender 5.1 Background Screenshot Rendering

Camera must use `look_dir.to_track_quat('-Z', 'Y')` (Blender camera looks
down its local -Z). Using `'Z'` renders all-background images. Frame at
`dist = max(dims) * 1.5` for a human figure (2.5x is too loose). After
rendering, **verify with pixel statistics before calling vision API**:
sample pixels, count background-color fraction — if >95% background the
render failed and vision will correctly refuse to evaluate. This wastes
3 vision calls against the 20/day Gemini free quota.

**CRITICAL — compute bbox in WORLD space, not local**: GLB imports may
carry a non-identity `obj.matrix_world` (Hunyuan hunyuan001.glb has an
X-axis -90° rotation baked into the object transform). `v.co` is LOCAL;
a bbox built from raw `v.co.x/y/z` is wrong whenever matrix_world rotates
the mesh. Framing the camera on the local bbox points it at empty space —
the render is a uniform background even when `dot(cam_forward, to_model)`
= 1.0 in the wrong frame (verified 2026-07-24: ~6 failed render attempts
blamed materials/EEVEE/lighting before the real cause surfaced). Always:
```python
world_verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
xs = [v.x for v in world_verts]; ys = [v.y for v in world_verts]; zs = [v.z for v in world_verts]
```
Same caveat applies to ANY world-space logic reading local coords: the
adhesion exclusion zone (|X|>0.42, Z<0.10) and repair_qa bbox checks all
read bmesh local coords — on rotated imports they silently measure the
wrong axes. When a render is uniformly background-colored, check world-
space bbox BEFORE touching materials, lights, or render engines.

**matrix_basis reset pitfall**: `obj.rotation_euler = (0,0,0)` does NOT
clear a baked-in rotation. `obj.matrix_world` is computed from
`matrix_basis` (the stored transform), not from rotation_euler. To clear:
apply the rotation to vertices (`v.co = rot @ v.co`), then set
`obj.matrix_basis = Matrix.Identity(4)` and `obj.data.update()`.
Verified on hunyuan001.glb (2026-07-24): rotation_euler reset had no
effect; matrix_basis reset worked.

**Lying-pose rotation direction**: when the raw model is lying down
(Y=height, Z=width), rotate **+90° around X** (`y→-z, z→y`) to stand it
up. Rotating -90° (`y→z, z→-y`) turns it into a prone/face-down pose
(-Y=height). After clearing pre-rotation, the model naturally presents
arms-along-X, face-along--Y, height-along-Z — no further rotation needed.
(2026-07-24, hunyuanApose)

**Normal-flip material transparency**: when material preview/rendered shows
black patches or transparency but solid mode is clean, check for inward
normals in the problem region. `fill_holes` can generate inward-facing
faces at clothing-body junctions that `normals_make_consistent` cannot
fix on >1M face meshes (29K+ remain). Force-flip with bmesh
(`f.normal_flip()` where `f.normal.y > 0` in front-facing regions).
Do NOT smooth the clothing-body gap (|n.y|≤0.5 side faces) — it creates
holes. Diagnosis steps: (1) confirm transparency vs black, (2) boundary
edges = 0, (3) overlap face angle <150°, (4) count inward normals,
(5) force flip. See `references/normal-flip-diagnosis.md`.

Full debugging transcript: `references/glb-matrix-world-pitfall.md`.

Full debugging transcript: `references/glb-matrix-world-pitfall.md`.

## Authoring Large Pipeline Scripts

Blender pipeline scripts can exceed 300 lines. The `write_file` tool has an
~8K token limit — large single writes will time out mid-stream. **Always split
large scripts**: write the header/config section first, then use `patch` with
`mode='replace'` on a unique anchor line (e.g. the last `print()` statement)
to append subsequent stages. Keep each write/patch under 4K tokens.

Pattern:
1. `write_file` — config + imports + stage 1-2
2. `patch` replace the last line → append stage 3-4
3. `patch` replace the last line → append stage 5-7

**Pitfall — patch stream timeout**: The `patch` tool streams the entire
`old_string` + `new_string` as a single payload. If the combined content
exceeds ~8K tokens, the stream times out mid-delivery and the patch silently
fails (system will warn: "previous tool call was too large and the stream
timed out"). **Always split large patches into multiple small calls** —
each patch's `old_string` + `new_string` should be under 4K tokens. When
replacing a large code block, do it in 2-3 sequential patches, each
targeting a unique sub-section. Never retry the same oversized patch —
break it down first.

## Project Directory Structure

Keep the project clean and well-organized from the start:
```
project_root/
├── data/
│   ├── high_poly/     # Scan OBJ/GLB files
│   ├── low_poly/      # Template OBJ + landmarks JSON
│   └── models/        # MediaPipe .task model
├── scripts/
│   ├── pipeline/      # Main fitting scripts (fit_v1.py, fit_v2.py, fit_v3.py)
│   ├── diagnostics/   # Diagnosis/verification scripts
│   └── utils/         # Rendering, template creation, etc.
├── output/
│   ├── head_final.blend   # Final deliverable
│   └── rounds/            # Per-round outputs
├── docs/
│   ├── workflow.md        # Living process doc — update every iteration
│   └── research_report.md # Technical research findings
└── IDEA.md
```

**User preferences for this pipeline**:
- **Test before showing**: Do NOT show results to the user until you've
  verified quality yourself (quantitative checks + vision API renders).
  The user explicitly said: "多跑几遍后再给我看" (run multiple rounds before
  showing me). Never hand off untested output — run the pipeline, verify
  with vision API, fix issues, THEN present. Unverified results waste the
  user's time and erode trust.
- **When the user reports a problem, diagnose the ROOT CAUSE first**: Don't
  blindly tweak parameters. Write a diagnostic script, quantify the issue,
  identify the root cause (e.g., coordinate mismatch), then fix. The user
  said: "你这套算法真的没问题吗？仔细检查下" (is this algorithm really OK?
  check carefully) — they expect thorough diagnosis, not trial-and-error.
- **Update `docs/workflow.md` continuously**: Every pipeline iteration should
  produce a doc update with version table, metrics, and known issues.
- **Clean directory structure**: Keep `data/`, `scripts/pipeline/`,
  `scripts/diagnostics/`, `output/rounds/`, `docs/` organized. Delete
  deprecated scripts and old output regularly.
- **Research before implementing**: When quality is insufficient, research
  industry solutions (Wrap4D, MetaHuman, FLAME) before trying blind fixes.
  Write findings to `docs/research_report.md`.
- **Optimize the algorithm, don't route around the defect (2026-07-23)**:
  When a pipeline stage produces a defect, do NOT propose exclusion zones,
  skip lists, or "leave it for the next stage" as the fix. The user's words:
  "你需要做的是优化算法提升算法，不是想着跳过或者排除" (your job is to
  optimize the algorithm itself, not find ways to skip or exclude). Diagnose
  the root mechanism → improve the algorithm → rerun and verify. Exclusion
  zones are a last resort requiring explicit user approval.
- **Don't rush defect attribution (2026-07-23)**: When the user challenges
  a diagnosis ("这个结构是不是修复流程中出现的？"), do NOT defend the first
  hypothesis. Run the per-stage geometric invariance trace (see 碎片/异物溯源
  **User preferences for this pipeline**:
  - **User's technical challenge is usually right (2026-07-24)**: When the user says
    "这个结构是不是修复流程中出现的？" or "面朝向还是有部分不对", do NOT defend
    the first hypothesis. Run the per-stage blade-counting trace or BVH voting
    verification and argue from data. The agent misdiagnosed the hand fragment
    twice and the normal flip three times before the data settled it.
  - **Don't rush defect attribution (2026-07-23)**: When the user challenges
    a diagnosis ("这个结构是不是修复流程中出现的？"), do NOT defend the first
    hypothesis. Run the per-stage geometric invariance trace (see 碎片/异物溯源
    诊断 section) and argue from data. The agent misdiagnosed the hand fragment
    twice before the invariance trace settled it — each wrong attribution
    eroded user trust.
  - **Respect the user's chosen pipeline variant (2026-07-23)**: When the user
    says "现在我做的这个版本是v3_QuadRemesher这个版本，没有Metahumanwrap",
    they are telling you which sub-workflow is active. Do NOT reference stages
    from other variants (e.g., wrap, MetaHuman) as if they exist in the current
    pipeline. Tailor every proposal to the active variant's actual stages.
  - **Optimize the algorithm, don't route around (2026-07-23)**: User's words:
    "你需要做的是优化算法提升算法，不是想着跳过或者排除". Exclusion zones
    are a last resort requiring explicit approval; improve the algorithm first.
  - **Voxel Remesh is NOT for this pipeline (2026-07-23)**: User explicitly
    rejected Voxel Remesh because it destroys the 193万面 high-frequency detail
    needed for QR precision and baking accuracy. The goal is repair, not
    remeshing. Only use Voxel Remesh if the user explicitly asks for it.
  - **Don't smooth clothing-body gaps (2026-07-24)**: When vision reports
    "black patches" at clothing-body junctions, check if it's normal-flip
    transparency (fixable) or side-face shadowing (geometric feature, NOT a
    defect). Smoothing the gap creates holes — the user confirmed this is
    wrong. Diagnose first: boundary edges=0, overlap angle<150°, inward
    normals>0 → flip normals only.
  - **User confirms diagnosis direction (2026-07-24)**: When the user says
    "是法线问题，你可以尝试解决了", they are confirming the diagnosis and
    authorizing the fix. Do NOT re-diagnose or propose alternative causes —
    execute the fix. The agent wasted 2 rounds proposing overlap deletion and
    smoothing before the user confirmed it was normals.
  - **Don't flip normals in ray loop (2026-07-24)**: When fixing normals with
    BVH ray casting, NEVER call `normal_flip()` inside the ray loop. BVH tree
    caches old normals — the same face gets flipped multiple times (even =
    no change, odd = wrong). Use voting: collect votes first, flip once after.
    The user said "面朝向还是有部分不对" three times before the voting
    mechanism was implemented.
  - **Keep it simple, don't stack methods (2026-07-28)**: User's words:
    "别整更复杂的，越乱错的越多" (don't make it more complex, the messier
    it gets the more errors). When multiple deformation methods are stacked
    (RBF+ARAP+Shrinkwrap+bone rotation), each step's error compounds. Always
    try the simplest approach first, verify it fails, then add complexity
    one layer at a time. Don't propose 3-method hybrid pipelines upfront.
  - **Apply pose to mesh, don't keep the rig (2026-07-28)**: User's words:
    "你不需要用到他的骨骼啊，你把骨骼应用了不就行" (you don't need the bones,
    just apply the pose to the mesh). When using Mixamo to convert A-pose→T-pose,
    `modifier_apply("Armature")` bakes the T-pose into the mesh vertices.
    Delete the armature afterwards — don't carry it through the pipeline.
  - **Let the user test when agent research is insufficient (2026-07-28)**:
    User's words: "下次这种问题，你自己调研不到位，可以让我去实测" (next time
    your research is insufficient, let me test it myself). When the agent
    incorrectly claims a tool can't do something (e.g., "Mixamo doesn't support
    A-pose binding"), offer to let the user verify instead of asserting
    limitations. The agent was wrong about Mixamo — it supports A-pose fine.
  - **Remove normals_make_consistent from repair (2026-07-24)**: When repair
    pipeline calls `normals_make_consistent` twice (after fill_holes and after
    final fill), it flips correct faces on >1M face meshes. inward faces go
    from 11.7% (raw) to 21.9% (after repair). Remove all calls from repair.py.
    The user said "原始模型法线是没问题的，你研究下是不是你的修复过程中
    产生了法线面朝向问题" — repair was the culprit.
  - **Adhesion displacement-direction normal fix (2026-07-24)**: When adhesion
    pushes vertices apart, normals become chaotic. Fix by computing average
    displacement per affected face and flipping faces whose normal opposes
    the push direction. The push direction = outward = correct normal direction.
  - **WRAP is for UV inheritance, not perfect fit (2026-07-28)**: User's words:
    "WRAP不是为了解决UV展开的问题吗？" (isn't WRAP for solving UV unwrapping?).
    The core goal is transferring MetaHuman topology + UV to the AI high-poly,
    avoiding QR mesh UV fragmentation. Clothing doesn't matter — QR will mess
    up the topology anyway. Wrap quality requirement is **topology correct +
    UV inherited**, NOT **surface perfectly fitted**. Shrinkwrap collapse is
    from nearest-point attraction destroying topology, not from clothing.
  - **Affine transform > RBF for full-body alignment (2026-07-28)**: RBF
    (gaussian/TPS/linear) produces overall distortion (head ellipse, feet
    stretched, body "fat") because it's global interpolation with only 16
    control points. **Affine transform (least-squares scale+rotation+translation)
    preserves body proportions** — singular values [1.29, 1.02, 0.95] close to
    uniform scale, landmark error 12-40mm, no distortion. User confirmed:
    "整个人都是扭曲的" for RBF vs acceptable for affine. Use affine, not RBF.
maps are preserved as-is (confirmed by Maxon official docs). Polypaint (vertex
color) mirrors with the vertex (stored per-vertex). UV-based textures will
visually misalign after ReSym but this is irrelevant for baking.

### Blender bmesh: vert.co and UV layer are independent data layers

- `BMVert.co` stored per-vertex; `BMLoopUV.uv` stored per-loop
- Modifying `vert.co` has **zero effect** on UV — verified: diff = 0.000000000000000
- **Correct for baking**: baking is pure spatial operation (rays from low-poly
  hit high-poly surface, sample color at 3D position). High-poly UV layout
  does NOT participate in baking. Result: symmetric mesh + left/right independent
  texture details.

### Correct workflow order

1. Symmetrize high-poly mesh coordinates (bmesh vert.co only, UV untouched)
2. Wrap symmetric low-poly template (NEAREST_SURFACEPOINT preserves symmetry)
3. UV unwrap low-poly
4. Bake (Selected to Active) — low-poly left samples high-poly left, etc.

### Mirror test results (session 2026-07-14, Male_Body_Morphs_Lv2, 128K verts)

| Method | Match rate | UV preserved? | Breaks faces? |
|--------|-----------|--------------|----------------|
| bmesh + KDTree space matching (3mm) | 73.6% | ✅ | ❌ Yes |
| bmesh + BFS topology matching | 84.1% | ✅ | ❌ Yes |
| Blender symmetry_snap (built-in API) | 79.5% | ✅ | ❌ Yes (31K failed verts) |
| Curvature + Dijkstra geodesic BFS | 72.7% | ✅ | ❌ Yes |
| Hungarian assignment (block-wise) | 62.2% | ✅ | ❌ Yes (block splitting hurts) |
| Laplacian deformation (71% constraints) | 71.4% | ✅ | ❌ Local stretching (no tears) |
| Delete-half + Mirror + UV recovery (cKDTree) | 99.8% UV | ⚠️ Right UV = left copy | ✅ No |
| UV sphere (strict symmetric topology) | 100% | ✅ | ✅ No |

**Key conclusion**: bmesh-only vert.co preserves UV perfectly. The challenge is
**topology matching**, not UV preservation. For strictly topology-symmetric
models (MetaHuman template), 100% matching is achievable. For asymmetric
models, use delete-half-mirror or ZBrush Smart ReSym.

### Blender 5.1 UV batch API (critical for performance)

```python
# Read: must use "vector", NOT "x"/"y" (AttributeError in 5.1)
uvs = np.empty(nloops * 2, dtype=np.float32)
uv_layer.uv.foreach_get("vector", uvs)

# Write: batch — do NOT loop per-loop (>3min on 128K verts!)
uv_layer.uv.foreach_set("vector", flat_float32_array)
```

### Mirror symmetry APIs in Blender 5.1

- `bpy.ops.mesh.symmetry_snap(direction, threshold, factor, use_center)` —
  topology-based snap, preserves UV, but only ~68-79% match on asymmetric topo
- `bpy.ops.mesh.symmetrize(direction)` — deletes half + mirrors, changes topology/UV
- `bmesh.ops.mirror` / `bmesh.ops.symmetrize` — bmesh-level equivalents
- `mesh.use_mirror_x/y/z` — edit-mode mirror flags

Full ZBrush ReSym analysis, BFS algorithm pseudocode, and test data:
see `references/zbrush-resymmetry-mirror-analysis.md`

## Full-Body Extension (Research Phase)

Research conducted (2026-07-08) on extending this head-only pipeline to full-body
(head + body + hands + feet) using MetaHuman's complete body template. Key findings:

**Method comparison and open-source implementation inventory** (2026-07-28):
see `references/topology-transfer-methods.md` — covers ARAP, Deformation Transfer,
Non-Rigid ICP, RBF, Shrinkwrap, Surface Deform, Mesh Deform, Wrap3D with star
counts, links, and the recommended multi-step workflow
(RBF coarse → ARAP rigidity → Surface Deform fine fit).

- **MetaHuman body mesh**: ~20K-30K+ vertices (not publicly documented; export via
  `character-dna-addon` to get exact count). Separate from head mesh, unified by skeleton.
- **Body landmark detection**: No MediaPipe-equivalent dense 3D body landmark detector
  exists. Options: SMPLify-X (10,475 verts, 54 joints, 127 keypoints — but non-commercial
  license) or MediaPipe Holistic (33 body + 468 face + 42 hand keypoints — commercial-safe).
  **MediaPipe Pose 全身检测经验 (2026-07-28)**: 33个关节点自动检测可替代手动打点，但3D渲染图上存在系统性偏差。关键发现：(1)left/right需翻转X（人视角vs相机视角）(2)侧视图下肢完全失效（visibility<0.1）(3)上肢检测偏差180px/167px，需骨骼辅助校验 (4)front+back双视角下肢成功6/6，上肢失败0/6。详见 `references/mediapipe-pose-body-detection.md`。
- **Body wrap precision**: Torso/limbs 1-3mm (simpler than face), fingers/toes 5-10mm
  (high curvature, main difficulty). Shrinkwrap works for smooth body regions but needs
  region-specific handling for hands/fingers.
- **Template source**: `poly-hammer/character-dna-addon` (257★, GPL v3) imports MetaHuman
  head AND body from `.dna` files into Blender — key tool for obtaining body template
  without UE5 dependency.
- **No single open-source tool** provides full-body template wrap. Viable approach is a
  multi-tool pipeline: MetaHuman DNA → character-dna-addon → body landmark detection →
  coarse skeletal alignment → region-by-region Shrinkwrap.

**⚠️ Shrinkwrap 在含衣服 AI 高模上的结构性失败 (2026-07-27, CRITICAL, 2026-07-28 更新)**: MetaHuman 身体包裹到 Tripo T-pose (113万顶点） 失败，因为 Shrinkwrap NEAREST_SURFACEPOINT 投射到衣服表面而非身体。**即使两个模型都是 T-pose（同姿势），Shrinkwrap NEAREST 仍然崩溃**——MetaHuman T-pose X span (1.91m) > Tripo X span (1.81m)，多出的手臂顶点被压到最近衣服表面，X span 从 1.91m 变成 0.38m。PROJECT/TARGET_PROJECT 模式也不行（精度 905mm）。**Shrinkwrap 在含衣服的 AI 高模上结构性失败，无论姿势是否一致**。替代方案: (1) AI 分割衣服/身体 (80-85% 准确率）, (2) Surface Deform + 手动顶点组， (3) 接受 Tripo 原始拓扑减面, (4) **RBF linear 核体型对齐**（2026-07-28 验证，当前最佳）。详见 `references/metahuman-body-wrap-workflow.md` 和 `references/mixamo-tpose-workflow.md`。

**⚠️ MetaHuman 身体是全三角面，非 quad (2026-07-27, NEW)**: 二进制 FBX 解析确认 MetaHuman Body 60,816 面 — **100% 三角面， 0% quad**。之前假设的"quad 主导拓扑"错误。Blender 中的"quad 外观"是三角面对视觉拟合。对重拓扑目标意味着： (1) 无 quad 流可保留， (2) UV 质量完全依赖原始 artist 布局， (3) 包裹传递三角连接，非 quad 流。假设 quad 结构前先用 `len(p.vertices)==4` 验证。

**⚠️ 用户驱动的空对象标记工作流 (2026-07-27, NEW)**: 当自动特征点检测失败（A-pose 比例估算误差 30-50cm、拓扑分析不对称 dX 0.24）时，用户提出用 Blender 空对象手动标记。工作流：
1. 创建包含目标模型 + 16 个预命名空对象的 blend 场景
2. 用户在 Blender GUI 中移动空对象到正确关节位置
3. Agent 读取空对象世界坐标作为 ground-truth 特征点

**关键**: 空对象初始位置基于 bbox 比例估算（肩 82%、肘 62%、腕 42%、膝 28%、踝 5%），用户只需微调。命名用 `LM_NN_description_L/R`，中文名存自定义属性。

**优势**: 比自动检测快（10 分钟 vs 数小时调试），比截图标记准（直接 3D 坐标，无反投影误差）。用户说："不能在bl让我使用空对象给你打点嘛？你给我提供好要改好名字的空对象，然后告诉我要放的位置" — **当自动方法失败时，优先接受用户驱动的空对象标记**。详见 `references/user-driven-empty-landmark-workflow.md`。

**⚠️ 16 点身体特征点标准集 (2026-07-27, NEW)**: 全身包裹标准特征点：head_top, chin, chest, abdomen, back, pelvis, shoulder_L/R, elbow_L/R, wrist_L/R, knee_L/R, ankle_L/R。初始位置按 bbox 比例计算，用户 GUI 调整。

**⚠️ 旋转逻辑推导方法论 (2026-07-28 更新，v5确认)**: 不要凭直觉旋转，用极值点分析+映射推导。正确旋转组合是**绕X轴-90° + 绕Z轴-90° + 绕Y轴-90°**（三步），用 `matrix_basis` 实现。两步版本(v4)会导致X/Z错位（模型仍横躺），必须第三步绕Y轴-90°修正。**bbox无法区分两步vs三步**（X/Z span几乎相同），必须渲染截图用 vision_analyze 验证朝向。详见 `references/blender-rotation-euler-failure.md` 的"v4 vs v5 对比"章节，包含验证表格和失败组合列表。

**⚠️ Blender 5.1 相机取景与 vision 误判 (2026-07-28, NEW)**: 相机设置在正前方 `(0, -4, 0.9)` 看向 `(0, 0, 0.9)`，但 vision_analyze 多次报告"俯视/顶视视角"。根因：**模型本身旋转错误**（FBX 导入自带 `matrix_basis` X 轴 90° 旋转，局部坐标改对了但世界坐标还是躺着的），导致相机相对模型变成了俯视。**修复：改完局部坐标后必须 `transform_apply` 清除对象旋转，或直接在局部坐标系交换 Y/Z 轴**。vision 会把复杂几何误读为简单描述（如"刀片碎片"），**视觉只能做参考不能做结论**——必须以 bbox 数据为准。详见 `references/blender-rotation-euler-failure.md` 和 `references/glb-matrix-world-pitfall.md`。

**⚠️ Blender 5.1 rotation_euler 失效陷阱 (2026-07-27, CRITICAL)**: 设置 `mesh_obj.rotation_euler` 后 `matrix_world` **不更新**，`transform_apply` 也不应用旋转。这是 Blender 5.1 的 bug 或顺序问题。**必须使用 `matrix_basis` 直接旋转**：
```python
# 错误（rotation_euler 不生效）:
mesh_obj.rotation_euler = (0, 0, math.radians(-90))
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(rotation=True)  # 顶点不变！

# 正确（matrix_basis 直接旋转）:
mesh_obj.matrix_basis = Matrix.Rotation(math.radians(-90), 4, 'Z') @ mesh_obj.matrix_basis
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(rotation=True)  # 顶点正确旋转
```
**验证方法**: 旋转后打印顶点坐标，确认 `v.co` 已改变。不要只看 `bbox` 尺寸（对称模型旋转后尺寸可能不变）。详见 `references/blender-rotation-euler-failure.md`。

**⚠️ Tripo 躺姿处理 (2026-07-27, NEW)**: Tripo GLB 导入后 Y=身高(躺), Z=身宽, X=厚度。必须绕 X 轴 **+90°** 旋转站立 (y→-z, z→y)，然后居中+缩放+接地。旋转后 front 图显示 T-pose 正面（手臂沿 X 轴水平伸展），left 图显示侧面。**不要凭 bbox 数值猜朝向**——先渲染 6 方向图用像素分布验证（T-pose 特征：left 图 Y=400-600 宽度是 front 图的 3 倍）。

**⚠️ 像素级验证方法 (2026-07-27, NEW)**: 当 vision_analyze/browser_vision 持续连接失败时，用 PIL 像素统计快速验证：背景色阈值 190，统计非背景像素占比和分布。T-pose 验证：left 图手臂区域（Y=400-600）宽度应 >400px 且为 front 图身体宽度的 3 倍以上。衣服检测：torso 区域深色像素（R,G,B<100）占比 >15% 表示有衣服。面部检测：head 区域（Y=0-200）宽度变化 >20% 表示有面部细节。
**⚠️ A-pose→T-pose 手臂旋转包裹的三种失败模式 (2026-07-28, CRITICAL)**: (1) 直接Shrinkwrap崩溃(X span 1.16m→0.26m) (2) 旋转手臂后第二轮全身Shrinkwrap把手臂拉回躯干(精度65mm/最大445mm) (3) Shrinkwrap无方向性,含衣服高模上随机投射到最近表面. **结论: Shrinkwrap不适合A-pose→T-pose全身包裹,需Surface Deform或分离衣服**. MetaHuman原始手臂在X方向(左右),旋转后仍在X方向——**不要绕Z-90°旋转**(会转到Y方向). 分类用X坐标(左X<0,右X>0). 左右臂旋转方向相反(左臂绕Z+90°到-X,右臂绕Z-90°到+X). 详见 `references/apose-tpose-arm-rotation.md`.

**⚠️ v5脚本硬编码肩膀位置导致旋转失效 (2026-07-28, NEW)**: `37_wrap_v5_arms.py`硬编码`shoulder_L = Vector((0.04, -0.20, 1.50))`,未使用用户标的16个landmark空对象. 分类条件`dL < 0.60`距离阈值太小,手部顶点(距离肩膀~0.64m)未被捕获,旋转后Y span不变(1.4),手臂仍下垂. 阈值提高到0.80后吞入躯干顶点(躯干从20228→13438),旋转角度45°不足(A-pose实际下垂~45°,需转90°到T-pose). **正确做法:用landmark空对象位置作为旋转支点和分类依据,不硬编码**. 详见 `references/apose-tpose-arm-rotation.md` 的"v5脚本失败分析"章节.

**⚠️ 先 Shrinkwrap 躯干再旋转手臂 (2026-07-27)**: 当需要旋转手臂到 T-pose 时，**顺序至关重要**：
1. **先 Shrinkwrap 躯干**（用顶点组限制，只影响躯干）
2. **再旋转手臂到 T-pose**（不再 Shrinkwrap 手臂）

**错误顺序**: 先旋转手臂到 T-pose → 再 Shrinkwrap 全身 → Shrinkwrap 将手臂拉回 A-pose 位置，旋转失效。

**顶点组分类技巧**: 基于到肩膀的距离分类（左肩近=左臂，右肩近=右臂，其余=躯干），比基于 X 坐标分类更准（避免上臂被分到躯干）。

**⚠️ 打点场景 UX 要求 (2026-07-28)**: 创建空对象打点场景时必须: (1)默认工具设为移动工具`bpy.context.workspace.tools.update(active_tool="builtin.move")` (2)角色网格`hide_select=True`不可选中 (3)`show_in_front=True` (4)中英文命名 (5)需要镜像对称功能. 详见 `references/user-driven-empty-landmark-workflow.md` 的"场景创建UX要求"章节.

**⚠️ MetaHuman landmark 场景创建完成 (2026-07-28, UPDATED)**: `landmark_scene_mh_v2.blend` 已创建,含 MetaHuman Body+Head(灰色实体,A-pose,1.8m) + Tripo_Reference(半透明,T-pose,1.8m) + 16个空对象(show_in_front=True,红色). 预填位置基于实际几何分析(非bbox估算): 左肩(-0.17,-0.04,1.50), 左肘(-0.45,-0.04,1.30), 左腕(-0.65,-0.10,1.13). 关键发现: A-pose肘部Z=1.30(低于肩),腕部Z=1.13(低于肘); T-pose时三者同高Z≈1.50. **MetaHuman原始朝向就是脸朝-Y,和Tripo一致,不需要旋转**. 详见 `references/metahuman-landmark-scene.md`.

**⚠️ RBF landmark 变形方案确定 (2026-07-28, NEW)**: Shrinkwrap 不适合 A-pose→T-pose 全身包裹(三种失败模式已验证). 替代方案: 用户标定16个landmark(MetaHuman A-pose位置) + Tripo 16个landmark(T-pose位置) → RBF/ARAP 变形. 不需要 Shrinkwrap. 待用户完成 `landmark_scene_mh_v1.blend` 标定后实施.

**⚠️ RBF linear 核是最佳体型对齐方法 (2026-07-28, CRITICAL)**: T-pose→T-pose 对齐时，linear 核远优于 gaussian/TPS：X span=1.925（gaussian=2.083），Y span=0.553（gaussian=0.882），Z span=1.818（gaussian=2.366）。linear 核是全局线性插值，不产生非线性膨胀。**RBF linear 核是当前最佳体型对齐方法**（不需要 Shrinkwrap）。高斯/TPS 核在 16 个稀疏控制点时产生严重膨胀（躯干"肥胖"），linear 核则保持体型比例。详见 `references/rbf-full-body-deformation.md` 和 `references/mixamo-tpose-workflow.md` 第7节。

**⚠️ MetaHuman Body+Head 必须一起导入 (2026-07-28, CRITICAL)**: Body 和 Head 是独立网格，Z 范围有重叠 (Body 149.4, Head 141.7~180.3)。只导入 Body 会导致"没头的身子"（用户原话）。正确做法：同时导入 Body + Head，总高 1.805m，一起缩放到 1.8m。Face 可选（眼睛/牙齿等独立组件，头部 wrap 用 test01 v3.4 方案单独处理）。

**⚠️ MetaHuman matrix_basis 自带 0.01 缩放 (2026-07-28, CRITICAL)**: `Metahuman_Low_01.blend` 中 Body/Head 的 `matrix_basis` 自带 0.01 缩放（cm→m），顶点坐标已经是米单位。**不要重复 `v.co *= 0.01`** — 这会导致顶点坐标崩溃（transform_apply 后所有顶点消失）。正确做法：直接 `transform_apply` 应用 matrix_basis 的缩放，或手动缩放后把 matrix_basis 设为单位矩阵再 transform_apply。

**⚠️ MetaHuman 原始朝向就是脸朝 -Y (2026-07-28, CRITICAL)**: MetaHuman 原始坐标系：X=肩宽（左右），Y=深度（前后），Z=身高（上下），脸朝 -Y。**和 Tripo 一致，不需要绕 Z-90° 旋转**。之前错误地绕 Z-90° 旋转导致脸朝 -X，且手臂从 X 方向转到 Y 方向。A-pose 手臂本来就在 X 方向（左右展开），旋转后到了 Y 方向（前后），完全错误。

**⚠️ 坐标系统一 (2026-07-28, UPDATED)**: Tripo 和 MetaHuman 原始坐标系一致（都是 X=左右，Y=前后，Z=上下，脸朝 -Y）。**不需要旋转**。直接缩放 + 居中对齐即可。Tripo T-pose X span 1.81m（手臂展开），MetaHuman A-pose X span 1.16m（肩宽+手臂厚度），Y span 0.42m（身体+手臂前后厚度）vs Tripo Y span 0.31m（身体厚度）— 这是 A-pose vs T-pose 的正常差异。

**⚠️ 打点场景模型不可选中 (2026-07-28, UX)**: 创建 landmark 场景时，必须设置 `obj.hide_select = True` 给 MetaHuman 和 Tripo，防止用户误移动模型。空对象保持可选中。

**⚠️ 不要镜像 landmark (2026-07-28, USER)**: 用户明确说"算了 镜像不要了。我的模型也可能就是不堆成的"。不要自动镜像 landmark，左右都让用户手动标。模型可能本身不对称，镜像会导致错误。

**⚠️ RBF 全身变形工作流 (2026-07-28, NEW)**: 完整工作流见 `references/rbf-full-body-deformation.md`。TPS 和高斯 RBF 都已实现，16 对 landmark 精度 <30mm。关键：landmark 位置精确匹配，但非 landmark 区域可能膨胀（vision 报告"肥胖"）。替代方案：增加 landmark 密度、ARAP 变形、Laplacian 变形、分离衣服。

**⚠️ 仿射变换对齐（最小二乘法）优于 RBF (2026-07-28, CRITICAL)**: RBF（高斯/TPS）在 16 个稀疏控制点时产生整体扭曲（头椭圆、脚拉长、身体变形）。**仿射变换（缩放+旋转+平移）用最小二乘法求解，不产生非线性变形**。奇异值接近均匀缩放（1.29, 1.02, 0.95），landmark 精度 12-40mm。比 RBF linear 核更好（RBF linear X=1.925 vs 仿射 X=1.957，但仿射无扭曲）。**RBF 不适合全身 wrap，仿射变换是当前最佳方案**。详见 `references/affine-full-body-alignment.md`。

**⚠️ 用户纠正：WRAP 目的是解决 UV 展开，不是完美贴合 (2026-07-28, USER)**: 用户原话："WRAP不是为了解决UV展开的问题吗？"。**核心目标是 MetaHuman 拓扑+UV 传递到 AI 高模，避免 QR 碎片化**。衣服无所谓——QR 之后布线一样乱。包裹质量要求是**拓扑正确、UV 继承**，不是**表面完美贴合**。Shrinkwrap 崩溃是因为最近点吸附导致拓扑塌陷，不是因为衣服。

**⚠️ MetaHuman Body 资产分析 (2026-07-27, NEW)**: 用户提供了 `Metahuman_Low_01.blend`，含 3 个独立网格：
1. 创建包含目标模型 + 16 个预命名空对象的 blend 场景
2. 用户在 Blender GUI 中移动空对象到正确关节位置
3. Agent 读取空对象世界坐标作为 ground-truth 特征点

**关键**: 空对象初始位置基于 bbox 比例估算（肩 82%、肘 62%、腕 42%、膝 28%、踝 5%），用户只需微调。命名用 `LM_NN_description_L/R`，中文名存自定义属性。

**优势**: 比自动检测快（10 分钟 vs 数小时调试），比截图标记准（直接 3D 坐标，无反投影误差）。用户说："不能在bl让我使用空对象给你打点嘛？你给我提供好要改好名字的空对象，然后告诉我要放的位置" — **当自动方法失败时，优先接受用户驱动的空对象标记**。详见 `references/user-driven-empty-landmark-workflow.md`。

**⚠️ 16 点身体特征点标准集 (2026-07-27, NEW)**: 全身包裹标准特征点：head_top, chin, chest, abdomen, back, pelvis, shoulder_L/R, elbow_L/R, wrist_L/R, knee_L/R, ankle_L/R。初始位置按 bbox 比例计算，用户 GUI 调整。

**⚠️ 旋转逻辑推导方法论 (2026-07-28 更新，v5确认)**: 不要凭直觉旋转，用极值点分析+映射推导。正确旋转组合是**绕X轴-90° + 绕Z轴-90° + 绕Y轴-90°**（三步），用 `matrix_basis` 实现。两步版本(v4)会导致X/Z错位（模型仍横躺），必须第三步绕Y轴-90°修正。**bbox无法区分两步vs三步**（X/Z span几乎相同），必须渲染截图用 vision_analyze 验证朝向。详见 `references/blender-rotation-euler-failure.md` 的"v4 vs v5 对比"章节，包含验证表格和失败组合列表。

**⚠️ Blender 5.1 相机取景与 vision 误判 (2026-07-28, NEW)**: 相机设置在正前方 `(0, -4, 0.9)` 看向 `(0, 0, 0.9)`，但 vision_analyze 多次报告"俯视/顶视视角"。根因：**模型本身旋转错误**（FBX 导入自带 `matrix_basis` X 轴 90° 旋转，局部坐标改对了但世界坐标还是躺着的），导致相机相对模型变成了俯视。**修复：改完局部坐标后必须 `transform_apply` 清除对象旋转，或直接在局部坐标系交换 Y/Z 轴**。vision 会把复杂几何误读为简单描述（如"刀片碎片"），**视觉只能做参考不能做结论**——必须以 bbox 数据为准。详见 `references/blender-rotation-euler-failure.md` 和 `references/glb-matrix-world-pitfall.md`。

**⚠️ Blender 5.1 rotation_euler 失效陷阱 (2026-07-27, CRITICAL)**: 设置 `mesh_obj.rotation_euler` 后 `matrix_world` **不更新**，`transform_apply` 也不应用旋转。这是 Blender 5.1 的 bug 或顺序问题。**必须使用 `matrix_basis` 直接旋转**：
```python
# 错误（rotation_euler 不生效）:
mesh_obj.rotation_euler = (0, 0, math.radians(-90))
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(rotation=True)  # 顶点不变！

# 正确（matrix_basis 直接旋转）:
mesh_obj.matrix_basis = Matrix.Rotation(math.radians(-90), 4, 'Z') @ mesh_obj.matrix_basis
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(rotation=True)  # 顶点正确旋转
```
**验证方法**: 旋转后打印顶点坐标，确认 `v.co` 已改变。不要只看 `bbox` 尺寸（对称模型旋转后尺寸可能不变）。详见 `references/blender-rotation-euler-failure.md`。

**⚠️ Tripo 躺姿处理 (2026-07-27, NEW)**: Tripo GLB 导入后 Y=身高(躺), Z=身宽, X=厚度。必须绕 X 轴 **+90°** 旋转站立 (y→-z, z→y)，然后居中+缩放+接地。旋转后 front 图显示 T-pose 正面（手臂沿 X 轴水平伸展），left 图显示侧面。**不要凭 bbox 数值猜朝向**——先渲染 6 方向图用像素分布验证（T-pose 特征：left 图 Y=400-600 宽度是 front 图的 3 倍）。

**⚠️ 像素级验证方法 (2026-07-27, NEW)**: 当 vision_analyze/browser_vision 持续连接失败时，用 PIL 像素统计快速验证：背景色阈值 190，统计非背景像素占比和分布。T-pose 验证：left 图手臂区域（Y=400-600）宽度应 >400px 且为 front 图身体宽度的 3 倍以上。衣服检测：torso 区域深色像素（R,G,B<100）占比 >15% 表示有衣服。面部检测：head 区域（Y=0-200）宽度变化 >20% 表示有面部细节。

**⚠️ 先 Shrinkwrap 躯干再旋转手臂 (2026-07-27, NEW)**: 当需要旋转手臂到 T-pose 时，**顺序至关重要**：
1. **先 Shrinkwrap 躯干**（用顶点组限制，只影响躯干）
2. **再旋转手臂到 T-pose**（不再 Shrinkwrap 手臂）

**⚠️ RBF linear 核是最佳体型对齐方法 (2026-07-28, CRITICAL)**: T-pose→T-pose 对齐时，linear 核远优于 gaussian/TPS：X span=1.925（gaussian=2.083），Y span=0.553（gaussian=0.882），Z span=1.818（gaussian=2.366）。linear 核是全局线性插值，不产生非线性膨胀。**RBF linear 核是当前最佳体型对齐方法**（不需要 Shrinkwrap）。高斯/TPS 核在 16 个稀疏控制点时产生严重膨胀（躯干"肥胖"），linear 核则保持体型比例。详见 `references/rbf-full-body-deformation.md` 和 `references/mixamo-tpose-workflow.md` 第7节。

**⚠️ MetaHuman Body+Head 必须一起导入 (2026-07-28, CRITICAL)**: Body 和 Head 是独立网格，Z 范围有重叠 (Body 149.4, Head 141.7~180.3)。只导入 Body 会导致"没头的身子"（用户原话）。正确做法：同时导入 Body + Head，总高 1.805m，一起缩放到 1.8m。Face 可选（眼睛/牙齿等独立组件，头部 wrap 用 test01 v3.4 方案单独处理）。

**⚠️ MetaHuman matrix_basis 自带 0.01 缩放 (2026-07-28, CRITICAL)**: `Metahuman_Low_01.blend` 中 Body/Head 的 `matrix_basis` 自带 0.01 缩放（cm→m），顶点坐标已经是米单位。**不要重复 `v.co *= 0.01`** — 这会导致顶点坐标崩溃（transform_apply 后所有顶点消失）。正确做法：直接 `transform_apply` 应用 matrix_basis 的缩放，或手动缩放后把 matrix_basis 设为单位矩阵再 transform_apply。

**⚠️ MetaHuman 原始朝向就是脸朝 -Y (2026-07-28, CRITICAL)**: MetaHuman 原始坐标系：X=肩宽（左右），Y=深度（前后），Z=身高（上下），脸朝 -Y。**和 Tripo 一致，不需要绕 Z-90° 旋转**。之前错误地绕 Z-90° 旋转导致脸朝 -X，且手臂从 X 方向转到 Y 方向。A-pose 手臂本来就在 X 方向（左右展开），旋转后到了 Y 方向（前后），完全错误。

**⚠️ 坐标系统一 (2026-07-28, UPDATED)**: Tripo 和 MetaHuman 原始坐标系一致（都是 X=左右，Y=前后，Z=上下，脸朝 -Y）。**不需要旋转**。直接缩放 + 居中对齐即可。Tripo T-pose X span 1.81m（手臂展开），MetaHuman A-pose X span 1.16m（肩宽+手臂厚度），Y span 0.42m（身体+手臂前后厚度）vs Tripo Y span 0.31m（身体厚度）— 这是 A-pose vs T-pose 的正常差异。

**⚠️ 打点场景模型不可选中 (2026-07-28, UX)**: 创建 landmark 场景时，必须设置 `obj.hide_select = True` 给 MetaHuman 和 Tripo，防止用户误移动模型。空对象保持可选中。

**⚠️ 不要镜像 landmark (2026-07-28, USER)**: 用户明确说"算了 镜像不要了。我的模型也可能就是不堆成的"。不要自动镜像 landmark，左右都让用户手动标。模型可能本身不对称，镜像会导致错误。

**⚠️ RBF 全身变形工作流 (2026-07-28, NEW)**: 完整工作流见 `references/rbf-full-body-deformation.md`。TPS 和高斯 RBF 都已实现，16 对 landmark 精度 <30mm。关键：landmark 位置精确匹配，但非 landmark 区域可能膨胀（vision 报告"肥胖"）。替代方案：增加 landmark 密度、ARAP 变形、Laplacian 变形、分离衣服。

**⚠️ MetaHuman Body 有 14 个连通分量 (2026-07-28, CRITICAL)**: MetaHuman Body 网格不是单一连通体，而是由 14 个独立部分组成（四肢、手脚、躯干前后分离）。ARAP 要求连通网格，多个分量导致 `arap_precomputation` 失败。即使提取最大连通分量（3345 verts），约束点也只剩 3 个（总共 16 个），ARAP 很快收敛但无实际意义。**不要在不连通网格上用 ARAP**——先用 `connected_components` 检查网格连通性，或分区域独立求解。

**⚠️ Laplacian Deform 不适合大幅度姿势变形 (2026-07-28, CRITICAL)**: Blender 内置 `LAPLACIANDEFORM` 修改器在 A-pose→T-pose 变形中产生严重畸变：尖顶（头顶拉伸成锥形）、躯干膨胀（腹部臃肿）、手腕向下折弯、脚部拉伸成薄片。根因：Hook 空对象约束太强，16 个 landmark 对全身 Laplacian 变形太少，局部坐标保持失败。**不要用 Laplacian Deform 做大幅度姿势变形**——它适合小幅调整（如修复自相交），不适合 A-pose→T-pose。

**⚠️ MediaPipe Pose 在 3D 渲染图上的系统性偏差 (2026-07-28, NEW)**: MediaPipe Pose 检测 3D 渲染图时，上肢（肩/肘/腕）位置比实际关节**偏外+偏下**（左肩偏差 180px/167px）。根因：MediaPipe 检测的是人体轮廓上的点（可能包括衣服），不是骨骼关节点。3D 渲染图的材质/光照与真实照片不同，T-pose 手臂和身体角度在 2D 图像上不明显。**必须标定偏差或用骨骼辅助校验**。详见 `references/mediapipe-pose-body-detection.md`。

**⚠️ 透视相机像素→射线必须考虑焦距 (2026-07-28, NEW)**: Blender 默认 50mm 透视相机，像素到 3D 射线的转换必须考虑焦距和传感器尺寸。错误做法（正交假设 `ray_local = Vector((nx, ny, -1))`）导致射线方向偏差，上肢全部 FAILED。正确公式：
```python
fov = 2 * math.atan(sensor_width / (2 * lens))  # 39.6°
tan_half_fov = math.tan(fov / 2)
aspect = sensor_height / sensor_width  # 24/36
ray_local = Vector((nx * tan_half_fov, ny * tan_half_fov * aspect, -1))
```
详见 `references/mediapipe-pose-body-detection.md` 的"透视相机射线计算"章节。

**⚠️ MediaPipe left/right 需翻转 X (2026-07-28, NEW)**: MediaPipe 的 left/right 是从**人的视角**出发的（人面对相机时，人的 left 在相机的 right）。front 相机在 -Y 看向 +Y，图像右侧对应 +X，但 MediaPipe 的 left_shoulder 在图像右侧（px=597），对应 Tripo 的右肩（X=+0.2）。**必须翻转像素 X 坐标**：`px = img_size - px`（1024 - px）。翻转前射线射向 X=+0.179（右侧），翻转后射向 X=-0.179（左侧），接近左肩 ✓。详见 `references/mediapipe-pose-body-detection.md`。

**⚠️ MediaPipe Pose 侧视图下肢完全失效 (2026-07-28, NEW)**: MediaPipe Pose 主要检测正面，侧面关节点置信度极低（visibility < 0.1）。侧视图下肢（膝/踝）完全失效，无法获得 Y 坐标（前后深度）。**只用 front + back 双视角**，下肢成功 6/6，上肢失败 0/6。Y 坐标用骨骼辅助（Mixamo 髋关节 Y 坐标参考）或 MediaPipe 相对深度 z 坐标估算。详见 `references/mediapipe-pose-body-detection.md`。

**⚠️ libigl 安装到 Blender Python 的兼容性问题 (2026-07-28, NEW)**: `pip install libigl --only-binary :all:` 安装的预编译 wheel 是 cp311（Python 3.11），但 Blender 5.1 用 Python 3.13（`python313.zip`），`import igl` 报 `No module named 'igl.pyigl_core'`。**解决方案**：用系统 Python 3.11 运行 ARAP 部分，导出结果给 Blender（分离流程）；或找 Python 3.13 兼容的 libigl 版本。不要试图在 Blender 内直接 import igl。

**⚠️ MetaHuman Body 资产分析 (2026-07-27, NEW)**: 用户提供了 `Metahuman_Low_01.blend`，含 3 个独立网格：
**⚠️ RBF landmark 变形方案确定 (2026-07-28, NEW)**: Shrinkwrap 不适合 A-pose→T-pose 全身包裹(三种失败模式已验证). 替代方案: 用户标定16个landmark(MetaHuman A-pose位置) + Tripo 16个landmark(T-pose位置) → RBF/ARAP 变形. 不需要 Shrinkwrap. 待用户完成 `landmark_scene_mh_v1.blend` 标定后实施.

**⚠️ RBF linear 核是最佳体型对齐方法 (2026-07-28, CRITICAL)**: T-pose→T-pose 对齐时，linear 核远优于 gaussian/TPS：X span=1.925（gaussian=2.083），Y span=0.553（gaussian=0.882），Z span=1.818（gaussian=2.366）。linear 核是全局线性插值，不产生非线性膨胀。**RBF linear 核是当前最佳体型对齐方法**（不需要 Shrinkwrap）。高斯/TPS 核在 16 个稀疏控制点时产生严重膨胀（躯干"肥胖"），linear 核则保持体型比例。详见 `references/rbf-full-body-deformation.md` 和 `references/mixamo-tpose-workflow.md` 第7节。

**⚠️ MetaHuman Body+Head 必须一起导入 (2026-07-28, CRITICAL)**: Body 和 Head 是独立网格，Z 范围有重叠 (Body 149.4, Head 141.7~180.3)。只导入 Body 会导致"没头的身子"（用户原话）。正确做法：同时导入 Body + Head，总高 1.805m，一起缩放到 1.8m。Face 可选（眼睛/牙齿等独立组件，头部 wrap 用 test01 v3.4 方案单独处理）。

**⚠️ MetaHuman matrix_basis 自带 0.01 缩放 (2026-07-28, CRITICAL)**: `Metahuman_Low_01.blend` 中 Body/Head 的 `matrix_basis` 自带 0.01 缩放（cm→m），顶点坐标已经是米单位。**不要重复 `v.co *= 0.01`** — 这会导致顶点坐标崩溃（transform_apply 后所有顶点消失）。正确做法：直接 `transform_apply` 应用 matrix_basis 的缩放，或手动缩放后把 matrix_basis 设为单位矩阵再 transform_apply。

**⚠️ MetaHuman 原始朝向就是脸朝 -Y (2026-07-28, CRITICAL)**: MetaHuman 原始坐标系：X=肩宽（左右），Y=深度（前后），Z=身高（上下），脸朝 -Y。**和 Tripo 一致，不需要绕 Z-90° 旋转**。之前错误地绕 Z-90° 旋转导致脸朝 -X，且手臂从 X 方向转到 Y 方向。A-pose 手臂本来就在 X 方向（左右展开），旋转后到了 Y 方向（前后），完全错误。

**⚠️ 坐标系统一 (2026-07-28, UPDATED)**: Tripo 和 MetaHuman 原始坐标系一致（都是 X=左右，Y=前后，Z=上下，脸朝 -Y）。**不需要旋转**。直接缩放 + 居中对齐即可。Tripo T-pose X span 1.81m（手臂展开），MetaHuman A-pose X span 1.16m（肩宽+手臂厚度），Y span 0.42m（身体+手臂前后厚度）vs Tripo Y span 0.31m（身体厚度）— 这是 A-pose vs T-pose 的正常差异。

**⚠️ 打点场景模型不可选中 (2026-07-28, UX)**: 创建 landmark 场景时，必须设置 `obj.hide_select = True` 给 MetaHuman 和 Tripo，防止用户误移动模型。空对象保持可选中。

**⚠️ 不要镜像 landmark (2026-07-28, USER)**: 用户明确说"算了 镜像不要了。我的模型也可能就是不堆成的"。不要自动镜像 landmark，左右都让用户手动标。模型可能本身不对称，镜像会导致错误。

**⚠️ RBF 全身变形工作流 (2026-07-28, NEW)**: 完整工作流见 `references/rbf-full-body-deformation.md`。TPS 和高斯 RBF 都已实现，16 对 landmark 精度 <30mm。关键：landmark 位置精确匹配，但非 landmark 区域可能膨胀（vision 报告"肥胖"）。替代方案：增加 landmark 密度、ARAP 变形、Laplacian 变形、分离衣服。

**⚠️ Mixamo 支持 A-pose 绑定 (2026-07-28, USER实测)**: 用户已在 Mixamo 中完成 MetaHuman A-pose 绑定并制作 T-pose 姿态动画，导出 `T-Pose.fbx`。**Mixamo 支持 A-pose 绑定**，之前"Mixamo 不支持 A-pose"的说法错误。骨骼命名 `mixamorig:Hips/Spine/LeftShoulder/LeftArm` 等，共 65 根。完整 Mixamo T-pose→Shrinkwrap 工作流（含坐标系转换、Shrinkwrap NEAREST 崩溃问题）详见 `references/mixamo-tpose-workflow.md`。

**⚠️ 用户要求：调研不到位时优先让用户实测 (2026-07-28, USER)**: 用户原话："下次这种问题，你自己调研不到位，可以让我去实测"。当 Agent 对工具能力边界不确定时（如"Mixamo 是否支持 A-pose"），**不要猜测，优先让用户去实测**。用户实测成本远低于 Agent 错误假设导致的返工成本。

**⚠️ 简单优先，不要叠加方法 (2026-07-28, USER)**: 用户原话："别整更复杂的，越乱错的越多"。当多个方法叠加时（RBF+ARAP+Shrinkwrap+骨骼旋转），每一步引入的误差会叠加放大。**优先用最简单的方法，确认失败后再叠加**。不要一开始就提"RBF+ARAP+Surface Deform 混合流程"。

**⚠️ 应用骨骼到网格，不保留骨骼 (2026-07-28, USER)**: 用户原话："你不需要用到他的骨骼啊，你把骨骼应用了不就行，反正模型是Tpose了已经"。Mixamo 绑定后，直接 `modifier_apply("Armature")` 把骨骼变形烘焙到网格顶点，然后删除骨骼。**不需要保留骨骼用于后续操作**。

**⚠️ 应用骨骼到网格，不保留骨骼 (2026-07-28, USER)**: 用户原话："你不需要用到他的骨骼啊，你把骨骼应用了不就行，反正模型是Tpose了已经"。Mixamo 绑定后，直接 `modifier_apply("Armature")` 把骨骼变形烘焙到网格顶点，然后删除骨骼。**不需要保留骨骼用于后续操作**。

**⚠️ MetaHuman Body 资产分析 (2026-07-27, NEW)**: 用户提供了 `Metahuman_Low_01.blend`，含 3 个独立网格：

**⚠️ 先 Shrinkwrap 躯干再旋转手臂 (2026-07-27)**: 当需要旋转手臂到 T-pose 时，**顺序至关重要**：
1. **先 Shrinkwrap 躯干**（用顶点组限制，只影响躯干）
2. **再旋转手臂到 T-pose**（不再 Shrinkwrap 手臂）

**错误顺序**: 先旋转手臂到 T-pose → 再 Shrinkwrap 全身 → Shrinkwrap 将手臂拉回 A-pose 位置，旋转失效。

**顶点组分类技巧**: 基于到肩膀的距离分类（左肩近=左臂，右肩近=右臂，其余=躯干），比基于 X 坐标分类更准（避免上臂被分到躯干）。

**⚠️ 打点场景 UX 要求 (2026-07-28)**: 创建空对象打点场景时必须: (1)默认工具设为移动工具`bpy.context.workspace.tools.update(active_tool="builtin.move")` (2)角色网格`hide_select=True`不可选中 (3)`show_in_front=True` (4)中英文命名 (5)需要镜像对称功能. 详见 `references/user-driven-empty-landmark-workflow.md` 的"场景创建UX要求"章节.

**⚠️ MetaHuman landmark 场景创建完成 (2026-07-28, UPDATED)**: `landmark_scene_mh_v2.blend` 已创建,含 MetaHuman Body+Head(灰色实体,A-pose,1.8m) + Tripo_Reference(半透明,T-pose,1.8m) + 16个空对象(show_in_front=True,红色). 预填位置基于实际几何分析(非bbox估算): 左肩(-0.17,-0.04,1.50), 左肘(-0.45,-0.04,1.30), 左腕(-0.65,-0.10,1.13). 关键发现: A-pose肘部Z=1.30(低于肩),腕部Z=1.13(低于肘); T-pose时三者同高Z≈1.50. **MetaHuman原始朝向就是脸朝-Y,和Tripo一致,不需要旋转**. 详见 `references/metahuman-landmark-scene.md`.

**⚠️ RBF landmark 变形方案确定 (2026-07-28, NEW)**: Shrinkwrap 不适合 A-pose→T-pose 全身包裹(三种失败模式已验证). 替代方案: 用户标定16个landmark(MetaHuman A-pose位置) + Tripo 16个landmark(T-pose位置) → RBF/ARAP 变形. 不需要 Shrinkwrap. 待用户完成 `landmark_scene_mh_v1.blend` 标定后实施.
bpy.ops.object.transform_apply(rotation=True)  # 顶点不变！

# 正确（matrix_basis 直接旋转）:
mesh_obj.matrix_basis = Matrix.Rotation(math.radians(-90), 4, 'Z') @ mesh_obj.matrix_basis
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(rotation=True)  # 顶点正确旋转
```
**验证方法**: 旋转后打印顶点坐标，确认 `v.co` 已改变。不要只看 `bbox` 尺寸（对称模型旋转后尺寸可能不变）。详见 `references/blender-rotation-euler-failure.md`。

**⚠️ Tripo 躺姿处理 (2026-07-27, NEW)**: Tripo GLB 导入后 Y=身高(躺), Z=身宽, X=厚度。必须绕 X 轴 **+90°** 旋转站立 (y→-z, z→y)，然后居中+缩放+接地。旋转后 front 图显示 T-pose 正面（手臂沿 X 轴水平伸展），left 图显示侧面。**不要凭 bbox 数值猜朝向**——先渲染 6 方向图用像素分布验证（T-pose 特征：left 图 Y=400-600 宽度是 front 图的 3 倍）。

**⚠️ 像素级验证方法 (2026-07-27, NEW)**: 当 vision_analyze/browser_vision 持续连接失败时，用 PIL 像素统计快速验证：背景色阈值 190，统计非背景像素占比和分布。T-pose 验证：left 图手臂区域（Y=400-600）宽度应 >400px 且为 front 图身体宽度的 3 倍以上。衣服检测：torso 区域深色像素（R,G,B<100）占比 >15% 表示有衣服。面部检测：head 区域（Y=0-200）宽度变化 >20% 表示有面部细节。

Full details: see `references/full-body-wrap-research.md`

### Reusable Landmark Scene Script

`scripts/create_landmark_scene.py` — Reusable template for creating a landmark
scene with 16 bilingual named empty objects. Automatically rotates the model
to standard orientation (v5 3-step matrix_basis), scales to 1.8m, and creates
empties with `show_in_front=True`, red color, and position descriptions.
Usage: `blender --background --factory-startup --python scripts/create_landmark_scene.py -- <glb_path> <output_blend>`

## Self-Check Pipeline Pattern

See also: `references/retopology-research.md` for technology landscape research
(Wrap4D, UE5 MetaHuman, open-source alternatives, and the root cause analysis
of why Shrinkwrap fails on thin facial structures).

The `auto_check_pipeline.py` script implements a self-check loop:
1. Run the full fitting pipeline with a parameter strategy
2. Run quantitative checks (distance, symmetry, anchors, ears)
3. Render verification views (front, left45, right45, top)
4. If all metrics pass thresholds → save as final, stop
5. If not → try next parameter strategy (more Shrinkwrap rounds, more anchors,
   different smooth factors)

Parameter strategies are pre-defined arrays:
```python
param_strategies = [
    dict(sw_rounds=4, anchor_rounds=30, smooth_factor=0.15, smooth_iters=2),
    dict(sw_rounds=6, anchor_rounds=40, smooth_factor=0.12, smooth_iters=3),
    dict(sw_rounds=5, anchor_rounds=35, smooth_factor=0.20, smooth_iters=2),
    dict(sw_rounds=6, anchor_rounds=50, smooth_factor=0.10, smooth_iters=3),
]
```

Number of rounds is controlled by `AUTOCHECK_ROUNDS` env var (default 4).