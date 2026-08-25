# Body Wrap: Method Comparison & Failure Analysis (2026-07-28)

> All 7 methods tried in test02 for MetaHuman Body (A-pose, 32K) → Tripo (T-pose, 1.1M, clothed). All failed.

**"全自动化" constraint (HARD)**: The product is positioned as "one-click automation for non-3D professionals." Manual steps (like "mark 16 landmarks in Blender GUI") are UNACCEPTABLE — the user explicitly said "全自动的产品体验" cannot include any manual interaction. Every stage must be fully automated via code/AI detection. This is a product-level constraint, not a preference.

## Input Assets

| Asset | Verts | Pose | Notes |
|-------|-------|------|-------|
| MetaHuman Body | 32,334 | A-pose | No skeleton, no vertex groups, pure mesh |
| MetaHuman Head | 24,414 | Forward-facing | Separate mesh |
| Tripo high-poly | 1,137,322 | T-pose | Contains loose clothing |

## Critical Bugs Discovered

### 1. MetaHuman matrix_basis double-scaling
MetaHuman Body's `matrix_basis` already contains a 0.01 scale (cm→m). Manually doing `v.co *= 0.01` then `transform_apply` causes vertex coordinates to collapse to 0/NaN.

**Fix**: Don't manually scale vertices. Just `transform_apply` to bake the matrix_basis scale.

### 2. MetaHuman orientation already -Y forward
MetaHuman original orientation is face→-Y, same as Tripo after 3-step rotation. **No Z-90° rotation needed.** Earlier scripts incorrectly rotated MetaHuman -90° around Z, making it face→-X.

**Verification**: Face vertices (Y < -0.10) center at (0.000, -0.122, 1.648) — face is in -Y direction.

### 3. MetaHuman needs Body+Head for correct height
Body alone: Z[0, 1.496m] (no head). Body+Head: Z[0, 1.803m]. Must import both and scale by total height, not body height alone.

## Method Results

### A. Direct Shrinkwrap (NEAREST_SURFACEPOINT)
- **Script**: 34_wrap_v3.py
- **Result**: X span 0.26m (Tripo=1.81m), model collapsed
- **Root cause**: A-pose arms near torso → Shrinkwrap pulls arm vertices to nearest torso clothing surface, not T-pose arm endpoints

### B. Rotate arms to T-pose then Shrinkwrap
- **Script**: 37_wrap_v5_arms.py
- **Result**: X span 0.94m, still deformed
- **Root cause 1**: Distance threshold 0.6m too small — hand vertices at 0.64m from shoulder weren't captured, arms "broke" at wrist
- **Root cause 2**: Second full-body Shrinkwrap pass pulled rotated arms back to torso clothing

### C. Vertex group limited Shrinkwrap (torso only)
- **Script**: 37_wrap_v5_arms.py (modified)
- **Result**: Y span compressed from 1.4 to 0.31 (squashed flat)
- **Root cause**: NEAREST_SURFACEPOINT吸附所有顶点到最近表面, Tripo Y方向很薄(0.31m)

### D. RBF TPS (Thin Plate Spline)
- **Script**: hermes-rbf-part2.py
- **Result**: Landmark precision <30mm ✓, but torso "bulged" (vision reported "extremely obese")
- **Root cause**: TPS global support — every control point influences entire space. With only 16 landmarks (6 for torso), inter-landmark regions freely interpolate and bulge.

### E. RBF Gaussian kernel
- **Script**: hermes-rbf-gaussian.py
- **Result**: Same bulging as TPS (X span 1.625 vs TPS 1.638)
- **Root cause**: Different kernels produce similar torso displacement (~0.05m). Bulging is driven by landmark distribution, not kernel choice.

### F. Anchor iteration + Shrinkwrap
- **Script**: 12_wrap_with_anchors.py
- **Result**: Not validated (depends on existing wrap result)
- **Limitation**: Still uses Shrinkwrap in final step → same structural failure

### G. Estimated landmark alignment
- **Script**: 33_align_v2.py
- **Result**: Positions inaccurate
- **Root cause**: Used T-pose arm positions (X-spread) for A-pose model (arms in Y direction)

## Landmark Distance Analysis (A-pose → T-pose)

| Region | Distance | Notes |
|--------|----------|-------|
| Head/torso | 60-100mm | Mostly Y-direction offset |
| Shoulders | ~57mm | Basically aligned |
| Elbows | ~256mm | A-pose droop vs T-pose horizontal |
| Wrists | ~453mm | Largest difference, arms need major stretch |
| Knees/ankles | ~55mm | Basically aligned |

## Industry Research: The Solution

**ARAP (As-Rigid-As-Possible) deformation** is the key technology to solve RBF bulging:
- Local rigidity constraint prevents inter-landmark regions from bulging
- Higher tolerance for sparse control points than RBF
- Open-source: `libigl/libigl-python-bindings` (369★), `oobma/ARAP-deformer` (Blender plugin)

**Industry standard multi-step pipeline**:
```
Step 1: RBF粗对齐 (landmark精确对齐)
Step 2: ARAP局部刚性修正 (消除膨胀, 保持手臂/腿形状)
Step 3: Surface Deform精细贴合 (同姿态下贴到高模表面)
Step 4: 手动修正衣服区域
```

## RBF Bulging: 6 Solutions

1. Increase control points (16→50+)
2. Wendland compact-support kernel (`scipy.interpolate.RBFInterpolator(kernel='wendland')`)
3. Regularization (volume preservation + Laplacian smoothing)
4. RBF + ARAP hybrid (coarse align + rigidity correction)
5. Region-wise RBF (head/torso/limbs independent)
6. Non-Rigid ICP (auto-denses control points)

## MediaPipe Pose Auto-Detection (2026-07-28, NEW)

**Goal**: Replace manual 16-point landmark marking with fully automated AI detection.

### Product-Level Constraint: Zero Manual Steps

User explicitly rejected manual landmark marking ("mark 16 points in Blender GUI") as incompatible with "one-click automation for non-3D professionals." Three automated alternatives evaluated:

| Approach | Automation | Implementation | Packaging | Accuracy | Clothing Handling | Verdict |
|----------|-----------|----------------|-----------|----------|-------------------|---------|
| **A. Skeleton-driven pre-alignment** | ✅ | Medium (need Mixamo first) | Easy | Medium (rotation is estimate) | ❌ Bones bind to clothing surface | Rejected: clothing deformation uncontrollable |
| **B. MediaPipe Pose detection** | ✅ | Medium-high (2D→3D mapping) | Easy (~50MB) | Medium-high (front/back good, side fails) | ❌ Raycast hits clothing | **Selected**: core approach, supplement with bone assist |
| **C. Non-Rigid ICP** | ✅ | High (complex implementation) | Hard (~2GB PyTorch) | High (dense correspondence) | ❌ NICP pulls to clothing | Deferred: packaging too heavy, clothing issue unsolved |

**Chosen hybrid**: MediaPipe Pose (core) + bone-assisted validation (fallback) + RBF+ARAP deformation. MediaPipe provides 33 joints (vs 16 manual), fully automated, proven in test01 (0.4mm head wrap). Bone assist covers MediaPipe side-view failures.

### Implementation

### Implementation

- **Model**: MediaPipe Pose Landmarker Heavy (29.2MB, `pose_landmarker_heavy.task`)
- **API**: `mediapipe.tasks.python.vision.PoseLandmarker` (MediaPipe 1.0.0 tasks API, NOT `mp.solutions.pose`)
- **Detection**: 33 body joints per view, 4 views rendered (front/side_L/side_R/back)

### Results by View

| View | Upper Body (shoulder/elbow/wrist) | Lower Body (hip/knee/ankle) | Usability |
|------|-----------------------------------|----------------------------|-----------|
| front | ✅ vis>0.99 | ✅ vis>0.97 | All usable |
| side_L | ❌ vis<0.4 | ❌ vis<0.1 | Failed |
| side_R | ⚠️ partial | ❌ vis<0.1 | Mostly failed |
| back | ✅ vis>0.98 | ✅ vis>0.82 | All usable |

### Key Findings

1. **Front+Back views sufficient for upper body**: shoulder/elbow/wrist all vis>0.98 from both views. Can triangulate X and Z coordinates.
2. **Side views fail for lower body**: knee/ankle vis<0.1 in both side views. Cannot get Y (depth) coordinate from side views.
3. **MediaPipe z-coordinate is relative depth** (not absolute 3D). Can estimate front/back relationships but not precise Y positions.
4. **2D→3D raycast projection needed**: 2D pixel coordinates must be projected back to 3D mesh surface via camera ray casting.

### 2D→3D Projection Strategy

```
Front view: 2D (px, py) → camera ray → 3D (X, Z) on mesh surface
Back view:  2D (px, py) → camera ray → 3D (X, Z) on mesh surface
Y (depth):  Use bone-assisted reference (Mixamo hip Y as baseline) or accept uncertainty
```

### Automated Landmark Generation

**12 key joints** for body wrap:
- left/right_shoulder (id 11/12)
- left/right_elbow (id 13/14)
- left/right_wrist (id 15/16)
- left/right_hip (id 23/24)
- left/right_knee (id 25/26)
- left/right_ankle (id 27/28)

**Next step**: Implement 2D→3D projection + RBF+ARAP deformation with auto-generated landmarks.

## Recommended Next Steps

1. Install `libigl` Python bindings: `pip install igl`
2. Test `oobma/ARAP-deformer` compatibility with Blender 5.1
3. Increase body landmarks to 50+ and re-test RBF+ARAP hybrid
4. Reference: `mickare/Deformation-Transfer-for-Triangle-Meshes` (213★) for correspondence auto-expansion
