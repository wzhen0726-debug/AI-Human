# Blender Symmetry, UV & Texture Baking — Pitfalls and Solutions

Research session: 2026-07-08. Sources: Blender 5.1 official docs (Mirror
Modifier, Render Baking, UV Unwrapping). ZBrush behavior based on user
correction and domain knowledge.

## A. Mirror Symmetry and Texture/Material Handling

### The Problem
ZBrush Smart Resymmetry preserves bilateral texture detail — it mirrors
vertex positions but leaves UV coordinates and texture maps unchanged.
The user confirmed ZBrush uses UV-textured models (not just Polypaint/
vertex color), and Smart Resymmetry works correctly on them: geometry
mirrors, UV/texture stays put.

Blender's default mirror operations do NOT behave this way — Mirror
Modifier and Symmetrize both modify UV alongside geometry.

### Blender Mirror Modifier Options (official docs verified)

| Option | What it does | When to use |
|--------|-------------|-------------|
| **Flip UV** | Mirrors UV coords: (0.3, 0.9) → (0.7, 0.1) | When you want mirrored texture display on the symmetric side |
| **UV Offsets** | Shifts mirrored UV to outside image bounds | Prevents UV overlap during baking; mirrored side doesn't participate in bake |
| **Flip UDIM** | Mirrors within each UDIM tile center | High-precision UDIM pipelines |
| **Vertex Groups** | Mirrors .L/.R named groups (target group must pre-exist and be empty) | Rigging weight mirrors |

**Key**: Without "Flip UV" checked, mirrored side UV overlaps original →
both sides show identical texture (not even flipped). With "Flip UV",
texture is mirrored-flipped but BOTH SIDES SAMPLE THE SAME IMAGE REGION.

### Solution: bmesh Vertex-Only Mirror (ZBrush-like behavior)

In bmesh, `vert.co` (3D position) and UV data (`loop[uv_lay].uv`) are
**completely independent data layers**. Modifying `vert.co` does NOT
touch any UV layer. This enables ZBrush-like symmetry:

```python
# Mirror only vertex X coordinates, leave UV untouched
for pos_v in positive_verts:
    match = find_nearest_by_yz(negative_verts, pos_v)
    if match:
        match.co.x = -pos_v.co.x
        match.co.y = pos_v.co.y
        match.co.z = pos_v.co.z
# UV layer automatically preserved — no action needed
```

**Caveat**: If vertices move but UV stays fixed, texture sampling shifts.
For small symmetry corrections (sub-mm), this is negligible. For large
corrections, re-bake textures after symmetrization.

Plugin: `mio3io/mio3_symmetry` — can independently symmetrize mesh,
UV, weights, shape keys, normals.

### Alternative: Apply Mirror → Independent UV Unwrap

1. Complete symmetric modeling, then Apply Mirror Modifier
2. UV unwrap the full model — left and right get independent UV islands
3. Bake textures — each side has independent texture data
- Pros: True bilateral independence
- Cons: UV space utilization ~50% (symmetric regions occupy double space)

## B. UV Auto-Unwrap Pitfalls

### Smart UV Project Limitations
- **Uncontrollable seams**: Auto-cuts at sharp angles — can place seams
  on visually important areas (front of face)
- **Island fragmentation**: Complex models produce many tiny UV islands
- **No symmetry guarantee**: Left/right UV layout may differ
- **Stretching**: High-curvature areas (ears, nose) show visible distortion
- **Verdict**: OK for prototyping. Production characters need either
  manual seam marking + Unwrap, OR the automated dihedral-angle pipeline
  (see `blender-uv-texture-baking` skill: edge-angle seam detection →
  symmetry-axis seam → Angle-Based Unwrap → pack islands).

## C. Texture Baking Pitfalls

### Clothes/Hair Removed → Baking Holes
**Problem**: High-poly has clothes/hair, low-poly doesn't. Projection
rays hit wrong surfaces.

**Solutions** (in order of preference):
1. **Separate high-poly source** (BEST): Split clothes/hair into
   separate objects. Bake body using ONLY body high-poly as source.
2. **Max Ray Distance tuning**: Set small Max Ray Distance (0.002-0.005)
   so rays only hit nearest surface. Too small → black patches. Too
   large → rays penetrate to wrong side.
3. **Cage Object**: Custom cage mesh inflated from low-poly but shrunk
   in clothes/hair regions. Best edge quality but requires manual work.

### Ray Distance Settings Reference

| Scenario | Max Ray Distance | Notes |
|----------|-----------------|-------|
| High/low-poly close fit | 0.005-0.01 (5-10mm) | Normal case |
| Large gap between meshes | 0.02-0.05 or use Cage | Too large risks back-face hits |
| Clothes/hair interference | 0.002-0.005 (2-5mm) | Only hits nearest surface |
| Edge artifacts | Use Cage instead | Cage eliminates edge glitches |

### Topology Impact on Baking Quality
- **Uneven mesh density → uneven UV area allocation**:
  Dense areas (face) → small UV islands → blurry texture
  Sparse areas (torso) → large UV islands → sharp texture
- **Fix**: Use Average Island Scale, increase density in key areas,
  set bake Margin to 16-32px (Extend mode)
