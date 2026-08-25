# Asymmetric High-Poly → Symmetric Low-Poly Baking Problem

## Problem Statement

If the high-poly model is asymmetric (e.g., left arm raised, right arm down) and the
low-poly is symmetric (both arms down), Blender's "Selected to Active" texture baking
**will produce incorrect textures**.

### Root Cause

Blender's bake system (confirmed via official docs) casts rays from the low-poly mesh
outward along vertex normals to find the high-poly surface and sample its color/normal.
If the high-poly and low-poly don't occupy the same space, rays either:
- Hit the **wrong** high-poly surface (e.g., low-poly right arm ray hits high-poly's raised left arm)
- Miss entirely (producing black/empty patches)

Blender Artists forum expert JA12 confirmed: "Baking those needs to happen so that high
detail surface and low detail surface occupy the same space to get the difference. That's
why you can't bake posed and unposed ones, the two model surfaces are way apart from each
other."

## Correct Flow (Revised 2026-07-09)

```
① Symmetrize HIGH-POLY (bmesh vertex coordinate mirror)
    ↓
② Wrap low-poly template onto the now-symmetric high-poly
    ↓
③ UV unwrap the low-poly
    ↓
④ Bake textures (high and low now occupy same space → correct projection)
```

**Why not symmetrize the low-poly after wrap?**
If you wrap first (on asymmetric high-poly), then symmetrize the low-poly, the low-poly
is now symmetric but the high-poly is still asymmetric → bake projects wrong.

**Why not symmetrize both?**
You only need the high-poly symmetrized before baking. The low-poly will naturally be
symmetric if wrapped onto a symmetric high-poly.

## Facial Micro-Asymmetry

Human faces are naturally ~1mm asymmetric. Baking a slightly asymmetric face onto a
symmetric low-poly template produces sub-pixel errors — acceptable in practice.
Industry consensus: do NOT force-symmetrize faces. Keep natural asymmetry.

## ZBrush Smart ReSym (智能重新对称)

- **Only modifies vertex positions**, NOT UV coordinates or textures
- Confirmed via ZBrush official docs (help.maxon.net/zbr):
  - SmartReSym: "restores symmetry to the object by examining all **points** in the mesh"
  - ReSym: "restores mirror symmetry by adjusting the **positions of vertices**"
  - Symmetry page: Poseable Symmetry "does not use UVs"
- User tested and confirmed: UV and textures remain unchanged after Smart ReSym
- **Caveat**: if vertices move but UV stays fixed, texture sampling shifts
  - Solution: symmetrize BEFORE UV unwrap + baking (then textures are correct)
  - Or use Polypaint as intermediate (texture → Polypaint → ReSym → re-bake)

## Blender bmesh Implementation

`vert.co` (vertex-level) and `BMLoopUV` (loop-level) are **completely independent data layers**.
Modifying `vert.co` has zero effect on UV:

```python
import bmesh
bm = bmesh.new()
bm.from_mesh(mesh)
for vert in bm.verts:
    vert.co.x = -vert.co.x  # Mirror X — UV untouched
bm.to_mesh(mesh)
bm.free()
```

**Plugin**: `mio3io/mio3_symmetry` (GitHub) can independently symmetrize mesh, UV, weights,
shape keys, normals — configure to symmetrize geometry only.
