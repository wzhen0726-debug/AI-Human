# Topology Transfer Methods: Comprehensive Comparison (2026-07-28)

Research session investigating how to transfer MetaHuman standard low-poly
topology (A-pose, 32K verts, no skeleton) onto AI-generated high-poly mesh
(Tripo, T-pose, 1.13M faces, clothed). Focus: zero-budget, open-source,
Blender-integrable solutions.

## Method Comparison Matrix

| Method | Pose diff | Cloth | Sparse ctrl pts | Keep topo | OSS/free | Blender | Score |
|--------|:---------:|:-----:|:---------------:|:---------:|:--------:|:-------:|:-----:|
| **ARAP** | ✅ | ⚠️ | ✅ high tol | ✅ | ✅ | ⚠️ plugin | ⭐⭐⭐⭐⭐ |
| **Deformation Transfer** | ✅ perfect | ⚠️ | ✅ auto-expand | ✅ | ✅ | ❌ adapt | ⭐⭐⭐⭐ |
| **Non-Rigid ICP** | ✅ | ⚠️ | ✅ auto | ✅ | ✅ | ❌ adapt | ⭐⭐⭐⭐ |
| Surface Deform (Blender) | ⚠️ pre-align | ✅ | N/A | ✅ | ✅ | ✅ built-in | ⭐⭐⭐ |
| RBF (TPS) | ⚠️ partial | ❌ | ❌ bulges | ✅ | ✅ | ❌ script | ⭐⭐ |
| Mesh Deform (Blender) | ⚠️ cage | ⚠️ | N/A | ✅ | ✅ | ✅ built-in | ⭐⭐ |
| Shrinkwrap (Blender) | ❌ fails | ❌ fails | N/A | ✅ | ✅ | ✅ built-in | ⭐ |
| Wrap3D/ZWrap | ✅ perfect | ✅ | ✅ | ✅ | ❌ paid | ❌ | ⭐(N/A) |

## 1. ARAP (As-Rigid-As-Possible) — RECOMMENDED

**Principle**: Minimizes deviation of each local triangle transformation from
a rigid transformation. Iterative solve: fix rotations → solve positions →
fix positions → solve rotations. Preserves local shape while allowing global
deformation.

**Why it solves RBF bulging**: Local rigidity constraint prevents regions
between sparse control points from expanding. Arms stay arm-shaped, torso
stays torso-shaped, even with only 16 landmarks.

**Open-source implementations**:
| Repo | Lang | Stars | Notes |
|------|------|-------|-------|
| `libigl/libigl` + `libigl-python-bindings` | C++/Py | 5059/369 | Geometry processing library, mature ARAP |
| `OllieBoyne/pytorch-arap` | Python | 54 | PyTorch, differentiable |
| `cheind/mesh-deform` | C++ | 84 | Interactive ARAP |
| `fanxiaochen/ARAP` | C++ | 39 | Standalone ARAP surface deform |
| `oobma/ARAP-deformer` | Python | 2 | **Blender-specific**, uses libigl |
| `IzN432/fyp-blender-arap-addon` | Python | 1 | Blender ARAP addon (student project) |

**Blender built-in**: Laplacian Deform Modifier is similar (Laplacian
coordinate deformation, needs skeleton/control points). Not true ARAP but
comparable results for moderate deformations.

**Limitation**: Pure ARAP does NOT project to target surface. It deforms
shape while preserving rigidity, but doesn't "stick" to the high-poly mesh.
Must be combined with Surface Deform or Shrinkwrap as a post-step.

## 2. Deformation Transfer (Sumner & Popović 2004)

**Paper**: http://people.csail.mit.edu/sumner/research/deftransfer/

**Principle**: Transfers deformation transforms (not geometry). Describes
deformation as position-independent triangle transformations. Two phases:
1. **Correspondence**: Iteratively "inflate" source into target shape,
   minimizing triangle transform cost while pinning marker vertices. Auto-
   expands sparse markers to dense correspondences via closest-point matching.
2. **Transfer**: Solve min Frobenius distance between source and target
   triangle transforms.

**Pose handling**: ✅ Inherently handles pose differences — transferring
deformation IS the pose change.

**Open-source implementations**:
| Repo | Lang | Stars | Notes |
|------|------|-------|-------|
| `mickare/Deformation-Transfer-for-Triangle-Meshes` | Python | 213 | Complete, MIT, 3D viewer |
| `Golevka/deformation-transfer` | C | 290 | ANSI C, 14yr old but stable |
| `guyafeng/Deformation-Transfer-for-Triangle-Meshes` | — | 58 | Paper reproduction |
| `jerenchen/deformxfer` | C++ | 49 | Header-only |
| `chand81/Deformation-Transfer` | C++ | 126 | Transfer keeping target identity |

**Requirement**: Need source reference + source deformed (e.g., MetaHuman
A-pose → T-pose) to transfer to target. The A→T deformation itself can be
done with ARAP + landmarks.

## 3. Non-Rigid ICP

**Principle**: Iteratively deform source to target: find closest point pairs
→ solve deformation energy min → update. Energy = correspondence distance +
rigidity + smoothness.

**Open-source implementations**:
| Repo | Lang | Stars | Notes |
|------|------|-------|-------|
| `wuhaozhe/pytorch-nicp` | Python | 275 | GPU-accelerated, PyTorch |
| `rabbityl/Nonrigid-ICP-Pytorch` | C++ | 129 | Depth scan alignment |
| `shubhamag/non_rigid_icp` | Python | 96 | Noisy point cloud optimized |
| `TimoBolkart/TemplateFitting` | C++ | 40 | Face scan template fitting |

**Limitation**: Sensitive to initial pose. Large pose differences (arm 90°)
need many iterations + good initialization. Auto-denses control points
(better than RBF) but clothing occlusion is still a problem.

## 4. RBF Bulging — 6 Solutions

The core problem (verified 2026-07-28): 16 landmarks → TPS/Gaussian RBF
produces "obese" body. Bulging is a mathematical property of RBF with sparse
control points, NOT a parameter issue (sigma tuning is ineffective).

### Solution 1: Increase control point density
- Expand from 16 → 50-100 landmarks
- Along joint chains (shoulder→elbow→wrist + midpoints)
- Torso grid (chest, back, sides × 2-3 rows)
- Semi-automatic: sample from high-poly mesh (equidistant + normal alignment)

### Solution 2: Wendland compact-support kernel (replaces TPS)
- TPS is global-support (every control point affects entire space)
- Wendland C2 is compact-support (influence limited to radius)
- `scipy.interpolate.RBFInterpolator(kernel='wendland')`
- Effect: control points only influence nearby region → less bulging

### Solution 3: Regularization terms
- Add volume preservation constraint to RBF energy
- Add Laplacian smoothness constraint (keep local mesh flat)
- E = E_RBF + λ₁·E_volume + λ₂·E_laplacian

### Solution 4: RBF + ARAP hybrid (RECOMMENDED)
- Step 1: RBF coarse alignment (landmarks exact)
- Step 2: ARAP local rigidity correction (eliminates bulging)
- ARAP "pulls back" expanded regions while keeping landmark positions

### Solution 5: Region-partitioned RBF
- Split mesh into regions (head, torso, L-arm, R-arm, L-leg, R-leg)
- Independent RBF per region, smooth blend at boundaries
- Reference: `yamahigashi/MayaMeshRetarget` uses skin-weight-based clustering

### Solution 6: Replace RBF with Non-Rigid ICP
- NICP auto-adds closest-point constraints (auto-denses control points)
- But requires iterative solve and initial alignment

## 5. Head vs Body Wrap Difficulty

| Dimension | Head | Body |
|-----------|------|------|
| Pose difference | None | Large (A-pose vs T-pose) |
| Surface continuity | Continuous convex | Complex (with clothes) |
| Landmark density | High (20+ in small area) | Low (16 for whole body) |
| Shrinkwrap effectiveness | Works | Fails |
| Clothing occlusion | None | Severe |
| Existing tool support | MetaHuman DNA | No direct tool |
| Verified precision | 0.4mm | Unsolved |

**Why head wrap works**: No pose difference, continuous convex surface,
dense landmarks, no clothes. Shrinkwrap NEAREST is effective on convex shapes.

**Why body wrap fails**: A-pose vs T-pose (~90° arm angle), clothes occlude
body geometry, 16 landmarks too sparse for body area, Shrinkwrap has no
semantic understanding (wraps to clothes, not body).

## 6. Recommended Multi-Step Workflow

```
Step 1: Expand control points (16 → 50+)
  - Along joint chains, torso grid, semi-auto from high-poly
  ↓
Step 2: RBF coarse alignment (Wendland kernel)
  - scipy.interpolate.RBFInterpolator(kernel='wendland')
  - Landmarks exact, rest roughly positioned
  ↓
Step 3: ARAP local rigidity correction
  - libigl Python bindings or oobma/ARAP-deformer
  - Eliminates bulging, preserves arm/leg shape
  ↓
Step 4: Surface Deform fine fit (Blender built-in)
  - Now both meshes are in same pose → Surface Deform works
  - Bind deformed low-poly to high-poly surface
  ↓
Step 5: Manual correction
  - Clothing regions: keep low-poly shape or simplified fit
  - Self-intersection: manual adjust
  - Corrective Smooth for artifacts
```

**Key principle**: Solve pose FIRST (ARAP), then solve surface fit (Surface
Deform). Never try to do both in one step (Shrinkwrap fails, RBF bulges).

## 7. Open-Source Tool Inventory

### Blender built-in modifiers (free)
| Modifier | Use | Suitability |
|----------|-----|-------------|
| Shrinkwrap | Wrap to surface | ❌ pose+cloth failure |
| Surface Deform | Transfer surface deform | ⚠️ post-align only |
| Mesh Deform | Cage deformation | ⚠️ needs cage |
| Laplacian Deform | Laplacian coord deform | ⚠️ needs skeleton |
| Corrective Smooth | Fix artifacts | ✅ post-process |

### Key libraries
| Library | Lang | For |
|---------|------|-----|
| `scipy.interpolate.RBFInterpolator` | Python | RBF with Wendland kernel |
| `libigl` Python bindings | Python | ARAP, geometry processing |
| `pytorch-nicp` | Python | GPU non-rigid ICP |
| `mickare/Deformation-Transfer` | Python | Sumner deformation transfer |

### MetaHuman integration
| Tool | Stars | Function |
|------|-------|----------|
| `poly-hammer/character-dna-addon` | 275 | MetaHuman DNA → Blender |
| `HakanErunsal/MetahumanToManny` | 14 | MH skeleton → Manny |

### Paid (reference only, not usable)
| Tool | Price | Function |
|------|-------|----------|
| R3DS Wrap3D | $499 | Industry standard topology transfer |
| ZWrap | $299 | ZBrush plugin version |
| Wrap4D | paid | Batch 4D sequence processing |

## 8. Search Strategy Note

During this research session, Google and DuckDuckGo both triggered bot
detection CAPTCHAs. Bing returned minimal results. The most effective
approach was:
1. **GitHub API search** (`api.github.com/search/repositories`) — reliable,
   no CAPTCHA, structured results with star counts
2. **Direct URL navigation** to known documentation (Blender docs, paper
   pages, specific GitHub repos)
3. **Browser snapshot** of individual repo READMEs for detailed content

GitHub API search tip: use `+` for spaces, `sort=stars` for quality ranking,
`per_page=5` for concise results. Save JSON to files with `curl -s URL > file`
(redirect) rather than `curl -s URL -o file` (which fails with exit code 23
on this Windows/git-bash environment).
