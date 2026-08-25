# Full-Body Wrap Research: MetaHuman Body Template + SMPL-X Landmarks

Research date: 2026-07-08. Investigated feasibility of extending the head-only
retopology pipeline to full-body (head + body + hands + feet) using MetaHuman's
complete body template.

## 1. MetaHuman Body Topology

- MetaHuman uses **separate head and body meshes** unified by a skeletal rig.
- Head mesh: ~8K vertices (already used in head pipeline).
- Body mesh (incl. hands, feet): exact vertex count **not publicly documented**.
  Industry estimate: **20K-30K+ vertices** based on comparable production rigs.
- Body mesh includes: torso, arms, fingers (with knuckle joints), legs, toes,
  eyeballs. All quad topology with animation-ready edge loops.
- **To get the exact count**: export via `character-dna-addon` (below) and count
  vertices in Blender (`len(mesh.vertices)`).

## 2. Open-Source MetaHuman Body Template Access

### character-dna-addon (poly-hammer, 257★, GPL v3)
- **GitHub**: https://github.com/poly-hammer/character-dna-addon
- Imports MetaHuman **head AND body** components from `.dna` files into Blender
- Free base version: full import/export of `.dna` files, OpenRigLogic integration
- Pro version (paid): advanced DNA editors for full pipeline replacement
- Compatible with UE 5.6/5.7 MetaHuman DNA files
- Supports Blender 4.5 and 5.1 (Windows/Linux/macOS arm64)
- **This is the key tool for obtaining a MetaHuman body template without UE5**
- Bundles Epic's OpenRigLogic (MIT license)

### Other tools
- `Heaverno/metahuman-DNA-Blender-tools` (15★): Read/write MetaHuman DNA in Blender
- `MetaReForgeLite` (6★): Editing MetaHumans in Blender
- `HakanErunsal/MetahumanToManny` (14★): Convert MetaHuman skeletal mesh to Manny skeleton

### Limitation
Still requires MetaHuman Creator (free, needs Epic account) to generate the
initial DNA file. No fully independent body template mesh is publicly available.

## 3. Full-Body Landmark Detection

### SMPLify-X (vchoutas/smplify-x, 2147★)
- **GitHub**: https://github.com/vchoutas/smplify-x
- Paper: arXiv 1904.05866 "Expressive Body Capture: 3D Hands, Face, and Body"
- SMPL-X model: **N=10,475 vertices, K=54 joints** (neck, jaw, eyeballs, fingers)
- AGORA dataset uses SMPLX skeleton: **127 keypoints** (excl. 17 face contour points)
- Computes body pose, hand pose, facial expression from a single RGB image
- **License: non-commercial scientific research only** — cannot use commercially
- PyPI: `pip install smplx[all]`
- Model download requires registration at https://smpl-x.is.tue.mpg.de

### MediaPipe Holistic
- Detects face (468 pts) + body pose (33 3D keypoints) + hands (21 pts × 2)
- Fully open source, **commercially usable**
- Provides 2D/pseudo-3D keypoints (less accurate than SMPL-X's 3D fitting)
- GitHub projects: `morphix` (browser-based real-time mocap with MediaPipe Holistic)
- **This is the commercial-safe option for body landmark detection**

### SMPL Mesh Registration (xthan/smplreg, 33★)
- Registration between reconstructed point cloud and estimated SMPL mesh
- Directly addresses 3D mesh alignment problem
- Could bridge: point cloud from AI mesh → SMPL mesh → template alignment

### Other pose estimators
- OpenPose / MMPose / ViTPose: 2D body keypoints (COCO 133pt / COCO 17pt)
- MobilePoser (142★): Full-body pose from IMUs
- Need multi-view or depth estimation for 3D coordinates

## 4. Body Alignment Challenge

Unlike the head (where MediaPipe provides 478 3D facial landmarks), the body
has **no equivalent dense 3D landmark detector**. Alignment strategies:

1. **Skeletal joint points**: Detect 2D/3D body joints (shoulder, elbow, wrist,
   hip, knee, ankle) as anchor points — sparse but anatomically meaningful
2. **SMPL-X parametric fitting**: Fit SMPL-X to the high-poly mesh first, then
   use SMPL-X's known vertex-to-joint correspondences to guide template alignment
3. **Region-by-region Shrinkwrap**: Split body into torso, arms, hands, feet,
   head — each region wrapped independently with region-specific anchors
4. **Manual anchor points**: Place a small number of anchors at anatomical
   landmarks (fingertips, elbow olecranon, knee patella, toe tips, etc.)

## 5. Precision Expectations

### Favorable factors
- Body surfaces (torso, limbs) are far simpler than face — low curvature, few details
- Large smooth areas are ideal for Shrinkwrap NEAREST
- AI-generated high-poly meshes (uniform tessellation) wrap well

### Unfavorable factors
- **Fingers/toes**: high curvature, dense detail, self-intersection risk — main difficulty
- **Joint creases** (axilla, groin, finger webs): Shrinkwrap may penetrate
- **Large surface area**: requires T-pose or A-pose alignment; pose mismatch is critical
- **AI mesh pose**: may not be standard T-pose — needs pose normalization first

### Expected precision
| Region | Expected mean | Expected <1mm |
|--------|--------------|--------------|
| Torso/limbs (smooth) | 1-3mm | 85-95% |
| Hands/fingers | 5-10mm | 50-70% |
| Joint creases | 5-15mm | may need manual fix |
| Feet/toes | 3-8mm | 60-80% |
| Head (existing pipeline) | 0.4mm | 96% |

### Shrinkwrap suitability
Blender Shrinkwrap modifier CAN handle full body, but requires:
- Coarse alignment first (via keypoints/skeletal transform)
- Reasonable Offset and Subdivision levels
- Region-specific operation for hands/fingers
- Post-processing for penetration in concave areas

## 6. Open-Source Full-Body Wrap Tools

| Tool | Stars | Type | Fit for full-body wrap |
|------|-------|------|----------------------|
| RetopoFlow (CGCookie) | 3.1k | Blender addon | Manual/semi-auto retopo, not auto-wrap |
| AutoRemesher (huxingyi) | 1.8k | Auto quad remesh | Auto remesh, NOT template-wrap |
| character-dna-addon | 257 | MH DNA→Blender | **Template source** (get MH body mesh) |
| smplreg (xthan) | 33 | SMPL mesh registration | Point cloud→SMPL alignment |
| SMPLify-X (vchoutas) | 2.1k | Single image→SMPL-X | Body keypoint/pose source |
| Blender Shrinkwrap | built-in | Mesh wrapping | Actual wrap operation |
| Faceform Wrap | commercial | Pro wrap tool | Industry standard, not open source |

**No single open-source tool provides "full-body template wrap" in one step.**
The viable approach is a multi-tool pipeline (see Recommended Route below).

## 7. Recommended Technical Route

1. **Get template**: MetaHuman Creator (free) → `character-dna-addon` → export
   body mesh to Blender → obtain vertex count and topology
2. **Detect keypoints**: Render AI high-poly model → SMPLify-X (research) or
   MediaPipe Holistic (commercial) → detect full-body landmarks
3. **Coarse alignment**: Use detected keypoints + MetaHuman template skeleton
   joints → ICP or rigid alignment
4. **Pose adaptation**: Bind template skeleton to detected pose → deform template
   mesh to roughly match high-poly model
5. **Region-by-region Shrinkwrap**:
   - Head: MediaPipe 468pt + Shrinkwrap (existing pipeline, 0.4mm)
   - Torso/limbs: direct Shrinkwrap, 1-3mm expected
   - Hands/fingers: extra anchors or manual correction needed
6. **Post-process**: Fix penetrations, smooth transitions between regions

## 8. Key Risks

- **SMPL-X license**: non-commercial only. For commercial use, MediaPipe Holistic
  is the safe alternative (less accurate but license-free)
- **Finger/toe wrap precision**: likely needs manual intervention
- **MetaHuman DNA access**: still requires MetaHuman Creator + Epic account
- **Pose normalization**: AI meshes may not be in T-pose; SMPL-X fitting can
  provide pose parameters for normalization
