# QR Density Control Experiments — Head/Hand Detail (2026-07-29)

> Goal: get MORE quad faces in high-detail regions (head, hands) and fewer in
> low-detail regions (torso, legs) from Quad Remesher. Three user-proposed
> approaches were tested in sequence. Verdicts are empirical, on a 1.93M-face
> Tripo T-pose high-poly.

## ❌ First, a rejected premise: subdivide AFTER QR

User's original request was to subdivide the QR output in head/hand regions.
This was explicitly shot down by the user:

> "你是在QR之后的模型加了细分,QR的模型已经没多少细节了，你迭代100次细分他不也是没细节??"

**Lesson**: QR output is a uniform quad grid with detail already smoothed away.
Subdividing it is pure interpolation — it adds faces but recovers ZERO surface
detail. Density control must happen BEFORE or DURING remeshing, never after.

## Approach 1: Decimate preprocessing with vertex-group protection — ❌ NO EFFECT

**Idea**: Decimate the high-poly with a vertex group protecting head/hand
regions (`vertex_group="HighDetail", invert_vertex_group=True, ratio=0.3`),
so the QR input has relatively more faces in those regions.

**Result** (QR target 150K):
| Metric | Decimate+QR | Direct QR 150K |
|--------|-------------|----------------|
| Total faces | 149,712 | 151,921 |
| Head faces | 20,288 (13.6%) | 20,416 (13.4%) |
| Hand faces | 15,335 (10.2%) | 15,440 (10.2%) |
| Non-manifold | 3 | 6 |

Head/hand distribution is **identical** to direct QR. QR's internal
curvature-adaptive algorithm redistributes faces based on ITS OWN analysis of
the input, not on the input's density distribution. Pre-decimating some areas
does not make QR allocate more quads there.

**Bonus cost**: the Decimate introduced non-manifold edges (0 → 3).

## Approach 2: Voxel Remesh + Quadriflow — ⚠️ WORKS but wrong distribution

**Idea**: skip QR entirely; use Blender's built-in Voxel Remesh
(`mesh.data.remesh_voxel_size = 0.002; bpy.ops.object.voxel_remesh()`) then
`bpy.ops.object.quadriflow_remesh(target_faces=150000)` for tri→quad.

**Result**:
| Metric | Value |
|--------|-------|
| Total faces | 221,424 (target_faces NOT honored) |
| Quad ratio | 100% |
| Non-manifold | 0 ✅ |
| Head | 29,624 (13.4%) |
| Hand | 14,238 (6.4%) — WORSE than QR's 10.2% |

Clean topology (0 non-manifold) but Quadriflow's `target_faces` parameter had
no effect (221K output for 150K target) and hand allocation dropped. Voxel
remesh at fixed voxel size treats all regions equally — no adaptive density.

**API notes**:
- Voxel size is set on the MESH data (`mesh.data.remesh_voxel_size`), NOT on
  scene (`scene.remesh_voxel_size` does not exist).
- `quadriflow_remesh` in Blender 5.1 does NOT accept `preserve_mesh_attributes`
  kwarg (TypeError). Valid kwargs: `use_mesh_symmetry, use_preserve_sharp,
  use_preserve_boundary, smooth_normals, mode='FACES', target_faces, seed`.

## Approach 3: Instant Meshes via pymeshlab — ⚠️ WORKS but 0% quad + high non-manifold

**Idea**: use pymeshlab's `meshing_isotropic_explicit_remeshing` (the Instant
Meshes core algorithm) which is truly curvature-adaptive.

**Result** (two-pass: targetlen 0.3% then 0.15% bbox diagonal, decimate to 150K):
| Metric | Value |
|--------|-------|
| Total faces | 149,986 |
| Quad ratio | **0%** (all triangles — output is tri mesh) |
| Non-manifold | **44** ❌ |
| Head | 50,388 (33.6%) ✅ |
| Hand | 819 (0.5%) ❌ |

Head allocation is excellent (33.6% vs QR's 13%) but hands collapsed to 0.5%,
output is all triangles (needs a separate tri→quad pass), and 44 non-manifold
edges.

**Integration pitfalls (Blender 5.1 + pymeshlab 2025.7)**:
- pymeshlab does NOT install into Blender's bundled Python — `pip install
  pymeshlab` into SYSTEM python, then run as a two-step process
  (Blender exports FBX → system python runs pymeshlab → Blender imports result).
- `targetlen` requires `ml.PercentageValue(0.3)`, NOT `ml.Percentage(0.3)`
  (class is `PercentageValue`, not `Percentage`).
- `ms.save_current_mesh()` to `.fbx` silently writes nothing on Windows; save
  to `.obj` instead.
- Blender 5.1 OBJ import is `bpy.ops.wm.obj_import(filepath=...)`, NOT
  `bpy.ops.import_scene.obj()` (removed). OBJ EXPORT is `bpy.ops.wm.obj_export`.
- `meshing_tri_to_quad_by_smart_triangle_pairing` raises PyMeshLabException on
  this mesh; don't rely on pymeshlab for tri→quad.

## Cross-cutting verdict: QR's face distribution is curvature-driven, not input-driven

All three experiments show the same pattern: head gets ~13%, hands ~9-10%
regardless of input preprocessing. The adaptive algorithm in every remesher
(QR, Quadriflow, Instant Meshes) analyzes surface curvature and allocates
quads by ITS OWN judgment. The only reliable lever for more head/hand detail
is **raising the total face count** (which proportionally raises all regions)
or **splitting the mesh into separate objects and remeshing each with its own
target count** (more pipeline complexity).

## QR face count vs non-manifold edges (empirical, same Tripo mesh)

| Target | Output | Non-manifold | Note |
|--------|--------|:---:|------|
| 90K | 86,733 | 0 | Clean baseline |
| 125K | 117,539 | 0 | ✅ Sweet spot: 235K tris, <250K target, clean |
| 150K | 138,905–151,921 | 3–6 | Small T-junction cluster at abdomen (-0.046, 0.05, 0.376) |
| 150K (after Decimate pre) | 149,712 | 3 | Pre-decimate ADDS defects |

The 150K non-manifold edges are T-junctions (1 edge shared by 3 faces + 5
dangling edges) at a density-transition zone. `remove_doubles`,
`delete_loose`, `fill_holes`, `normals_make_consistent`, and
`dissolve_degenerate` do NOT fix them. Options: accept and repair with a small
local face-delete + grid-fill, or stay at 90K/125K (clean).

**User decision**: QR 125K (117,539 quads, 235,058 tris, 0 non-manifold) is
the production choice — meets <250K triangle budget with clean topology.

## QR double-layer geometry: 42.7% inward-facing normals (2026-07-29)

QR on a clothed AI high-poly (Tripo) produces **42.7% inward-facing normals**
(42.7-42.8% at both 90K and 125K). This is NOT a normal-direction bug —
`normals_make_consistent` does NOT fix it (the inward faces share edges with
outward faces, so Blender cannot unify them).

**Root cause**: QR preserves the clothing+body double-layer structure. The
"inward" faces are the body surface underneath clothing. They are geometrically
correct — they face inward because they're the back side of the body shell,
covered by the clothing shell.

**Impact on pipeline**:
- **Bake**: unaffected — high-poly clothing projects onto these faces during
  Selected-to-Active bake. The inward faces receive the body's texture.
- **Render**: affected — backface culling hides them, creating "transparent"
  patches in material preview. Fix: enable "Show Backface Culling" OFF in
  viewport, or use two-sided materials.
- **Rigging**: unaffected — skin weights bind to vertices, not normals.

**Do NOT try to "fix" this by flipping normals** — it breaks the double-layer
structure and creates holes. Accept it as QR's faithful preservation of the
input's layered geometry.
