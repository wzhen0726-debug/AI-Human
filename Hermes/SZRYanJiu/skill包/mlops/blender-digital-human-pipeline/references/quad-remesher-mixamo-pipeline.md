# Quad Remesher + Mixamo Pipeline Feasibility (2026-07-15)

> Source: Multi-site research session (exoside.com, 80.lv, Polycount, Blender Artists, Adobe Mixamo community, YouTube tutorials)

## 1. Quad Remesher Detail Retention at ~300K Faces

**Capability**: Quad Remesher (by Maxime Rouca, same developer as ZBrush ZRemesher) converts triangle/mixed-poly meshes into uniform quads with user-specified target count. Two modes:
- **Adaptive Size**: Higher face density in high-curvature regions (wrinkles, facial features)
- **Uniform Quads**: Evenly-sized quads across entire surface

**For 300K clothed models**:
- 300K faces is mid-high range — sufficient for detail retention
- Adaptive Size mode automatically allocates more faces to wrinkle zones and facial contours
- Vertex Color painting enables manual density control: paint high-density on face/wrinkles, low-density on flat clothing areas
- Community testing (chippwalters, Blender Artists 2019): Quad Remesher "far superior" to Quadriflow and Voxel Remesher on organic models

**Symmetry X off**: Allows natural asymmetric detail (clothing folds, hair) but introduces slight asymmetry that may affect Mixamo auto-rigging (see §3).

## 2. Edge Flow on Clothed Single-Mesh

**Material Boundary control** (official docs): Different Material IDs on body vs. clothing regions guide Quad Remesher to route edge loops along boundaries — confirmed by 80.lv review: "The flow of edges in the new topology is controlled by material boundaries, smoothing groups or surface normals."

**Clothing wrinkle topology**: Community reports that wrinkle regions naturally follow fold direction — edge flow is acceptable for animation.

**Problem areas**: Armpits, crotch, and other concave junctions may produce irregular topology or triangulation (Polycount forum, Setir 2019). Vertex Color painting or manual cleanup recommended.

**Recommendation**: Clean the AI-generated high-poly before retopology (remove floating faces, fix normals, apply Material IDs to separate body/clothing).

## 3. Mixamo Auto-Rigging with ~300K Models

**Upload limits** (community-observed, not officially documented):
- File size: ~100MB (FBX/OBJ)
- Face count: 100K-250K typically works; 250K-500K is borderline; 500K+ often fails
- 300K is at the upper boundary — recommend reducing to 200K-250K for reliability

**Auto-rigging process**:
- Upload FBX/OBJ → mark key points (chin, wrists, elbows, knees, groin) → automatic skeleton binding
- Must be T-pose or A-pose with arms spread
- Single mesh required (body+clothing as one mesh is fine)
- Symmetry detection is used for bone placement — asymmetry from Quad Remesher (Symmetry X off) may cause skewed bones
- **Recommendation**: After Quad Remesher, apply light symmetrization before Mixamo upload

## 4. Mixamo Weight Quality on Clothing

**Algorithm**: Heat Map Diffusion from bones outward — purely geometric, no semantic understanding of clothing vs. body.

**Quality by clothing type**:
- **Tight/semi-tight clothing** (T-shirts, jeans, thin jackets): 70-80% acceptable weight quality, minor manual fixes needed
- **Loose clothing** (dresses, robes, wide coats): 30-50% of vertices need manual weight correction
- Common issues: dress hem stretching, cloth-body penetration, armpit/crotch weight errors

**Post-Mixamo workflow**:
- Download rigged FBX → import to Blender → Weight Paint mode manual correction
- For tight clothing: 1-2 days of weight cleanup
- For loose clothing: 3-5 days of weight cleanup, potentially requiring additional bones or cloth simulation

## 5. Recommended Pipeline

```
Photo → AI high-poly (tight/semi-tight clothing)
  → Blender cleanup (normals, floating faces, Material IDs) [1-2 days]
  → Quad Remesher (200-250K target, Adaptive Size, Symmetry X ON) [1-2 days]
  → Light symmetrization → FBX export [0.5 day]
  → Mixamo upload + auto-rig [1 day]
  → Blender weight correction (clothing regions) [2-5 days]
  → Animation testing [2-3 days]
```

Total: **8-13 days** within a 6-8 week project window.

**Key constraint**: AI generation should produce **tight or semi-tight** clothing (no loose dresses/robes) to minimize Mixamo weight correction effort.

## 6. Sources

- Quad Remesher official: https://exoside.com/quadremesher/
- 80.lv review: https://80.lv/articles/quad-remesher-new-automatic-retopology-plugin
- Blender Artists thread (681 posts): https://blenderartists.org/t/quad-remesher-auto-retopologizer/1170913
- Polycount discussion: https://polycount.com/discussion/208030/quadremesher-new-auto-retopo-plugin-for-maya-3dsmax
- Mixamo: https://www.mixamo.com
- Adobe Mixamo community: https://community.adobe.com/t5/mixamo/ct-p/ct-mixamo