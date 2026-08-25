# Clothes/Hair/Eyelash Removal — Technical Feasibility Research

Research session: 2026-07-08. Source: arXiv + GitHub survey + existing
blender-head-retopology Shrinkwrap experience.

## (1) Volumetric Boolean Cut with Body Template

**Status: PARTIALLY VIABLE — fails on loose clothing.**

- **Tight clothing** (T-shirt, pants): Boolean DIFFERENCE/INTERSECT with SMPL
  template works, ~1-3cm error. Needs pose alignment first.
- **Loose clothing** (coats, skirts, dresses): **FAILS.** Tripo AI models are
  single-surface meshes — there is NO body geometry under the clothes.
  Boolean cannot create geometry that doesn't exist. The space under a coat
  or skirt is empty.
- **Root limitation**: Boolean assumes the clothed mesh contains complete body
  geometry internally. True for tight clothing, false for loose.
- **Blender API**: Boolean modifier with solver='EXACT'. Pre-clean mesh
  (non-manifold/self-intersecting Tripo meshes cause Boolean failures).
- **Recommendation**: Use as a rough first pass only. Must pair with body
  template face transplantation for areas where geometry is missing.

## (2) AI Segmentation of Clothing Regions

**Status: VIABLE — recommended primary approach.**

### Approach A: 2D Segmentation → 3D Face Projection (zero-cost, recommended)
1. Render 6-8 views from Blender (front/side/back/angles)
2. Run 2D segmentation: SAM (Segment Anything), U2Net/IS-Net (fashion),
   SCHP/PP-HumanSeg (18-class body parsing: top/coat/skirt/pants/face/hair...)
3. Project 2D masks back to 3D mesh faces via camera ray-cast
4. Multi-view voting: each face accumulates votes across visible views
5. Delete faces labeled "clothing"

Expected accuracy: 80-85% at face level after multi-view voting.
2D parsing mIoU is 85-90% on LIP/ATR datasets; 3D projection loses some
at occlusion boundaries.

### Approach B: 3D Point Cloud Segmentation (higher precision, needs training)
- PointNet/PointNet++ / Point Transformer on the mesh-as-point-cloud
- **arXiv:2508.05531** (2025): "Clothed Human Layering" — predicts both
  visible clothing AND occluded body regions. Exactly what's needed for
  geometry reconstruction under clothes. Trained on CAPE dataset.
- Needs PyTorch + GPU inference (external to Blender).

### Approach C: Pixels2Points (arXiv:2504.19718, Eurographics 2025)
- Fuses 2D image features (frozen DINO) with 3D geometric features
- Predicts skin vs non-skin (hair/beard/accessories) directly on mesh
- +8.89% over pure 2D, +14.3% over pure 3D segmentation
- Generalizes to real data despite synthetic-only training

### Key papers
- arXiv:2508.06032 (AAAI 2026): Spectrum — texture-aware clothing parsing
- arXiv:2309.16189: Cloth2Body — 2D clothing → 3D body mesh
- arXiv:2512.17545: ClothHMR — diverse clothing mesh recovery

## (3) Hair & Eyelash Removal

**Status: VIABLE with multi-feature fusion. No single method is sufficient.**

### Method A: Distance Threshold from Scalp Template
- Fit head template, delete vertices >5-10mm from scalp surface
- **Short hair**: reliable. **Long hair**: unreliable (falls to shoulders/back,
  far from scalp but so is shoulder skin → false positives)
- **Eyelashes**: unreliable (1-3mm, indistinguishable from eyelid)

### Method B: Curvature/Normal Analysis
- Hair = high-frequency filament structure (high curvature)
- Skin = smooth surface (low curvature)
- Compute per-vertex normal deviation from neighbor mean
- **Hair**: medium-high reliability. **Eyelashes**: low (overlaps with
  eyelid edge/eyebrow curvature)
- Must restrict to head region (nose/ears/lips are also high-curvature)

### Method C: Color/Texture (MOST EFFECTIVE when texture exists)
- Tripo models have texture maps. Hair/eyebrows/eyelashes are dark
  (low brightness, low saturation). Skin is flesh-toned (R>G>B, bright).
- Sample texture at each vertex UV → classify by color
- **Dark hair**: high reliability. **Blonde/light hair**: medium.
  **Dyed hair**: low (needs clustering first)
- **Eyelashes**: medium (same color as hair, can correlate)
- Risk: dark clothing, dark eyes, shadows → false positives

### Method D: Pixels2Points (SOTA, needs external inference)
- See section (2) Approach C. Directly designed for this problem.

### Recommended fusion strategy
Hair: color (primary) + curvature (secondary) + spatial filter (head region)
Eyelashes: color (correlate with hair) + fine curvature in eyelid region only
No-texture fallback: distance threshold + curvature + normal direction

## (4) Geometric Hole Repair After Deletion

**Status: HIGHLY AUTOMATABLE — most controllable stage.**

### Small holes (<5cm, <50 boundary verts): bmesh holes_fill
```python
bmesh.ops.holes_fill(bm, sides=64)
```

### Medium holes (clothing regions): fill + Shrinkwrap to body template
1. holes_fill for initial faces (rough)
2. Shrinkwrap modifier (NEAREST_SURFACEPOINT, OUTSIDE_SURFACE, offset=1mm)
   → snaps patch faces to body template surface
3. Laplacian Smooth (5 iters, lambda=0.3) → blends seams
This is the SAME Shrinkwrap technique validated in blender-head-retopology
(0.4mm accuracy on head fitting).

### Large holes (entire torso missing): transplant from SMPL template
- Delete bad region → select corresponding region on SMPL by position
- Copy faces, merge by boundary, Shrinkwrap + smooth to blend
- This is NOT repair — it's replacement from a template.

### Voxel Remesh / Poisson Reconstruction (alternative)
- Voxel Remesh: bpy.ops.object.voxel_remesh(voxel_size=0.005)
- Poisson: needs Open3D externally (create_from_point_cloud_poisson, depth=9)
- Good for topology-agnostic resurfacing but loses UV/texture

## (5) Blender Python Implementability

### Fully scriptable (pure Blender Python)
- Multi-view rendering, bmesh operations, Boolean, Shrinkwrap, Laplacian
  Smooth, BVHTree ray_cast/find_nearest, KDTree, UV texture sampling,
  curvature computation, Voxel Remesh

### Needs external preprocessing (Blender-external Python, output → Blender)
- 2D AI segmentation (SAM/U2Net/SCHP): PyTorch inference → mask images
- 3D point cloud segmentation: PyTorch3D/Open3D
- Poisson reconstruction: Open3D
- SMPL fitting: smplx Python package

### Architecture
External Python → mask images / labels → Blender Python (voting, deletion,
repair, export). Can chain via subprocess or file I/O.

## Revised Difficulty Assessment

| Sub-task | Difficulty | Bottleneck |
|----------|-----------|------------|
| Boolean cut (tight clothes) | Medium | Pose alignment |
| Boolean cut (loose clothes) | **Blocked** | No body geometry under clothes |
| AI clothing segmentation | Medium | 2D→3D projection accuracy at boundaries |
| Hair removal (color) | Low-Medium | Texture quality, hair color variety |
| Eyelash removal | Medium-High | Tiny structure, overlaps eyelid |
| Hole repair (small/medium) | Low | Well-understood bmesh+Shrinkwrap |
| Large area body reconstruction | **Hard** | Must transplant from SMPL, needs precise pose |
| Full pipeline integration | Medium | Threshold tuning, boundary cleanup |

## Previous Skill's Hardcoded Decisions — Now Revised

The Tripo full pipeline section of blender-digital-human-pipeline SKILL.md
previously stated:
- "Clothes removal: volumetric cut, not AI segmentation" → REVISED: AI
  segmentation is the recommended primary; volumetric cut only for tight clothes
- "Hair/eyelash removal: distance-from-scalp (5mm), not AI-based" → REVISED:
  distance threshold alone is unreliable for long hair and eyelashes;
  use color/curvature fusion as primary
