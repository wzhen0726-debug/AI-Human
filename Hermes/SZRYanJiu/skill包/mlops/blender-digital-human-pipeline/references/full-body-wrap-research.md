# Full-Body Wrap: Standard Low-Poly Template Feasibility

Research date: 2026-07-08. Companion to `blender-head-retopology/references/full-body-wrap-research.md`.

## Core Question

Can the head retopology pipeline (MediaPipe landmarks → Shrinkwrap → standard
template) be extended to full body (head + body + hands + feet)?

## Template

**The user provides the template model themselves.** It does NOT need to be
MetaHuman specifically — any well-topologized low-poly body with standard edge
loops (facial rings, joint deformation loops, symmetric topology) will work.
The user confirmed: "想要什么都可以" — can export from UE5, hand-stitch, or
source third-party. In documents, use "标准低模模板" (standard low-poly template),
NOT "MetaHuman."

### character-dna-addon (poly-hammer, 257★, GPL v3)
- https://github.com/poly-hammer/character-dna-addon
- Imports MetaHuman **head AND body** from `.dna` files into Blender
- Free base version supports full import/export + OpenRigLogic
- Compatible UE 5.6/5.7 DNA files, Blender 4.5/5.1
- **This is the tool for getting MetaHuman body topology without UE5** (if needed)

### SMPLify-X (vchoutas, 2147★)
- https://github.com/vchoutas/smplify-x
- SMPL-X: 10,475 vertices, 54 joints, 127 keypoints (AGORA dataset)
- Single image → body pose + hand pose + face expression
- **Non-commercial license** — use MediaPipe Holistic for commercial work

### MediaPipe Holistic
- Face (468) + body (33 3D) + hands (21×2) keypoints
- Fully open source, commercially usable
- Less accurate 3D than SMPL-X but license-safe

## SMPL-X vs MetaHuman Body Topology

| Property | SMPL-X | MetaHuman Body |
|----------|--------|----------------|
| Vertices | 10,475 | ~20K-30K+ (est.) |
| Joints | 54 | ~70+ (full skeleton) |
| Hands | Yes (finger joints) | Yes (knuckle detail) |
| Feet | Limited | Yes (toe detail) |
| License | Non-commercial | Free (via MetaHuman Creator) |
| Open mesh | No (registration required) | Via character-dna-addon |

## Body Alignment Strategy

The head pipeline relies on MediaPipe's 478 dense 3D facial landmarks. The body
has no equivalent. Recommended approach:

1. Detect sparse body joints (shoulder, elbow, wrist, hip, knee, ankle) via
   SMPLify-X or MediaPipe Holistic
2. Fit SMPL-X parametric model to the AI high-poly mesh (provides dense
   vertex correspondences)
3. Use SMPL-X vertex-to-joint map to establish coarse alignment with
   MetaHuman template skeleton
4. Region-by-region Shrinkwrap: torso/limbs (easy, 1-3mm), hands/fingers
   (hard, 5-10mm, may need manual fix)

## Precision Expectations

| Region | Mean | <1mm | Notes |
|--------|------|------|-------|
| Torso/limbs | 1-3mm | 85-95% | Simple curvature, Shrinkwrap works well |
| Hands/fingers | 5-10mm | 50-70% | High curvature, self-intersection risk |
| Joint creases | 5-15mm | varies | Axilla, groin, finger webs — may need manual |
| Feet/toes | 3-8mm | 60-80% | Moderate complexity |
| Head | 0.4mm | 96% | Existing pipeline (for reference) |

## Recommended Pipeline

```
MetaHuman body template (already available, no acquisition needed)
AI high-poly mesh → render reference views
  → MediaPipe Holistic (commercial) or SMPLify-X (research, non-commercial)
  → body keypoints + pose parameters
  → coarse skeletal alignment (ICP on joint points)
  → pose normalization (if AI mesh not in T-pose)
  → region-by-region Shrinkwrap:
      head: existing MediaPipe 468pt pipeline (0.4mm)
      torso/limbs: direct Shrinkwrap (1-3mm)
      hands/fingers: extra anchors + manual correction
  → post-process: fix penetrations, smooth region transitions
```

## Risks

- SMPL-X non-commercial license blocks commercial use
- Finger/toe precision likely insufficient without manual cleanup
- MetaHuman DNA still needs MetaHuman Creator + Epic account
- AI mesh pose normalization adds complexity (SMPL-X pose params can help)
