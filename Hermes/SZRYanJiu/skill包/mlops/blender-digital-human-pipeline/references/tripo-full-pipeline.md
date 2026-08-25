# Tripo AI Full Pipeline — Production Decisions

## Route Decision
- Route 1 (Camera Matrix): 60-200 cameras, ¥50万+, studio, team. **Infeasible** (zero budget, solo).
- Route 2 (AI Gen): Tripo AI / Meshy / Rodin. Free tier. **Adopted.**

## Key Technical Challenges

### Clothes Removal  [REVISED 2026-07-08 — see clothing-hair-removal-research.md]
Tripo generates clothed models; binding requires nude.

**Original decision (now superseded)**: volumetric cut only — standard nude
body template → dilate 5-10mm → filter vertices inside → delete outside.
This was evaluated as the sole method with AI segmentation dismissed as
"inaccurate".

**Revised decision after feasibility research**:
- Volumetric Boolean cut **only works for tight clothing** (1-3cm error,
  needs pose alignment via PARE/OSX or manual). Pre-clean mesh first
  (Tripo topology is non-manifold → Boolean fails without cleanup).
- Boolean **FAILS for loose clothing** (coats, skirts, dresses): Tripo
  meshes are single-surface — there is no body geometry under loose
  clothes, so Boolean cannot "reveal" a body that isn't there.
- **Recommended primary method: AI segmentation** (2D SAM/U2Net/SCHP
  multi-view render → 3D face projection + multi-view voting → delete
  "clothing" faces). Expected ~80-85% face-level accuracy.
- For large gaps where geometry is entirely missing: **transplant
  corresponding region from SMPL template** (select by body-region
  position, copy faces, merge boundary, Shrinkwrap+smooth to blend).
- Geometric hole repair after deletion: bmesh holes_fill (small) +
  Shrinkwrap to body template (medium) + Laplacian smooth (seams).

### Hair & Eyelash Removal  [REVISED 2026-07-08]
AI generates solid hair blocks that cause animation tearing. Hair should
be Groom (UE5), not geometry.

**Original decision (now superseded)**: MediaPipe 478 face points → scalp
surface → distance >5mm = delete. Single-method approach.

**Revised decision after feasibility research**:
- Distance-from-scalp alone is **unreliable for long hair** (falls to
  shoulders/back, far from scalp but so is shoulder skin → false positives).
- Distance threshold is **unreliable for eyelashes** (1-3mm, overlaps with
  eyelid geometry, hard to separate).
- **Recommended: multi-feature fusion**:
  1. Color/texture analysis (primary): dark hair/eyebrows/eyelashes vs
     flesh-tone skin. Sample texture at vertex UV, classify by brightness
     + saturation. High reliability for dark hair, medium for light/dyed.
  2. Curvature/normal analysis (secondary): hair = high-frequency
     filaments (high curvature), skin = smooth. Compute per-vertex normal
     deviation from neighbor mean. Restrict to head region (nose/ears/
     lips are also high-curvature → false positives).
  3. Distance-from-scalp threshold (fallback only): for no-texture models,
     combine with curvature + normal direction.
- **SOTA**: Pixels2Points (arXiv:2504.19718, Eurographics 2025) fuses 2D
  image features (frozen DINO) with 3D geometric features → predicts
  skin vs non-skin (hair/beard/accessories) directly on mesh. +8.89% over
  pure 2D, +14.3% over pure 3D. Needs external PyTorch inference.
- **Eyelashes specifically**: correlate color with detected hair color,
  apply fine curvature filter within eyelid region only, manual confirm.

### Body Symmetrization
AI meshes are asymmetric → unnatural animation. PCA mirror + average body, but keep face asymmetric (natural).

### Topology Impact on Binding
Clothes/hair have chaotic edge flow → bone rotation causes torn faces. Must remove ALL non-body geometry before retopology. Clean quad topology is prerequisite for binding.

## Pipeline (7 stages)
Photos → Tripo GLB → Geo Prep (voxel+clothes+hair+symmetry) → Quad Remesher (30-50K) → UV+Bake → ARKit 52 (Auto-Rig Pro) → Mixamo body → Export GLB

## Dual Delivery
Paid: Quad Remesher + Auto-Rig Pro. Free fallback: Instant Meshes + Mixamo. Auto-detect + fallback.

## Documentation for Leadership
- Output .docx, not .md (boss reads Word)
- Concise: explain the important, skip trivia
- NEVER "领导要求" or "the boss requires" — this doc IS for the boss
- Rephrase ideas professionally, don't quote raw user thoughts
- Python-docx: use 2-3 small sequential .py scripts to avoid stream timeout (<3K tokens each)