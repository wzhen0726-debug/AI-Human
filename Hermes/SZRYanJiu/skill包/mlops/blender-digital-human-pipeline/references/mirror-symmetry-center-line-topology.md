# Mirror Symmetry: Center Line Edge Loop Topology Requirements

Research date: 2026-07-09. Sources: Blender 5.1 official docs (Mirror
Modifier, Shrinkwrap Modifier), ZBrush official docs (via Wayback Machine),
pipeline实测数据. Companion to `symmetrization-texture-baking-definitive.md`.

## (1) What Is the Center Line Edge Loop and Why Is It Required?

**Definition**: A continuous edge loop running along the sagittal plane (X=0),
where all vertices have X coordinate exactly 0. It defines the "mirror seam."

**Blender Mirror Modifier requirement** (official docs verified):
- Mirror Modifier mirrors along Object Origin's local axes. Positive X vertices
  become negative X mirrored copies.
- **Merge option**: "Where a vertex is in the same place (within the Merge
  Distance) as its mirror it will be merged." If center line vertices are at
  X=0, mirrored copy overlaps original → auto-merged → seamless center line.
- **Clipping option**: "Vertices on the mirror plane will be unable to move
  away from the mirror plane as long as Clipping is enabled."
- **Without center line edge loop**: No vertices fall on the mirror plane →
  Merge Distance cannot capture them → two halves remain separate → gap.

**Topology reason**: The center line edge loop ensures:
- Mirrored halves share boundary vertices (merged) → continuous mesh
- Subdivision Surface doesn't crack at center
- Rig control points can drive symmetrically

## (2) Problems Without Center Line Edge Loop

| Problem | Cause | Severity |
|---------|-------|----------|
| Gap | Center verts X≠0, Merge can't capture them | High |
| Broken/overlapping faces | Non-symmetric center verts mirror into交错geometry | High |
| Vertex misalignment | No center constraint, mirror side fully determined by non-symmetric original | Med-High |
| Subdivision cracks | No continuous center loop → CC subdiv cracks at axis | High |
| Weight binding errors | Left/right weights don't mirror | Med |
| UV/texture misalignment | Center UV seam not at X=0 → wrong bake stitching | Med |

**Pipeline实测** (`landmark-retopology.md` Bug 5): PROJECT-mode Shrinkwrap
broke symmetry — left/right eye Y delta 12.3mm, mouth Z delta 8.3mm — because
projection had no center line X=0 constraint.

## (3) MetaHuman Topology — Satisfies the Requirement

### Head (MH_Head_01.obj, ~8.2K verts, pure quads)
- **Symmetric topology confirmed**: All 12 facial anchor points and ~52 contour
  anchors have left/right symmetric template vertex indices.
- **Center line edge loop exists**: Sagittal edge loop (nose bridge → nose tip
  → philtrum → chin → neck front), all at X=0.
- **Boundary loops symmetric** (`head-cavity-topology-analysis.md`): Left eye
  (112 verts) = Right eye (112 verts); mouth (168 verts) centered on X=0.

### Body (~20K-30K+ verts)
- Center line edge loop: chest center → navel → pubic symphysis → spine →
  posterior neck.
- A-pose (arms 15-20°) but center axis still at X=0.

### Why MetaHuman guarantees symmetry
- Identity Solve uses non-rigid ICP + symmetric constraints
- Database retrieval returns symmetric approximations
- Rig binding requires symmetric control point layout

## (4) Shrinkwrap: Preventing Center Line Vertex Displacement

### Problem
Shrinkwrap NEAREST_SURFACEPOINT finds nearest target surface point. If target
high-poly has micro-asymmetry (real scans almost always do), center line
vertices get pulled off X=0.

### Official mechanism — Vertex Group
Shrinkwrap Modifier has a Vertex Group field: "If a vertex is not a member of
this group, it is not displaced (same as weight 0)." Can exclude center line
verts from Shrinkwrap.

### Pipeline pitfall — hard exclusion causes pinch
(`blender-head-retopology` v3.20 finding): If center line verts are completely
frozen (skip all smoothing), neighbors get pulled → pinch at anchor neighbors.
Fix: spring-weight anchoring (0.3× weight) instead of hard lock. But this
introduces micro-asymmetry.

### NEAREST vs PROJECT for center line
- **NEAREST_SURFACEPOINT**: symmetric (eye Y delta 0.9mm) — correct choice
- **PROJECT mode**: breaks symmetry (eye Y delta 12.3mm) — NEVER use on faces
  with any surface asymmetry

## (5) Countermeasures — Constraining Center Line to X=0

### Method A: Vertex Group exclusion (simplest, official)
1. Select center line edge loop vertices on template
2. Create Vertex Group "center_line"
3. Set weight 0 (or remove from group)
4. In Shrinkwrap Modifier, select that Vertex Group
5. Center verts not moved → stay at X=0
**Risk**: Hard exclusion → pinch. Needs follow-up Laplacian smooth.

### Method B: bmesh X=0 enforcement (RECOMMENDED)
After each Shrinkwrap round, force center line vertices' X to 0:
```python
import bmesh
bm = bmesh.new()
bm.from_mesh(mesh)
for vert in bm.verts:
    if abs(vert.co.x) < 0.002:  # 2mm threshold for center line identification
        vert.co.x = 0.0  # Force X=0, keep Y/Z from Shrinkwrap
bm.to_mesh(mesh)
bm.free()
```
**Why best**: Allows Shrinkwrap to fit Y and Z at center line, only locks X.
Preserves surface fit quality while guaranteeing mirror compatibility.

### Method C: Center line verts as anchors
Add center line vertices to the anchor list, targeting the high-poly's center
line detection points (if high-poly already symmetrized, its center is at X=0).

### Method D: Mirror Modifier Clipping
Enable Clipping in Mirror Modifier. But Clipping only works in Edit Mode
transform — may not constrain modifier-level Shrinkwrap displacement.

### Method E: Pre-symmetrize high-poly (ROOT FIX)
1. Symmetrize high-poly mesh first (bmesh vert.co mirror, X→-X, preserve UV)
2. Wrap template onto the now-symmetric high-poly
3. Symmetric target → Shrinkwrap naturally doesn't pull center off X=0
**This is the most fundamental solution.** See
`symmetrization-texture-baking-definitive.md` for the full symmetrize→wrap→bake
flow.

## (6) ZBrush Smart ReSym vs Blender Mirror Modifier

### ZBrush Smart ReSym (官方文档)
- SmartReSym: "restores symmetry by examining all **points**... determining
  which were originally intended to lie in mirror-symmetrical positions"
- ReSym: "adjusting the **positions of vertices** which lie in
  **near-symmetrical positions**"
- Poseable Symmetry: "100% dependent on your mesh being **topologically
  symmetrical**" — requires symmetric topology structure, not strict X=0

### Comparison

| Feature | ZBrush Smart ReSym | Blender Mirror Modifier |
|---------|--------------------|--------------------------|
| Needs center line edge loop? | Not strictly | **Must** |
| How it works | Intelligent vertex-pair matching | Plane flip + Merge |
| UV affected? | No (positions only) | Optional Flip UV |
| Center not at X=0? | Can handle (smart match) | Fails (unless origin moved) |
| Topology requirement | Topologically symmetrical (connection structure) | Vertices on mirror plane |

### Key difference
- **ZBrush Smart ReSym** is more forgiving — can recover symmetry even when
  center vertices drift slightly off X=0, by matching near-symmetric vertex
  pairs. Still requires topology to be *roughly* symmetric.
- **Blender Mirror Modifier** is strict — needs vertices exactly on the mirror
  plane for Merge to work.
- **Blender bmesh manual mirror** can mimic ZBrush behavior (Y/Z nearest-neighbor
  matching of left/right vertex pairs), not strictly needing X=0 center line.

## Practical Recommendations

1. **Low-poly template MUST have center line edge loop** — Blender Mirror
   Modifier hard requirement, also needed for rigging.
2. **MetaHuman template satisfies this** — head and body have continuous center
   line edge loop at X=0.
3. **Constrain center line during Shrinkwrap** — use Method B (bmesh X=0
   enforcement after each round) or Method E (pre-symmetrize high-poly).
4. **Use NEAREST, never PROJECT** — PROJECT breaks left/right symmetry.
5. **Pre-symmetrize high-poly is the root fix** — symmetric target means
   Shrinkwrap naturally preserves center line.
6. **ZBrush Smart ReSym is more forgiving** but still needs roughly symmetric
   topology. Blender bmesh mirror can achieve similar flexibility.
