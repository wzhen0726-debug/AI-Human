# Symmetrization + Texture Baking: Definitive Research

## The Core Problem

User wants: **symmetric mesh** (for binding) + **asymmetric texture** (left scar stays left, right stays right — no mirror duplication).

## Wrong Approach (abandoned)

"Symmetrize low-poly after wrap" → baking fails because asymmetric high-poly and symmetric low-poly don't overlap in space. Blender's Selected-to-Active bake casts rays from low-poly normals outward — if surfaces don't align, rays hit wrong high-poly surfaces or miss entirely.

Example: high-poly has left arm raised, right arm down. Low-poly has both arms down (symmetric). Low-poly's right arm rays hit... nothing (or the high-poly's raised left arm) = texture garbage.

## Correct Flow (verified 2026-07-09)

```
① Symmetrize HIGH-POLY mesh coordinates (bmesh vert.co only, DO NOT touch UV/texture)
   → high-poly mesh is now left-right symmetric
   → high-poly surface texture is STILL asymmetric (UV didn't move, left scar still in left UV space)
   → high-poly texture DISPLAY may look wrong in viewport (vertices moved but UVs didn't) — THIS IS FINE

② Wrap low-poly template onto the now-symmetric high-poly
   → low-poly is naturally symmetric (template is symmetric topology)

③ UV unwrap low-poly

④ Bake textures (Selected to Active)
   → low-poly left face rays → hit high-poly left face (has left scar) → sample left scar texture ✓
   → low-poly right face rays → hit high-poly right face (has right scar) → sample right scar texture ✓
   → Result: symmetric mesh + asymmetric texture ✓
```

## Why This Works

Baking is a **pure spatial operation** — rays travel from low-poly surface outward along normals, hit high-poly surface, sample the color at that 3D position. The high-poly's UV layout is **irrelevant** to baking. The high-poly is just a color source in 3D space. Even if the high-poly's viewport display looks wrong (texture misaligned due to moved vertices + unmoved UVs), the surface still displays colors at each 3D position, and that's what baking samples.

## ZBrush Smart ReSym (智能重新对称) — Official Behavior

**Source**: ZBrush official docs at help.maxon.net/zbr, verified via ZBrushCentral forum API.

- SmartReSym: "restores symmetry to the object by examining all **points** in the mesh... determining which were originally intended to lie in mirror-symmetrical positions"
- ReSym: "restores mirror symmetry to the object by adjusting the **positions of vertices** which lie in near-symmetrical positions"
- Poseable Symmetry: "**does not use UVs** and is 100% dependent on your mesh being topologically symmetrical"
- UV operations have a **completely separate sub-panel** (Tool > UV Map) — if Resymmetry touched UV, this panel wouldn't need to exist separately

**Conclusion**: Smart ReSym only modifies vertex positions. UV and texture are untouched.

**User tested and confirmed**: Smart ReSym on a model with UV+texture → UV and texture preserved unchanged.

**Important**: This means in ZBrush, if your model has UV+texture, Smart ReSym makes the mesh symmetric but the texture display will misalign (vertices moved, UVs didn't). ZBrush users handle this via Polypaint as intermediary (texture → Polypaint → Smart ReSym → new UV+texture). In our Blender pipeline, we don't care about high-poly display — we only care about the baked low-poly texture, which is correct because baking is spatial.

## bmesh Implementation

`BMVert.co` (vertex-level) and `BMLoopUV.uv` (loop-level/per-face-vertex) are **completely independent data layers**. Modifying `vert.co` has zero effect on UV. A single vertex can even have different UVs in different faces (per-loop storage).

```python
import bmesh
bm = bmesh.new()
bm.from_mesh(mesh)
for vert in bm.verts:
    vert.co.x = -vert.co.x  # Mirror X axis — UV is NOT affected
bm.to_mesh(mesh)
bm.free()
```

Match left/right vertex pairs by Y/Z coordinate nearest-neighbor, then mirror X. Or use plugin `mio3_symmetry` (github.com/mio3io/mio3_symmetry) which can independently symmetrize mesh, UV, weights, shape keys, normals.

## Head Symmetrization

The head ALSO needs mesh symmetrization. User statement: "头部也是要做网格镜像的，不然之后需要绑定，不对称的话很难打控制点" (head needs mesh mirroring, otherwise binding control points on asymmetric mesh is difficult).

The standard low-poly template has symmetric topology. When wrapped onto a symmetrized high-poly, the result is naturally symmetric. Facial micro-asymmetry (<1mm) from the original high-poly is averaged out during symmetrization — this is acceptable and expected.

## Mirror Center Edge Loop Constraint (critical for wrap symmetry)

When wrapping a symmetric template onto a high-poly using Shrinkwrap, the
**center-line vertices** (those on the X=0 symmetry plane) MUST stay on X=0
throughout the wrap process. If Shrinkwrap pulls them off the plane, the
resulting mesh won't be mirror-symmetric — mirroring after wrap will produce
seams, gaps, or flipped faces at the center line.

**The requirement**: The template topology must have a **continuous edge loop
running along the X=0 plane** (the mirror axis). This is standard in
production templates (MetaHuman, well-topologized bodies). Without it, there
are no vertices to constrain to X=0, and mirror symmetry will have no clean
seam.

**Implementation**: After each Shrinkwrap iteration, force center-line
vertices back to X=0:
```python
# Identify center-line verts (|x| < threshold before Shrinkwrap)
center_verts = [v.index for v in bm.verts if abs(v.co.x) < 0.001]

# After Shrinkwrap apply:
for vi in center_verts:
    bm.verts[vi].co.x = 0.0  # Pin to mirror plane
```
This is a pure Python operation, fully automatable, and prevents the most
common wrap-symmetry failure mode. The user explicitly raised this:
"对称中心肯定是有一圈平直的线，不然对称完可能会出错误" (the symmetry center
must have a flat loop of edges, otherwise symmetry will produce errors).

## Pose Correction vs Symmetrization — NOT the Same Operation

| | Pose Correction | Symmetrization |
|---|---|---|
| **What it fixes** | Joint ANGLES (arm position, head tilt) | Left/right vertex POSITIONS (body-type differences) |
| **How** | Rotate bones/SMPL pose parameters (θ=0) | Mirror average vertex coordinates |
| **Example problem** | Left arm raised, right arm down | Left shoulder 0.5cm higher than right |
| **Fixes the other?** | NO — T-pose but still asymmetric | NO — symmetric but still wrong pose |
| **Order** | FIRST | SECOND (after pose correction) |
| **Precision** | ≤15° for Rigify binding, ≤5° for wrap | Vertex-level, ~1mm tolerance |

Both are required, in fixed order: Pose correction → Symmetrization. They are orthogonal — one operates on the rotation subspace (SE(3)), the other on the vertex coordinate subspace.
