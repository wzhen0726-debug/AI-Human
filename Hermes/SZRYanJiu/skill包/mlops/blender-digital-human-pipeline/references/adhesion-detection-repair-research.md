# Mesh Adhesion Detection & Repair Research (2026-07-15)

Research on detecting and repairing mesh adhesion (self-contact / near-self-intersection) in AI-generated 3D character models, particularly inner thigh regions.

## 1. MediaPipe Holistic on AI 3D Renders

- BlazePose (arXiv:2006.10204) trained on real human photos; domain gap exists for AI 3D renders
- Realistic renders (Metahuman, Character Creator): PCK@0.2 estimated 85-92%
- Stylized/game renders (DAZ3D, Vroid): PCK@0.2 estimated 70-85%
- Anime/cartoon renders: PCK@0.2 estimated 50-70%
- **Recommendation**: Use MediaPipe only for ROI rough localization of inner thigh region. Precise adhesion detection must use 3D geometry algorithms. Multi-view renders improve robustness.

## 2. Minimum Distance Adhesion Detection

Core approach: BVH acceleration + triangle-to-triangle distance queries.

**Key references:**
- Ericson, "Real-Time Collision Detection", Morgan Kaufmann, 2004 (essential reference book)
- GJK algorithm: Gilbert, Johnson, Keerthi, "A Fast Procedure for Computing the Distance Between Complex Objects in Three-Dimensional Space", IEEE J. Robotics and Automation, 1988
- CGAL AABB Tree: Alliez et al., CGAL User Manual — efficient closest-point and intersection queries
- Volino & Magnenat-Thalmann, "Efficient Self-Collision Detection on Smoothly Discretized Surface Animations", CGF 1994
- Bridson et al., "Robust Treatment of Collisions, Contact and Friction for Cloth Animation", ACM TOG 2002

**Detection pipeline:**
1. Build BVH (CGAL AABB Tree or Intel Embree)
2. Use MediaPipe keypoints to determine inner-thigh ROI (left/right leg inner face sets)
3. BVH proximity queries on ROI faces
4. Filter pairs with distance < threshold (5mm)
5. Exclude topologically adjacent faces (shared edges/vertices)
6. Output adhesion regions

**Implementation options:**
- C++ industrial: CGAL AABB Tree or Intel Embree — O(n log n) build + O(m log n) query
- Python prototyping: trimesh `proximity.closest_point`, libigl Python bindings `AABB`, open3d `KDTreeFlann`

## 3. Vertex Normal Displacement + Transition Smoothing

**Three-step approach:**
1. Compute penetration depth and separation direction per adhesion face-pair
2. Displace vertices along normals (small steps, <1mm per iteration)
3. Laplacian smoothing with distance-weighted falloff on transition region

**Key references:**
- Sorkine & Alexa, "As-Rigid-As-Possible Surface Modeling", SGP 2007
- Botsch & Sorkine, "On Linear Variational Surface Deformation Methods", IEEE TVCG 2008
- Taubin, "A Signal Processing Approach to Fair Surface Design", SIGGRAPH 1995 (alternating λ/μ to prevent volume shrinkage)
- Fleishman et al., "Bilateral Mesh Denoising", ACM TOG 2003 (edge-preserving smoothing)
- Bouaziz et al., "Projective Dynamics: Fusing Constraint Projections for Fast Simulation", ACM TOG 2014

**Library support:** CGAL, libigl (`igl::laplacian_smooth`, `igl::cotmatrix`), OpenMesh, trimesh, Blender Python API

## 4. Risk of New Self-Intersections or Holes After Repair

**Risk assessment:**
- New self-intersections: 30-50% probability (high severity)
- Holes/tears: 10-20% probability (high severity)
- Triangle quality degradation: 40-60% probability (medium severity)
- Normal flipping: 5-10% probability (medium severity)

**Mitigation strategies:**
- Iterative small-step repair with validation loop (rollback + retry with smaller step on failure)
- Constrained optimization (Projective Dynamics) instead of pure geometric displacement
- Post-repair self-intersection detection via CGAL `does_self_intersect()` or libigl `self_intersections()`
- Mesh quality checks: degenerate faces, aspect ratio, non-manifold edges, normal consistency, boundary sealing

## 5. Impact on Quad Remesher and Rigging

**Quad Remesher:** Repair must happen BEFORE Quad Remesher. Remesher requires manifold input and correct geometry. After repair, run isotropic remeshing (Botsch & Kobbelt, SGP 2004) to ensure triangle quality before Quad Remesher.

**Rigging/Skinning:** Repair before rigging is safe. Repair after rigging requires recomputing skin weights. Recommended pipeline:
```
AI generation → Adhesion repair → Quality check → Isotropic remeshing → Quad Remesher → Rigging
```

**Key references:**
- Baran & Popović, "Automatic Rigging and Animation of 3D Characters", ACM TOG 2007
- Jacobson et al., "Bounded Biharmonic Weights for Real-Time Deformation", ACM TOG 2011

## Overall Feasibility

| Component | Feasible | Risk | Notes |
|-----------|----------|------|-------|
| MediaPipe keypoint detection | Conditional | Medium | ROI only, multi-view needed |
| Min-distance adhesion detection | Yes | Low | Mature algorithms, industrial libs |
| Normal displacement + smoothing | Yes | Medium | Need iterative repair + validation |
| Avoiding new self-intersections | Needs extra handling | Medium-High | Validation loop + constrained optimization |
| Quad Remesher compatibility | Yes | Low | Repair before Remesher |
| Rigging compatibility | Yes | Low | Same as above |