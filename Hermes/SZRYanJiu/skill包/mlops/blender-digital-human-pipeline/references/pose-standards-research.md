# Pose Standards for Digital Human Rigging — Research Findings

Compiled 2026-07-08. Sources: Wikipedia (T-pose article), Mixamo official site, MediaPipe GitHub source code (pose.py), Blender 5.1 manual, MetaHuman documentation references, Reallusion documentation.

## 1. T-pose vs A-pose: Definitions and Tradeoffs

### T-pose
- Arms horizontal, 90° from body, forming a capital "T"
- The standard default bind pose in most 3D animation software
- Wikipedia: "The purpose of the T-pose relates to the important elements of the body being **axis-aligned**, thereby making it easier to rig the model for animation, physics, and other controls."
- Also the standard motion capture calibration pose
- **Advantage**: axis alignment simplifies rigging, IK setup, physics
- **Disadvantage**: shoulder region deformation is worst-case (arms rotate 90° from T to rest), can cause visible pinching

### A-pose
- Arms angled downward ~45° (some sources say 15-20° for MetaHuman variant), forming an "A"
- More natural resting position
- **Advantage**: shoulder deformation is more natural, less weight-painting required, less arm-torso interpenetration
- **Disadvantage**: not fully axis-aligned, some auto-rigging tools don't expect it

### Y-pose
- Arms angled upward — rarely used, mentioned for completeness (Wikipedia)

## 2. Mixamo (Adobe) — "Default or Neutral Pose" (T-pose Recommended)

### Official source (verified 2026-07-08)
Adobe helpx Mixamo FAQ: https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html
(via Web Archive — direct access returns HTTP2 errors in China)

Official wording: "The character is in a **default or neutral pose**. Auto-rigging may not work if the character is largely asymmetric or posed prior to rigging."

Full 7-point requirement list:
1. Humanoid with distinguishable head, body, arm, leg areas
2. No large appendages/props (wings, tails, large hair/clothing)
3. **Default or neutral pose** — not pre-posed, not largely asymmetric
4. No other content in file (cameras, helpers, scene objects)
5. No gaps between body parts (e.g., floating head disjoined from body)
6. Character centered at scene origin (0,0,0)
7. Clean, error-free mesh

### Analysis
- **The official FAQ does NOT use the word "T-pose"** — it says "default or neutral pose"
- All Mixamo built-in character templates ARE in T-pose
- Auto-detection assumes arms ~horizontal (T-pose) for joint identification
- Community practice: **T-pose has highest success rate**; light A-pose (arms 30-45°) often works; arms too low (near body) = misdetected as "non-default"
- **Recommendation: use T-pose for Mixamo.** If A-pose fails, reset to T-pose and retry.

**Correction note**: A previous version of this section claimed "Mixamo strictly requires T-pose (arms horizontal 90°)." This overclaimed — the official wording is "default or neutral pose," which in practice means T-pose works best but is not a hard documented requirement.

## 3. MetaHuman (Epic Games) — A-pose

- MetaHuman Creator generates characters in **A-pose** (arms slightly away from body, ~15-20°)
- MetaHuman Identity (Mesh to MetaHuman) requires input meshes close to A-pose
- MetaHuman's body skeleton system is designed around A-pose for better shoulder deformation
- Facial system uses full ARKit 52 BlendShape-compatible expression set
- Custom mesh input requires: front-facing head, neutral expression, eyes open

## 4. ARKit 52 BlendShape — Facial Requirements (face-only, no body pose)

### Official source (verified 2026-07-08)
- ARFaceAnchor.BlendShapeLocation: https://developer.apple.com/documentation/arkit/arfaceanchor/blendshapelocation
- Rigging a Model for Motion Capture: https://developer.apple.com/documentation/arkit/rigging-a-model-for-motion-capture
- Validating a Model for Motion Capture: https://developer.apple.com/documentation/arkit/validating-a-model-for-motion-capture

### Key finding: face vs body are TWO DIFFERENT requirements

**ARKit 52 BlendShape (pure facial, ARFaceAnchor)**:
- 52 coefficients are pure facial expression morph targets — **no body pose requirement**
- Each coefficient: 0.0 = neutral, 1.0 = maximum movement
- Covers: left/right eye (7 each), mouth & jaw, brows, cheeks, nose, tongue
- Naming: left/right relative to the FACE itself (face's right = screen right, front camera mirrors)
- **Requirement: face mesh built on neutral expression** (eyes open, mouth closed, no expression)
- Head must be front-facing and upright for bilateral symmetry

**ARKit body mocap (ARBodyAnchor) — REQUIRES T-pose**:
Official docs explicitly state:
> "Your characters should be rigged in a standard T-pose." (Validating a Model for Motion Capture)
> "You should model your mesh in a standard T-pose." (Rigging a Model for Motion Capture)
> "Your character should be modeled in a T-pose, your scene should contain only one bind pose" (Rigging a Model for Motion Capture)

Additional ARKit body mocap requirements:
- Coordinate system: +Y up, +Z forward, +X right
- Model faces +Z axis (forward)
- Skeleton joint names must exactly match ARKit spec (hips_joint, spine_1_joint, spine_2_joint... head_joint, left_arm_joint, etc.)
- Max 4 joint influences per vertex
- No animation keyframes
- Full joint hierarchy: 8 torso + 4 neck/head + 3 arm×2 + 5 leg×2 + full hand joints

### Conclusion
- **Pure facial BlendShape: no body pose requirement, but face needs neutral expression**
- **Body mocap: MUST be T-pose**
- Digital human projects usually combine both → use **T-pose + neutral face** for maximum compatibility

## 5. MediaPipe Pose Landmarks (33 points) — Verified from Source

Source: `mediapipe/python/solutions/pose.py` (Google AI Edge, master branch)

```
NOSE = 0
LEFT_EYE_INNER = 1, LEFT_EYE = 2, LEFT_EYE_OUTER = 3
RIGHT_EYE_INNER = 4, RIGHT_EYE = 5, RIGHT_EYE_OUTER = 6
LEFT_EAR = 7, RIGHT_EAR = 8
MOUTH_LEFT = 9, MOUTH_RIGHT = 10
LEFT_SHOULDER = 11, RIGHT_SHOULDER = 12
LEFT_ELBOW = 13, RIGHT_ELBOW = 14
LEFT_WRIST = 15, RIGHT_WRIST = 16
LEFT_PINKY = 17, RIGHT_PINKY = 18
LEFT_INDEX = 19, RIGHT_INDEX = 20
LEFT_THUMB = 21, RIGHT_THUMB = 22
LEFT_HIP = 23, RIGHT_HIP = 24
LEFT_KNEE = 25, RIGHT_KNEE = 26
LEFT_ANKLE = 27, RIGHT_ANKLE = 28
LEFT_HEEL = 29, RIGHT_HEEL = 30
LEFT_FOOT_INDEX = 31, RIGHT_FOOT_INDEX = 32
```

MediaPipe Holistic combines: pose (33) + face_mesh (468) + hands (21×2).

### Pose Correction Pipeline (MediaPipe-based)
1. Render orthographic views (front/side/top) of the AI-generated model
2. Run MediaPipe Holistic to detect 2D/3D joint positions
3. Calculate joint angle deviations from standard T-pose/A-pose
4. Apply corrective bone rotations via IK or direct rotation
5. Update skinned mesh via Linear Blend Skinning (LBS)

**Limitations**: MediaPipe is designed for 2D images — 3D models need multi-view rendering. Only detects joint positions, cannot directly manipulate 3D bones. Requires additional rigging step.

## 6. Reallusion Headshot / Character Creator

- Character Creator default body pose: **A-pose**
- Headshot (photo → 3D head): requires **front-facing ID-photo-style** input (head upright, neutral expression, front-facing)
- AccuRIG (auto-rigging tool): has some tolerance for non-standard poses but recommends A-pose
- Generated head auto-matches to CC4 standard body skeleton

## 7. Pose Correction Approaches (for non-standard AI-generated models)

| Approach | Tool | Tolerance | Notes |
|----------|------|-----------|-------|
| MediaPipe Holistic → bone rotation | Custom (Blender Python) | Medium | Detect joint angles → rotate to standard. Complex, less reliable |
| AccuRIG | Reallusion | Medium | Tolerates some pose variation |
| Auto-Rig Pro | Blender plugin | Medium | Auto-detects bone positions, some pose tolerance |
| RigNet | Academic (deep learning) | High | Handles varied poses, limited industrial readiness |
| SMPL-X fitting | Custom pipeline | High | 3D joint extraction → pose normalization. Research-grade |
| Photo capture control | N/A (prevention) | Best | Control pose at input time, most reliable |

## 8. Photo Capture Template Recommendations

### Recommended pose: micro-A-pose (15-30° arm spread) — NOT full T-pose
- Body: standing upright, facing forward
- Head: upright, facing forward, not tilted
- Arms: **15-30° from body** (micro-A-pose) — separates arms from torso for AI reconstruction
- Legs: shoulder-width apart — separates legs
- Hands: palms open, fingers spread (if hand detail needed)
- Hair: tied back or flattened (avoids reconstruction artifacts)
- Expression: neutral, eyes open looking forward, mouth closed
- Clothing: form-fitting (avoid loose clothes distorting body shape)

**Why NOT full T-pose (arms horizontal) for photo capture**:
- Real humans can't hold perfect T-pose comfortably
- Arms fully horizontal causes shoulder muscle tension → unnatural body shape
- AI reconstruction cares more about "arms separated from torso" than "perfect T-pose"
- 15-30° spread is sufficient for arm-torso separation
- Full T-pose is for 3D model bind pose, not for photo capture

### Multi-angle shooting:
- Front, sides (45° and 90° left/right), back
- 360°环绕 (every 15-30°) is best for multi-view reconstruction
- PIFuHD works with single front image, but multi-view improves quality

### Lighting:
- Even diffuse light, avoid strong shadows
- White or solid color background
- Avoid reflections (skin, clothing)

### For facial BlendShape capture (optional):
- Front-facing, unobstructed, neutral expression
- Optionally capture expression set (smile, open mouth, blink) for BlendShape calibration

## 9. Key Industry Insight

- **A-pose is gaining ground**: MetaHuman, Reallusion, Unreal Engine all use A-pose for better shoulder deformation
- **T-pose remains the safe choice for auto-rigging**: Mixamo and ARKit body mocap work best with T-pose
- **Facial requirements are universal**: regardless of body pose, head must be front-facing, upright, neutral expression
- **Pose compatibility gap**: a model in T-pose (for Mixamo) cannot directly go to MetaHuman (A-pose) without pose conversion
- **Best practice**: control pose at photo capture time; post-processing correction is complex and unreliable

### T-pose as "exchange format", A-pose as "final display format"
- **T-pose**: best tool compatibility (Mixamo, ARKit, tool-to-tool transfer). Use for automated pipelines.
- **A-pose**: best shoulder deformation quality (MetaHuman, AAA games). Use for final hand-tuned characters.
- **Facial**: always neutral expression, regardless of body pose.

### Industry AI digital human projects

**PIFuHD (Facebook Research, 9.7k stars, archived)**:
- Input: single RGB image (any pose) → Output: 3D mesh (preserves input pose)
- Does NOT enforce pose; output mesh pose = input photo pose
- Downstream needs extra step to retarget to T-pose or A-pose
- GitHub: https://github.com/facebookresearch/PIFuHD

**TripoSR / Meshy / Rodin (AI 3D generation)**:
- Output pose uncontrollable, usually A-pose or input photo pose
- Some platforms (Meshy) starting to auto-convert to T-pose on output
- Usually recommend Mixamo/AccuRIG for downstream rigging

**Wonder Dynamics (Wonder Studio)**:
- AI video mocap + character replacement
- Accepts any-pose character model, uses SMPL auto-fitting internally
- Exports to UE/Blender with automatic pose conversion

**Reallusion (Character Creator + iClone + AccuRIG)**:
- Character Creator generates A-pose characters
- AccuRIG has high pose tolerance (accepts A-pose and T-pose)
- iClone animation → auto-retarget on export

### Universal pipeline pattern
```
AI generated model (any pose)
    ↓ Pose standardization (→ T-pose or A-pose)
      Methods: SMPL fitting / Auto-Rig Pro / manual
    ↓ Auto-rigging
      T-pose → Mixamo / ARKit
      A-pose → AccuRIG / MetaHuman
    ↓ Animation / mocap driving
    ↓ Engine rendering (UE5 / Unity / Blender)
```
