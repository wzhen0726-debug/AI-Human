# Head Cavity Topology Analysis — Eye Sockets, Oral Cavity, Lips

Research date: 2026-07-09. Definitive analysis of MetaHuman BaseMesh interior
geometry, answering: do standard character head meshes have eye socket interior
walls and oral cavity interior walls, or are they open holes?

## Methodology

Analyzed `MetaHuman_BaseMesh.obj` (24,403 vertices, 47,901 faces) using
trimesh + scipy. The analysis script is at `scripts/analyze_head_cavity.py`.

Key techniques:
1. **Watertight check**: `mesh.is_watertight` → False (open shell)
2. **Boundary loop detection**: Find edges with only 1 adjacent face → trace
   into closed loops → each loop is an "opening" in the mesh
3. **Inward-facing face detection**: For each face, compute
   `(face_center - mesh_centroid) · face_normal`. Negative = inward-facing.
4. **Cavity clustering**: Cluster inward-facing faces by spatial proximity
   using `scipy.cluster.hierarchy.fclusterdata` to identify discrete cavities.
5. **Depth profiling**: For each cavity region, histogram face Z-coordinates
   to measure cavity depth from the opening.

## Results

### Overall mesh stats
- Vertices: 24,403 | Faces: 47,901 | Edges: 72,317
- Watertight: **False** (open shell, not a closed volume)
- Boundary loops: **21** (open edges where mesh has holes)
- Inward-facing faces: **10,657 (22.2%)** — significant interior geometry

### Eye sockets — HAVE interior walls

| Metric | Left Eye | Right Eye |
|--------|----------|-----------|
| Eyelid boundary loop | 112 verts | 112 verts |
| Eyelid opening Z position | ~71mm | ~71mm |
| Interior wall faces | ~386 | ~409 |
| Interior wall Z range | 42–68mm | 41–68mm |
| Socket depth from eyelid | ~15–26mm | ~15–27mm |
| Average normal Z | -0.387 | -0.396 |

**Finding**: The eyelid boundary (112-vert loop) is the eye *opening*. Behind
it, mesh continues inward forming the eye socket interior wall. The eyeball
sits inside this pocket. The socket is NOT a simple hole — it has geometry
behind the eyeball position.

### Oral cavity / mouth — HAS interior walls

| Metric | Value |
|--------|-------|
| Lip boundary loop | 168 verts |
| Mouth opening Z position | ~75mm |
| Interior wall faces (Z<72mm) | 925 |
| Interior wall Z range | 35–72mm |
| Cavity depth from lips | ~40mm |
| Interior wall Y range | 195–225mm (upper+lower) |
| Average normal Z | -0.396 |
| Additional upper cavity faces (Z~94mm) | 359 |

**Finding**: The lip boundary (168-vert loop) is the mouth *opening*. Behind
the lips, mesh continues inward ~40mm forming the oral cavity. The cavity
spans both upper (toward nose) and lower (toward chin) interior walls.

### Lips — HAVE interior mesh

| Metric | Value |
|--------|-------|
| Lip region total faces | 6,858 |
| Interior-facing lip faces | 4,621 |
| Exterior-facing lip faces | 1,788 |

**Finding**: Lips have BOTH exterior and interior-facing geometry. The inside
of the lips is not empty — it has mesh that faces into the oral cavity.

### Boundary loops (21 total)

| # | Verts | Center (mm) | Size (mm) | Anatomy |
|---|-------|-------------|-----------|---------|
| 0 | 208 | (0, 149, -42) | 367 | Body/waist bottom |
| 1 | 168 | (0, 198, 75) | 40 | Mouth opening (lip boundary) |
| 2 | 112 | (-11, 198, 71) | 71 | Left eye opening (eyelid) |
| 3 | 112 | (10, 198, 71) | 71 | Right eye opening (eyelid) |
| 4-6 | 52 each | (±31, 264, 73) | 23 | Eye socket area |
| 7-20 | 3-33 | various | 0.3-6 | Small openings (eye area, nostrils) |

## Definitive Answers to Key Questions

### Q1: Is the eye socket an open hole or does it have interior walls?
**Has interior walls.** The eyelid boundary is the opening; behind it, ~390
inward-facing faces per eye form a socket pocket ~15-26mm deep. The eyeball
sits inside this pocket.

### Q2: How is the gap between eyeball and eye socket handled?
- Eye socket interior wall provides backing behind the eyeball
- Eyelid edge loop布线 designed to follow eyeball curvature
- Eyeball is an independent opaque mesh object
- No additional covering needed — interior wall + eyeball suffice

### Q3: Do lips have interior mesh? Is the oral cavity empty or walled?
**Lips have interior mesh** (4,621 inward-facing faces). **Oral cavity has
interior walls** (~2,400 inward-facing faces, 40mm deep). Not empty.

### Q4: If template lacks interior walls, what happens after wrap?
If a template truly has no interior walls (some simplified game meshes may
not), wrap will lose all high-poly cavity information. Must either:
- Use a template WITH interior walls (MetaHuman does — recommended)
- Manually add interior walls after wrap (labor-intensive)

### Q5: Standard practice — does the template come with interior walls?
**Yes.** MetaHuman BaseMesh comes with eye socket interior walls and oral
cavity interior walls. Wrap should fit these interior surfaces too. This is
WHY Shrinkwrap fails on concave features — it pulls interior-wall vertices
to the wrong (exterior) surface. Dense contour anchors around eye rims and
lips are the mitigation (see Bug 4 in landmark-retopology.md).

### Q6: If template has no interior walls, should they be added after wrap?
**Yes, if missing.** Without interior walls:
- Eye rotation reveals empty head interior (visual break)
- Open mouth shows a void
- Lip intersection looks unnatural

Add by: extracting interior geometry from a standard template (MetaHuman)
and fitting to the wrapped mesh, or manual modeling in Blender.

## Implication for the Wrap Pipeline

The fact that MetaHuman templates HAVE interior walls means:

1. **Shrinkwrap must fit interior surfaces too** — not just the exterior face.
   This is harder than exterior-only fitting because NEAREST_SURFACEPOINT
   frequently jumps to the wrong surface in concave regions.

2. **Contour anchors around eye rims and lips are critical** — they pin the
   boundary between exterior and interior mesh, preventing Shrinkwrap from
   collapsing the cavity.

3. **Y-limit pullback (v3)** is partially effective for mouth interior but
   NOT for eye sockets (eyelid vertices have normal Y range). See
   `blender-head-retopology` SKILL.md "Nose & Eye Socket Penetration" section.

4. **Template choice matters** — if using a simplified template without
   interior walls, the wrap result will have open cavities that need
   post-processing. Always verify template has interior walls before wrapping
   (run `scripts/analyze_head_cavity.py` on the template).

## Previous Documentation Correction

Earlier versions of `eyes-teeth-symmetry-stitching.md` described the head mesh
as "an open shell with empty eye sockets and oral cavity." This was misleading
— the mesh is an open shell (not watertight), but the eye sockets and oral
cavity have **interior cavity walls**. They are not "empty" in the sense of
being open holes; they are "empty" only in the sense of not containing
eyeball/teeth/tongue geometry (which are separate mesh objects).

This distinction matters because it determines whether the wrap pipeline needs
to fit interior surfaces (it does) and whether post-wrap cavity patching is
needed (it isn't, if the template has interior walls and they fit correctly).
