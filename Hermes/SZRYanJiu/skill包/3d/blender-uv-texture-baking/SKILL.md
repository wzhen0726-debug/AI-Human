---
name: blender-uv-texture-baking
description: >-
  Blender UV unwrapping, texture baking, and mirror-symmetry texture handling.
  Covers Smart UV Project quality, manual seam workflows, Selected-to-Active
  baking parameters (ray distance, cage, margin), and Mirror Modifier UV/texture
  behavior. Verified against Blender 5.1 official documentation.
version: 1.0.0
author: Hermes Agent
tags: [blender, uv, texture, baking, mirror, symmetry, 3d]
platforms: [windows]
---

# Blender UV & Texture Baking

Practical knowledge for UV unwrapping, texture baking, and mirror-symmetry
texture handling in Blender. Verified against Blender 5.1 official docs
(see `references/blender-docs-findings.md` for source excerpts).

## Mirror Modifier — UV & Texture Behavior

### Default: geometry-only mirror
The Mirror Modifier mirrors **geometry only** by default. UV coordinates on the
mirrored side are **identical to the original** (overlapping), NOT flipped.

### Data panel options (must be explicitly enabled)

| Option | Effect |
|--------|--------|
| **Flip UV** | Mirrors UV coordinates across image center. (0.3, 0.9) → (0.7, 0.1) |
| **UV Offsets** | Shifts mirrored UVs outside image bounds. **Designed for baking** — prevents UV overlap artifacts during bake while preserving display |
| **Flip UDIM** | Mirrors texture coordinates around each UDIM tile center |
| **Vertex Groups** | Mirrors vertex groups (requires .L/.R naming convention; target group must pre-exist and be empty) |

### Three approaches to texture-preserving symmetry

1. **UV Offsets method** (simplest): Enable Flip UV + set UV Offset (e.g. U=1.0).
   Mirrored UVs go off-image. Bake excludes them; display still shows mirrored
   texture. Limitation: sides are mirror-flipped, not independent.

2. **Apply-then-unwrap** (most flexible): Apply Mirror Modifier → unwrap full
   model → both sides get independent UV islands → independent textures.
   Closest to ZBrush behavior. Downside: double UV space for symmetric regions.

3. **UDIM method**: Enable Flip UDIM → mirrored side on separate UDIM tile
   (e.g. 1001 vs 1002) → truly independent textures per side. Best for
   high-precision character pipelines.

### Approach 4: bmesh vertex-mirror (closest to ZBrush Smart Resymmetry)

The three approaches above all create **new geometry** on the mirrored side,
which means new UV assignments are generated. To truly replicate ZBrush Smart
Resymmetry — mirror geometry while UV stays **completely untouched** — use
bmesh to modify `BMVert.co` in-place. This works because of a key architectural
fact:

- **Vertex coordinates** (`BMVert.co`) live on **verts**
- **UV coordinates** (`loop[uv_lay].uv`) live on **loops** (face corners)
- These are **independent custom-data layers** — modifying `vert.co` never
  touches any UV layer

This means you can iterate verts, match left-side to right-side by Y/Z
proximity, and overwrite the target side's `co` with the mirrored source — UV
layers are automatically preserved because you never touch them.

**When to use**: models with already-existing UV maps and textures where you
need to fix geometry asymmetry without redoing UVs/textures. Requires
topologically symmetric mesh (same vertex count and connectivity on both
sides).

**Pitfall**: The vertex-matching step is the hard part. Left/right verts must\nbe paired by nearest Y/Z distance. For large meshes, use a spatial hash (e.g.\n`mathutils.kdtree.KDTree`) to avoid O(n²) blowup. Center-axis verts (|x| <\nthreshold) should be snapped to x=0.\n\n**CRITICAL: Topology-asymmetric meshes cannot be bmesh-mirrored in Blender.**\nIf the mesh has even a small vertex-count difference between left/right sides\n(e.g., 13 verts difference on a 128K mesh), spatial matching maxes out at ~71%\nand produces broken faces at every unmatched vertex boundary. **Multiple\nmatching strategies have been tested and all hit the same ~71% ceiling:**\n- Pure spatial cKDTree (bidirectional + normal + degree filter): 71.4%\n- Curvature seeds + Dijkstra geodesic + single-round BFS: 72.7%\n- Curvature seeds + all-seed geodesic + multi-round BFS: 68.4% (worse)\n- Blender's `bpy.ops.mesh.symmetry_snap()`: ~39% (31K/128K failed)\n\nCurvature-based seeds produce higher-quality seed pairs (66 unique 1:1 pairs\nvs 144-205 from center-axis), and Dijkstra geodesic distance is computationally\nviable in Python (~0.6s per source on 128K verts), but neither improves the\noverall match rate because the bottleneck is topological: unmatched vertices\ngenuinely lack symmetric counterparts. Multi-round BFS with progressive\nthreshold relaxation actively HURTS (68.4% vs 72.7% single-round) because it\nfragments the natural BFS propagation flow.\n\n**ZBrush Smart ReSym works perfectly on these same meshes** (~10 seconds,\nuser-confirmed) — the algorithm is C++ optimized and handles topology\nasymmetry gracefully. **Recommendation**: For topology-asymmetric high-poly\nmeshes, use ZBrush Smart ReSym (import OBJ → Smart ReSym → export) before\nimporting to Blender. For Blender-only pipelines, use the **upgraded\ndelete-half mirror technique** (see below). For topology-symmetric meshes\n(production templates, MetaHuman), bmesh mirror works 100% — verified\non a 482-vertex sphere with perfect symmetry and UV preservation.

### Upgraded delete-half mirror with negative UV restoration

This is the best Blender-only approach for topology-asymmetric meshes. It
achieves perfect symmetry, zero broken faces, and 65.9% original negative UV
preservation:

1. Save positive-side vertex UVs AND negative-side vertex UVs (both sides)
2. Delete negative-side (X<0) vertices
3. Apply Mirror Modifier → perfect geometric symmetry + no broken faces
4. Positive-side new vertices: match to original positive coords → restore
   positive UVs (100% match)
5. Negative-side new vertices: match to original negative coords using
   abs(X)+Y+Z → restore negative UVs (65.9% match). Fallback to positive
   UV for the remaining 34.1% where original negative vertices are too
   far (deformation areas).

**Key difference from naive delete-half mirror**: The naive approach copies
positive UVs to the negative side, losing all negative UV detail. The
upgraded approach preserves original negative UVs wherever possible.

**Performance**: 5 seconds total for 128K vertices. Uses cKDTree for batch
matching and `foreach_set("vector", ...)` for UV writes.

See `references/mirror-symmetry-test-results.md` for full 10-approach
comparison and detailed findings. **Untested but potentially viable** for\nBlender-only >90% matching: ARAP (As-Rigid-As-Possible) deformation and\nlibigl C++ non-rigid ICP — these remain the only unexplored paths.\n\n**Blender 5.1 foreach_get/foreach_set API quirk**: When batch-reading or\nwriting UV data, use `uv_layer.uv.foreach_get("vector", flat_float32_array)`\nand `uv_layer.uv.foreach_set("vector", flat_float32_array)`. Do NOT use\n`foreach_get("x", ...)` or `foreach_get("y", ...)` — Blender 5.1 raises\n`AttributeError: foreach_get(..) elements have no attribute 'x'`. The\ncorrect property name is `"vector"`, and the array must be a flat\n`np.float32` array of shape `(nloops*2,)` interleaved as [u0, v0, u1, v1, ...].\nSimilarly, `mesh.vertices.foreach_get("co", flat_float32)` reads all vertex\ncoordinates, and `mesh.loops.foreach_get("vertex_index", int32_array)` reads\nloop→vertex mapping. These batch APIs are **1000x faster** than per-element\nPython loops for meshes >10K vertices — per-loop `uv_data[li].uv.x = val` will\ntimeout on meshes with >100K loops.\n\nSee `references/bmesh-geometry-mirror-keep-uv.md` for full API details and a\nworking script template, and `references/mirror-test-results.md` (in the\n`blender-digital-human-pipeline` skill) for 13 tests covering symmetric and\nasymmetric meshes.

### ZBrush Smart Symmetry comparison — verified against official docs

ZBrush has three relevant symmetry tools, all of which operate on **vertex
positions only** and do **not** touch UV data. Verified against Maxon official
documentation (help.maxon.net/zbr, 2026-07-08 — see
`references/zbrush-resymmetry-docs-findings.md` for verbatim excerpts).

| Feature | Panel | What it operates on | UV affected? | Polypaint affected? |
|---------|-------|-------------------|-------------|-------------------|
| SmartReSym | Deformation | Vertex positions only | No | Yes (travels with verts) |
| ReSym | Deformation | Vertex positions only | No | Yes (travels with verts) |
| Mirror and Weld | Geometry > Modify Topology | Mirror + weld (topology change) | No | Yes (explicitly stated in docs) |
| Poseable Symmetry | Transform (uses SmartResym) | Vertex positions (topology-based) | No ("does not use UVs") | Yes |

**Key distinction — Mirror and Weld vs Smart Resymmetry**:
- **Mirror and Weld** (Geometry > Modify Topology): **topology operation** —
  mirrors the model along an axis and welds all points. Changes polygon count
  and connectivity. Explicitly documented as transferring polypaint.
- **SmartReSym** (Deformation): **deformation operation** — examines all
  points, finds mirror-symmetric pairs, restores symmetry by moving existing
  vertices in-place. Does NOT change polygon count or connectivity. Supports
  masking one side to lock it.
- **ReSym** (Deformation): simpler version of SmartReSym — adjusts vertices
  in "near-symmetrical" positions. Less sophisticated; docs recommend
  SmartReSym for complex cases.

All three leave UV coordinates completely untouched. The reason this "works"
for ZBrush workflows is architectural:

1. **Polypaint (per-vertex color) travels with vertices automatically.** When
   SmartReSym moves vertices to their mirrored positions, polypaint moves with
   them. This is why Mirror and Weld's docs explicitly state "will also
   transfer polypaint information" — polypaint is the primary color data in
   ZBrush sculpting, and it naturally follows vertex repositioning.

2. **UV mapping is a separate, post-sculpting step.** ZBrush's UV Map
   sub-palette (Tool > UV Map) has dedicated UV operations (Flip U, Flip V,
   Cycle UV, etc.) that are completely independent from Deformation. The
   official Poseable Symmetry documentation states explicitly: "It does not
   use UVs and is 100% dependent on your mesh being topologically
   symmetrical."

3. **Texture maps are UV-sampled, not vertex-attached.** The Texture Map
   sub-palette provides conversion tools (New From Polypaint, Polypaint From
   Texture) precisely because polypaint and texture maps are different data
   representations.

**The texture-misalignment consequence (important)**: If a model already has
UV maps and texture maps applied, executing Resymmetry will:
- Move vertices to symmetric positions ✅
- Leave UV coordinates exactly as they were ✅ (UV data is never destroyed)
- **Break texture alignment** ❌ — vertices that moved to the symmetric
  position still have their original UV coordinates, which now point to the
  wrong part of the texture. The texture is sampled at the old UV location,
  but the vertex is now at a different 3D position.

**Exception**: If the UV layout is itself symmetric (left and right halves
are mirror images in UV space), the texture will still appear correct after
Resymmetry because the symmetric vertex pairs map to symmetric UV locations.

**Practical ZBrush workaround for UV-textured models**: Use polypaint as a
bridge — Texture → Polypaint From Texture → Resymmetry (polypaint mirrors
correctly) → re-unwrap UVs → New From Polypaint (regenerate texture).

**Alternative community workaround** (from ZBrushCentral): clone model →
mirror it → append as subtool → store morph target on original → use ZProject
brush or ProjectAll to transfer detail → switch morph target back. This
mirrors polypaint but, as the forum user noted, "if you have UV's laid out
that's another story altogether" — UV-based textures remain unhandled. See
`references/zbrushcentral-resymmetry-community-findings.md` for details.

**Pitfall**: Do not assume Blender Mirror = ZBrush Smart Resymmetry for
textures. Blender's Symmetrize operator and Mirror Modifier both create **new
geometry** (new verts/edges/faces on the mirrored side), which means new UV
assignments are generated for those new elements. ZBrush's Smart Resymmetry
instead **moves existing vertices** in-place, so UV loops are never touched.
To replicate ZBrush behavior in Blender, use the bmesh vertex-mirror technique
below.

## UV Unwrapping

### Smart UV Project — when to use and when to avoid

- **Good for**: quick prototyping, simple/organic shapes, test unwraps, **AND high-poly QR retopo meshes (>10K faces)** where edge-angle seam marking produces per-face fragmentation
- **Avoid for**: production characters requiring symmetric UVs, high-curvature areas (ears, nose)
- **On QR retopo meshes (>10万面)**: `edges_select_sharp(sharpness=0.96)` (~55°) marks EVERY non-coplanar edge as a seam → every face becomes a separate UV island → completely fragmented bake. Smart UV Project (`angle_limit=66°`) avoids this by auto-merging adjacent faces into reasonable islands. User confirmed the edge-angle approach produces "每个面都是碎的" (every face is fragmented).
- **island_margin tuning**: 0.001 is too small (islands touch). User requires 0.01 for clear gaps. UV range shifts from [0.001,0.999] to [0.006,0.994]. Previously user also corrected 0.03 as "太保守" (too conservative). **Recommended: 0.01 for production, 0.002 for space-maximizing MVP.**
- **Known issues**:
  - Uncontrollable seam placement — cuts may appear on visually important areas
  - UV island fragmentation — complex meshes produce many small islands
  - No symmetry guarantee — left/right UV layouts may differ
  - Visible distortion at high-curvature regions

### Recommended production workflow

1. Mark seams manually along natural boundaries (hairline, clothing edges,
   mirror axis)
2. For bilateral models: **seam along the mirror axis** so both halves can
   overlay on the same UV space (official doc recommendation)
3. Unwrap → check with test grid image → adjust seams → repeat
4. Use Average Island Scale to balance UV island sizes
5. Pack Islands for efficient layout

### Automated UV Pipeline (for batch / digital-human pipelines)

For fully automated pipelines (no manual seam marking), use
`scripts/auto_uv_pipeline.py`. It implements:

1. **Dihedral-angle seam detection** — iterates all edges, marks those with
   face angle ≥ threshold (default 55°) as seams. Uses bmesh
   `edge.calc_face_angle()` — no operator dependency.
2. **Symmetry-axis seam** — marks all edges whose both vertices lie on the
   symmetry plane (default X=0) as additional seams. **Critical** for human
   models — without it, left/right UV layouts will differ.
3. **Angle-Based Unwrap** — `bpy.ops.uv.unwrap(method='ANGLE_BASED')` —
   far better than Smart UV Project for organic meshes.
4. **Pack Islands** — `bpy.ops.uv.pack_islands(rotate=True, scale=True)` —
   optimizes UV space utilization.

Usage: `blender --background model.blend --python auto_uv_pipeline.py`

**Why this beats Smart UV Project for human models**:
- Seam placement is predictable (only at sharp angles + symmetry axis)
- Left/right UV symmetry is guaranteed
- Far fewer fragmented islands (Smart UV Project: 50-200+; this: ~10-30)
- Standard Unwrap preserves texel density better on organic surfaces

**Angle threshold tuning**: 55° is a good starting point for human body
meshes. Lower (45°) = more seams = less stretching but more islands.
Higher (65°) = fewer seams = more stretching. For faces, use 50-55°.

**Alternative tools for comparison**:
- **UVPackmaster** (paid, $29-49): GPU-accelerated UV packing only (not
  unwrapping). Has Python SDK for scripting. Free SDK available.
- **RizomUV** (paid, $299-1499): professional UV unwrapper with **full headless/CLI support** via RizomUVLink (ZMQ API) and Lua scripting. Lua scripts can automate: import → unwrap → pack → export. Can run on headless Linux/Windows servers. rizomuv-mcp (GitHub: fkrn75/rizomuv-mcp) provides MCP protocol bridge for AI-driven control.
- **Magic-UV** (free, Blender built-in): UV editing utilities, no auto-seam
  or auto-unwrap.

### Seam strategy (from official docs)

- Fewer seams = less stretching but harder texturing at boundaries
- More seams = less stretching but more UV islands to manage
- Hide seams where they won't be seen (back of head, under clothing)
- 3D paint (projection painting) handles seams better than 2D texturing
- Use `Select Linked` in Face Select mode to verify seam continuity

**Pitfall**: Unwrapping before geometry is finalized wastes effort. New faces
added after unwrapping get auto-assigned UVs but may need manual correction.

## Texture Baking (Cycles)

### Selected to Active — the core workflow

Rays cast from low-poly (active) object inward toward high-poly (selected)
objects. Key parameters:

### Max Ray Distance
- Controls how far inward rays travel to find the high-poly surface
- **Too large**: rays pass through model, hit backside → reversed artifacts
- **Too small**: some areas get no bake data → black patches
- Only available when NOT using Cage

### Cage mode
- Cage = "ballooned" version of low-poly mesh that controls ray direction
- **Cage Extrusion**: inward ray cast distance when using cage
- **Cage Object**: manually created cage for precise control
- **Requirement**: cage must have same topology as low-poly (face count + order)
- Produces better edge results than raw ray distance
- Without cage: rays follow normals → edge glitches (documented behavior)

### Clothing/hair interference during baking

When high-poly has clothing/hair but low-poly doesn't:

| Method | Approach | Tradeoff |
|--------|----------|----------|
| Split high-poly | Separate body/clothes/hair, bake each independently | Most reliable, more setup |
| Small ray distance | Set Max Ray Distance very small (2-5mm) | Risk of unbaked patches |
| Custom cage | Manually sculpt cage to avoid hair/clothes regions | Best quality, most effort |
| Full UV retention | Keep UV islands for hidden regions, bake everything, delete unwanted texels after | Wastes UV space but safe |

**Recommended**: Split high-poly by material/region and bake each part
separately. This is the most reliable approach.

### Pose and symmetry mismatch — the #1 cause of broken bakes

**Fundamental rule**: Selected to Active requires the high-poly and low-poly
to **spatially coincide**. The rays cast from low-poly inward must hit the
corresponding high-poly surface. If the two models are in different poses
(e.g., high-poly has one arm raised, low-poly is symmetric with both arms
down), the low-poly's rays will hit the **wrong** high-poly surface or miss
entirely — producing garbage textures.

This is confirmed by both the Blender docs ("rays are cast from the
low-poly object inwards towards the high-poly object") and community
consensus (Blender Artists: "you can't bake posed and unposed ones, the
two model surfaces are way apart from each other").

**Correct workflow order**:
1. Determine final high-poly form (symmetric or asymmetric)
2. Symmetrize high-poly IF a symmetric result is needed
3. Wrap/retopologize low-poly to match high-poly's spatial form
4. UV unwrap low-poly
5. Bake — high and low now spatially coincide

**Pitfall**: Do NOT wrap the low-poly first, then symmetrize the low-poly,
then bake. The low-poly will no longer match the asymmetric high-poly's
space. Always symmetrize the high-poly BEFORE wrapping.

**Facial asymmetry**: Industry consensus is to NOT force-symmetrize faces.
Natural facial asymmetry (a few mm) is within ray-distance tolerance and
does not break baking. Forcing symmetry produces an uncanny, obviously
fake look. UVs can still be symmetric (shared L/R space) while the bake
preserves the slight asymmetry from the high-poly sculpt.

See `references/asymmetric-baking-findings.md` for full research findings,
solution comparison table, and UV-symmetry vs geometry-symmetry matrix.

### Margin settings

- **Extend**: copies border pixels outward (simple, fast)
- **Adjacent Faces**: fills margin using pixels from adjacent faces across UV
  seams (better for visible seams)
- **Size**: 16-32px typical for production; prevents mip-map seam artifacts

### Bake types reference

| Type | Use case |
|------|----------|
| Combined | All materials + lighting (except specularity) |
| Normal | Surface normal direction (Tangent space default — correct for animated objects) |
| Ambient Occlusion | AO only, ignores lights |
| Diffuse/Glossy/Transmission | Individual material passes |
| Emit | Emission/glow color |
| Position | World-space XYZ in RGB |
| UV | UV coordinate visualization |

### Normal map baking — space matters
- **Tangent** (default): independent of transform/deformation — right for
  animated objects. Match bake space to Image Texture node's Normal Map setting.
- **Object**: object coordinates — dependent on deformation.
- **Swizzle**: controls which axis maps to R/G/B channels.

**⚠️ Blender 5.1: `NodeLinks.remove()` signature changed (2026-07-31)**: `nt.links.remove(from_socket, to_socket)` raises `TypeError: NodeLinks.remove(): takes at most 1 arguments, got 2`. In Blender 5.1, `remove()` accepts only a single `NodeLink` object. Additionally, removing links while iterating over `nt.links` causes `ReferenceError: StructRNA of type NodeLink has been removed`. **Fix**: copy the link list before iterating, and remove by link object:
```python
for link in list(nt.links):
    if link.to_node == target_node and link.to_socket.name == 'Normal':
        nt.links.remove(link)
```
Do NOT use `nt.links.remove(node1.outputs['X'], node2.inputs['Y'])` — that API no longer exists.

**⚠️ Blender 5.1: `colorspace_settings.name` clears baked pixel data**: Setting `tex_node.image.colorspace_settings.name = 'Non-Color'` on a Normal map image that ALREADY has baked pixel data DESTROYS the data — the image becomes all zeros. Set colorspace BEFORE `bpy.ops.object.bake(type='NORMAL')`, never after. In `connect_textures()`, only create node connections; do NOT modify image properties.

**⚠️ Blender 5.1: `pass_filter` does NOT accept 'NORMAL'**: `bake(type='NORMAL', pass_filter={'NORMAL'})` raises `TypeError`. Valid values: 'NONE', 'EMIT', 'DIRECT', 'INDIRECT', 'COLOR', 'DIFFUSE', 'GLOSSY', 'TRANSMISSION'. Use `bake(type='NORMAL')` without pass_filter.

**⚠️ Adaptive bake distance**: Fixed small distance causes black patches on large models. Compute: `max(0.1, model_max_bbox * 0.15)`.

**⚠️ Bake orientation mismatch — the #1 cause of broken textures (2026-07-17)**: When low-poly and high-poly are in different orientations (e.g., low-poly rotated 90° in repair stage, high-poly imported from original GLB without rotation), bake rays miss entirely. This produces 55-95% black pixels — the single most destructive bake failure. **Fix**: After importing the high-poly source, detect orientation via `dim_y > dim_x * 2` (arms along Y) and rotate to match low-poly via bmesh (`new_x = old_y; new_y = -old_x`). Verify both meshes have the same bbox orientation before baking. The user rated the result of this mismatch as "基本上完全不对" (basically completely wrong) — 10/100 quality score. **Always check high/low bbox alignment before baking** — it takes 2 lines of Python and prevents the worst bake failure mode.

**⚠️ Flipped normals cause 56% black pixels (2026-07-16)**: AI-generated meshes (Tripo etc.) often have ~43% of faces with inward-pointing normals. Bake rays shoot along the low-poly normal — if it points inward, the ray misses the high-poly, producing a black pixel. **Always run `bpy.ops.mesh.normals_make_consistent(inside=False)` on BOTH high-poly and low-poly before baking.** Detect flipped normals: `f.normal.dot(f.calc_center_median()) < 0`. See `blender-digital-human-pipeline/references/bake-normals-flipped-faces-fix.md` for full bake distance tuning results (0.02m→56% black, 0.08m→28.5%, diminishing returns past 0.12m).

**⚠️ Smart UV Project for retopo meshes**: The angle-based seam pipeline (55° threshold) produces only 65 seams on a flat Quad Remesher output — insufficient for full UV coverage (~50% empty space). However, **Smart UV Project is also bad for retopo meshes**: it creates 841-894 islands on a 224K-face Quad Remesher output (nearly every quad becomes its own island), producing 82-95% black texture pixels. **Best approach for retopo meshes**: mark only a few strategic seams (back center + crotch + armpits) with very tight tolerance (0.5% of width for X), then use Angle-Based Unwrap. This produces ~420 islands with 8304 seams — far from ideal but the best automated option found. **Never use Z-band ring cuts (neck/waist/ankle) with wide tolerance** — they mark 128K+ edges and collapse every face into a separate island (95% black).

**⚠️ Too many seams = UV island fragmentation disaster (2026-07-17)**: On a 178K-face Quad Remesher character mesh, 6672 strategic seams produced **3110 UV islands** — one giant island with 175470 faces and 3089 tiny single-face islands. This causes catastrophic bake failure (rays hit island boundaries). **Root cause**: the back-center + armpit + crotch seams use wide Z-band tolerance (±0.01×H), which catches almost every edge in those bands on a dense retopo mesh. **Fix**: reduce to exactly **7 seams** — back center line (X=0, Y>0), left armpit (X<0, Z≈0.76H), right armpit (X>0, Z≈0.76H), left leg inner (X<0, Z≈0.3H), right leg inner (X>0, Z≈0.3H), neck ring (Z≈0.83H), waist ring (Z≈0.55H). Use **very tight tolerance**: ±0.003×W for X, ±0.04×H for Y. Use a soft condition (`< yt`, not `== 0`) to catch slightly-off-center edges. Target: <200 seams, <50 islands. **Verify after unwrap**: island count ≤ 50, largest island ≥ 80% of faces. **Never use Z-band ring cuts (neck/waist/ankle) with wide tolerance** — they mark 128K+ edges and collapse every face into a separate island (95% black). **Angle-based unwrap on 178K faces can timeout (>300s)** — consider reducing face count first or using a faster unwrap method.

**⚠️ Cage baking dramatically reduces black pixels (2026-07-17)**: For AI-generated high-poly meshes (Tripo, 193万面) baked onto Quad Remesher low-poly (22万面), the high-poly has ~43% flipped normals and internal surfaces that cause ray-miss black pixels. Full tuning progression on a 0.976m-tall model:

| Config | Black pixels | Notes |
|--------|:---:|-------|
| 0.02m ray, no cage, no normal recalc | 55.9% | Many flipped normals |
| 0.05m ray, no cage, normals recalc'd | 34.5% | Improved |
| 0.08m ray, no cage, normals recalc'd | 28.5% | Diminishing returns |
| 0.12m ray, no cage, normals recalc'd | 28.5% | Plateau |
| 0.15m ray, no cage, normals recalc'd | 45.3% | Got worse (UV changed) |
| **0.2m ray + cage (0.15m extrusion), normals recalc'd** | **19.2%** | **Best result** |

**Key lessons**: (1) Always `normals_make_consistent(inside=False)` on BOTH high and low poly before baking. (2) Cage mode (`use_cage=True, cage_extrusion=0.15`) with large max_ray_distance (0.2m) is the most effective combination for meshes with surface misalignment. (3) Without cage, increasing ray distance past 0.12m gives diminishing returns because rays start hitting back faces. (4) The remaining ~19% black is from the Tripo high-poly's internal surfaces/cavities that no ray distance can fix — would require cleaning the high-poly before baking.

**⚠️ Cage with max_ray_distance=0 is best for AI meshes (2026-07-17)**: For AI-generated high-poly (Tripo, 193万面) with internal surfaces and 43% flipped normals, the optimal config is `use_cage=True, cage_extrusion=0.3, max_ray_distance=0.0` (let Cage fully control ray direction, no distance limit). This produced 14.7% black pixels (down from 19.2% with cage_extrusion=0.15 + max_ray_distance=0.2). Setting `max_ray_distance=0` tells Cycles to rely entirely on the Cage mesh for ray guidance, which prevents rays from hitting internal surfaces. Combined with `normals_make_consistent(inside=False)` on both meshes and 128 samples, this is the recommended default for any AI-generated mesh bake. Remaining ~15% black is from the Tripo high-poly's internal surfaces/cavities that no ray can reach — would require cleaning the high-poly before baking.

**⚠️ Angle-based unwrap on dense retopo meshes can timeout (>300s)**. On 178K-face Quad Remesher output, `bpy.ops.uv.unwrap(method='ANGLE_BASED')` can exceed 5 minutes. Workaround: use `bpy.ops.uv.smart_project()` for quick tests, or reduce face count before unwrapping.

**⚠️ Simple back-center seam + Unwrap as fallback (2026-07-20)**: When strategic seams with wide Z-band tolerance produce 3000+ fragmented islands, fall back to a SINGLE back-center seam + Angle-Based Unwrap. Mark edges where X≈mid_x, Y>0, Z∈[5%,95%]×H — with very tight X tolerance (0.003×W). This produces a single clean seam splitting front/back, resulting in ~400 islands for a 90K-face retopo mesh. Simpler and more reliable than multi-seam approaches. Script: `uv_simple.py` in `blender-digital-human-pipeline/scripts/`.

**Pitfall**: On dense retopo meshes, even a single seam produces 400-800 islands (each averages 200-400 faces). Smart UV Project produces 3110 islands (57 faces/island), multi-seam strategic produces 3110. Single-seam Unwrap is the least-fragmented automated option found. **For 90K faces, ~400 islands is acceptable** — the seam is on the back (hidden), and island distribution is reasonable.

**⚠️ Blender 5.1 MINIMUM_STRETCH (ARAP) unwrap — NEW method, tested 2026-07-20 (poor result)**: Blender 5.1 added a third `method` enum to `bpy.ops.uv.unwrap()`: `MINIMUM_STRETCH` (As-Rigid-As-Possible). Parameters: `iterations` (default 10, tested 20), `no_flip`, `use_weights`, `weight_group`, `weight_factor`. Tested on 90K-face QR mesh with 455 minimal seams: produces IDENTICAL 84 islands as CONFORMAL/ANGLE_BASED, but 10-15x slower (48s vs 3s CONFORMAL vs 35s ANGLE_BASED). Checkerboard quality unchanged (2/10). **NOT recommended for background pipelines** — poor time/quality ratio. CONFORMAL (LSCM) remains the fastest viable unwrap for QR meshes. The fragmentation is topology-driven (seam placement), not solver-driven — switching algorithms does not help.

**⚠️ Blender 5.1 `average_islands_scale` + `pack_islands` — confirmed working in `--background --factory-startup` (2026-07-20)**: API signatures verified:
- `bpy.ops.uv.average_islands_scale(scale_uv=False, shear=False)` — normalizes per-island texel density
- `bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, rotate_method='ANY', scale=True, merge_overlap=False, margin_method='SCALED', margin=0.001, pin=False, pin_method='LOCKED', shape_method='CONCAVE')` — packs UV islands into square
- NEW: `bpy.ops.uv.arrange_islands(initial_position='BOUNDING_BOX', axis='Y', align='MIN', order='LARGE_TO_SMALL', margin=0.05)` — pre-pack layout ordering
- Both require Edit mode + `bpy.ops.uv.select_all(action='SELECT')` first
- **Critical caveat**: `average_islands_scale()` normalizes per-island average texel density but CANNOT fix within-island distortion (folding). On QR meshes with fragmented sub-islands, arms/legs fragments remain geometrically folded even after normalization. `pack_islands(scale=True)` partially undoes `average_islands_scale` — use `scale=False` if strict texel density matters (but layout won't fill UV square).

**⚠️ RizomUV 2025.0 CLI runs but ZomUnfold does PROJECTION (2026-07-22, FINAL)**: RizomUV's `/cfi` LUA scripting runs in `--background` mode from install dir, but `ZomUnfold` does orthogonal projection not LSCM/ARAP. **VERDICT: NOT viable for production UV.** See `references/rizomuv-cli-lua-failure.md` for full API details and `templates/rizomuv-border-unfold.lua` for the (non-working) script.

**Pipeline A (SharpEdges 1° with NormalizeUVW — VERIFIED 2026-07-22, PROJECTION NOT UNFOLD)**: Blender exports FBX (no seams needed) → RizomUV `ZomLoad({...,XYZ=true},NormalizeUVW=true)→ZomSelect({All=true,ResetBefore=true})→ZomSelect({Auto={SharpEdges={AngleMin=1.0}},PrimType="Edge",WorkingSet="All"})→ZomCut({PrimType="Edge",WorkingSet="Selected"})→ZomUnfold({WorkingSet="All"})→ZomOptimize({Iterations=3})→ZomSave→ZomQuit` → Blender imports FBX → `average_islands_scale()` → `pack_islands()`. Produces 90333 unique UVs, ~1978 islands, but **ZomUnfold does projection not LSCM — 2-3/10 quality**. `NormalizeUVW=true` is REQUIRED — without it, ZomSave outputs only 4 UV coordinates. `ZomUVSet` does NOT exist at runtime. `ZomCut` WorkingSet must be `"Selected"` not `"All"`. `Auto.Skeleton=true` alone does NOT work on QR meshes — must use `Auto.SharpEdges.AngleMin=1.0` instead. `ZomPack` can hang on 90K+ faces — skip and pack in Blender. See `references/rizomuv-cli-lua-failure.md` for full API details.

**Pipeline B (Manual seams + Unfold)**: Blender marks 5 anatomical seams → exports FBX → RizomUV `ZomLoad→ZomUnfold→ZomOptimize→ZomSave→ZomQuit` (~30s) → Blender imports FBX → `average_islands_scale()` → `pack_islands()`. **NOTE**: ZomUnfold does projection not LSCM in headless mode — 2-3/10 quality. Use ZEN UV or Blender built-in instead.

**Key API facts**: `ZomCutAuto` does NOT exist. The auto-seam API is `ZomSelect({Auto={Skeleton=true, Cut=true, Unfold=true, Flatten=true, Pack=true}})`. `ZomPack` can be slow on 90K+ faces — if it hangs, skip it and pack in Blender instead. `ZomQuit()` is required to exit headless mode. See `templates/rizomuv-auto.lua` for the AutoSkeleton script and `references/rizomuv-cli-lua-failure.md` for full API details. (neck/waist/ankle) — NEVER USE on dense QR meshes (confirmed 2026-07-20)**: A "ring at Z=0.83H" with ANY tolerance catches every edge crossing that height — thousands of edges on a 90K-face mesh — and collapses each face into a separate island (95% black bake). **Always use X-band (vertical lines) for seams, never Z-band (horizontal rings).** Only back-center (X=mid, Y>0) + leg-inner (X=mid±1.5%W) cuts are safe. Arm-inner cuts (Y<0, X>15%W) catch too many edges (4596 → 2301 islands) — avoid them too.

**⚠️ RizomUV headless pipeline NOT VIABLE (2026-07-22, FINAL)**: RizomUV 2025.0 CLI `/cfi` LUA scripting runs without crash, but `ZomUnfold` does orthogonal projection not LSCM/ARAP in headless mode. All approaches (Border+Cut+IslandGroups, SharpEdges, Auto.Skeleton, NormalizeUVW) produce 2-4.5/10 quality. An earlier "7.0/10" was a false positive from a UV import bug. **Use Blender ZEN UV (8.25/10) or ANGLE_BASED+average (8.5/10) instead.** See `references/rizomuv-cli-lua-failure.md` for full API details.

**⚠️ QR+UV joint workflow — Material ID guided retopology (2026-07-27, NEW)**: Instead of QR then manual UV, use Material ID regions to auto-generate UV seams after QR. Steps: (1) Pre-QR: mark Material IDs on high-poly via curvature/position rules; (2) QR with `use_materials=True` — edge flow follows material boundaries; (3) Post-QR: material boundary edges → auto-mark_seam → Angle Based Unwrap → average_islands_scale. This produces ~200-500 seams (vs 6501 manual) and ~50-100 islands (vs 1145), with seams at natural clothing boundaries. See `blender-digital-human-pipeline/references/qr-material-id-uv-joint-workflow.md` for the full workflow.

**⚠️ Blender 5.1 OBJ import/export is under `bpy.ops.wm`, NOT `bpy.ops.import_scene` (2026-07-29)**: Blender 5.1 moved OBJ I/O to `bpy.ops.wm.obj_import()` and `bpy.ops.wm.obj_export()`. The old `bpy.ops.import_scene.obj()` does NOT exist. Only `import_scene.fbx` and `import_scene.gltf` remain under `import_scene`. **Before claiming a Blender operator "does not exist", check ALL possible locations**: `dir(bpy.ops.import_scene)`, `dir(bpy.ops.wm)`, `dir(bpy.ops.object)`. A previous session incorrectly concluded "Blender 5.1 removed OBJ import" — it was just moved. User corrected this directly: "blender5.1有obj导入 你做的时候都好好检查好了".

**⚠️ User style correction (2026-07-29)**: When documenting results, do NOT present numeric metrics as "success" when visual quality is poor. User explicitly corrected: "怎么总是给人感觉这个方案跑通了一样" — numeric 0.402mm/96.2% does NOT mean the result is usable. Always state both numeric metrics AND visual quality assessment (e.g., "数值达标但视觉质量差，不可用").

**⚠️ Sculpt mode SMOOTH brush is READ-ONLY in --background (2026-07-29)**: `bpy.context.tool_settings.sculpt.brush` is read-only — cannot assign a Smooth brush programmatically in background mode. `bpy.ops.sculpt.brush_stroke()` is available but the brush type defaults to DRAW. Creating a new brush via `bpy.data.brushes.new('SmoothSculpt', mode='SCULPT')` + setting `brush.sculpt_brush_type = 'SMOOTH'` works, but assigning it to `tool_settings.sculpt.brush` raises `AttributeError: bpy_struct: attribute "brush" from "Sculpt" is read-only`. **Implication**: Cannot programmatically smooth specific mesh regions (e.g., QR overlap areas) via Sculpt mode in background. Use `bpy.ops.mesh.vertices_smooth()` in Edit mode as a fallback — but it applies Laplacian smoothing to ALL selected vertices simultaneously, which cannot separate overlapping layers (shared neighbors move together). Only manual GUI sculpting with a radius-limited brush can separate overlapping geometry layers.

**⚠️ User workflow preference (2026-07-29)**: 分步执行，每步完成后给用户检查。不要一口气跑完整个管线。例如QR完成后先给用户blend文件确认，再继续Smart UV。每次产出结果文件时，提供文件路径给用户。

**⚠️ QR vertex-color density control does NOT work in headless xremesh (2026-07-29)**: Setting `UseVertexColorMap=1` in RetopoSettings.txt has no effect — QR produces identical face count (86,417) with or without vertex colors. The high-poly mesh had no vertex colors (verified: `len(mesh.vertex_colors) == 0`), and even after creating a vertex color layer with red (4x density) on head/hand regions, the xremesh engine did not read it from the FBX. **Do not attempt vertex-color-guided density control via the headless xremesh pipeline.**

**⚠️ QR post-subdivision is meaningless (2026-07-29, user correction)**: User explicitly rejected "QR + local subdivision" approach: "QR的模型已经没多少细节了，你迭代100次细分他不也是没细节？" — Subdivision on QR output is interpolation, not detail reconstruction. The detail is already lost during QR. To get more head/hand detail, increase QR target count or use a different retopology tool BEFORE the detail is lost.

**⚠️ pymeshlab Instant Meshes results (2026-07-29)**: `meshing_isotropic_explicit_remeshing(targetlen=PercentageValue(0.2), featuredeg=45, adaptive=True)` on 193万面 Tripo → 180K faces → `meshing_decimation_quadric_edge_collapse(targetfacenum=125000)` → 125K faces. Overlap reduced to 1/1000 BUT: 0% quad (all triangles), 68 non-manifold edges, hand detail lost (0.6% vs QR's 9.0%). `meshing_tri_to_quad_by_smart_triangle_pairing()` fails on this mesh. `meshing_tri_to_quad_by_4_8_subdivision()` works but explodes face count (125K→450K). `ml.PercentageValue()` is the correct class name (NOT `ml.Percentage()`). FBX save via `ms.save_current_mesh()` does NOT write FBX reliably — use OBJ format instead.

**⚠️ RizomUV edge ID mismatch — FBX reorders edges (2026-07-22)**: When Blender marks anatomical seams (6355 edges) and exports FBX, the edge indices in the FBX do NOT match Blender's internal edge indices. RizomUV's `ZomSelect({IDs={...}, List=true})` uses RizomUV's internal edge numbering, which is reordered during FBX import. Result: `ZomCut` cuts the wrong edges or no edges, producing flat-plane projection (4 unique UVs). **No workaround found** — FBX format does not preserve edge ordering. OBJ has the same problem. The only way to specify seams in RizomUV is through its own auto-seam algorithms (Auto.Skeleton, Auto.SharpEdges), which all fail on QR meshes.

**⚠️ RizomUV NormalizeUVW=true is MANDATORY (2026-07-22)**: `ZomLoad({File={..., XYZ=true}, NormalizeUVW=true})` resets UVs to a flat projection before any processing. WITHOUT `NormalizeUVW=true`, ZomLoad preserves the existing UV (from FBX), and subsequent ZomUnfold operates on the old UV layout — producing only 4 unique UV coordinates (unchanged default UV). WITH `NormalizeUVW=true`, RizomUV creates 90333 unique UVs. This was the root cause of all "UV only has 4 coordinates" failures in earlier RizomUV attempts.

**⚠️ RizomUV all auto-seam methods FAIL on QR meshes (2026-07-22, final verdict)**: Three auto-seam approaches were tested on 90K-face QR output:
1. `Auto.Skeleton=true` — finds no skeleton (uniform normals, no branching detected) → 4 UVs
2. `Auto.SharpEdges.AngleMin=1.0` (1°) — cuts at every edge with any normal difference → 1978 islands but 2-3/10 quality (severe stretching on head/arms/legs)
3. Manual seam edge IDs from Blender — edge indices don't match after FBX reimport → 4 UVs

**⚠️ RizomUV `ZomSelect({Border=true})` + ZomIslandGroups + ZomUnfold — DOES PROJECTION NOT LSCM (2026-07-22, FINAL VERDICT)**: The `Border=true` parameter in `ZomSelect` correctly selects UV island border edges, and `ZomIslandGroups({Mode="CreateFromCuts"})` correctly rebuilds island segmentation. However, `ZomUnfold` in `/cfi` + `/nu` + `/nle` headless mode **always does orthogonal projection, not LSCM/ARAP unfolding** — regardless of IslandGroups, NormalizeUVW, Border+Cut, or Iterations. An earlier session reported "7.0/10 → 8.0/10" — this was a **FALSE POSITIVE** caused by a silent UV import bug (import script selected wrong mesh, so Blender's old projection UVs were saved instead of RizomUV's output). User screenshots confirmed circular/projection UVs. Final confirmed score: **4.5/10** with visible circular projection artifacts. **RizomUV headless is NOT viable for production UV unfolding.**

**Complete RizomUV headless LUA script (NOT RECOMMENDED — produces projection, not real unfold)**:
```lua
ZomLoad({File={Path="in.fbx", ImportGroups=true, XYZUVW=true, UVWProps=true}})
ZomSet({Path="Prefs.FileSuffix", Value=""})
ZomSelect({PrimType="Edge", Border=true, ResetBefore=true})
ZomCut({PrimType="Edge", WorkingSet="Selected"})
ZomIslandGroups({Mode="CreateFromCuts"})  -- rebuilds islands but ZomUnfold STILL projects
ZomUnfold({PrimType="Polygon", WorkingSet="All"})  -- PROJECTION not LSCM in headless mode
ZomOptimize({Iterations=20})
ZomSave({File={Path="out.fbx"}})
ZomQuit()
```
Run from RizomUV install dir: `cd "D:\Program Files\Rizom Lab\RizomUV 2025.0" && rizomuv.exe /cfi script.lua /nu /nle`

**Blender side**: Mark 5 anatomical seams → `bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)` (seam→UV border) → export FBX → (RizomUV) → import FBX → `average_islands_scale()` → save.

**Why this DOES NOT work**: ZomUnfold in headless `/cfi` mode defaults to orthogonal projection. Adding `ZomIslandGroups({Mode="CreateFromCuts"})` correctly rebuilds island segmentation, but ZomUnfold STILL projects. The GUI Unfold (triggered by keyboard 'U') does real LSCM/ARAP — the LUA API behaves differently. An earlier session's 7.0/10 vision score was a false positive from a UV import bug. User-confirmed 4.5/10 with circular projection. **Use Blender ZEN UV (8.25/10) or ANGLE_BASED+average (8.5/10) instead.**

**⚠️ Vision score false positives from UV import bugs (2026-07-22, CRITICAL LESSON)**: An AI vision model rated a checkerboard render 7.0/10 when the actual UV was orthogonal projection (should be 2/10). The cause: a silent import bug where the UV copy script selected the wrong mesh object, so the rendered model still had Blender's old projection UVs (not RizomUV's output). The vision model saw "uniform checkerboard" because `average_islands_scale` had been applied to the OLD projection UVs — making projection look deceptively good. **Lesson**: always verify UV is NOT projection by checking a known vertex coordinate (head-top V should NOT equal Z/height) BEFORE trusting a vision score. A vision score on projection+average can look 7/10 when the real quality is 2/10. The user caught this by opening the file in Blender GUI and seeing circular UVs.

**⚠️ RizomUV ZomSelect WorkingSet enum values (2026-07-22)**: The `WorkingSet` parameter in ZomSelect/ZomCut/ZomUnfold/ZomPack accepts ONLY these values: `"Visible"`, `"Selected"`, `"Flat"`, `"NotFlat"`. Combinations like `"Visible&Selected&Flat"` are allowed. There is **NO `"All"` value** and **NO `"UVBorders"` value**. Using `"All"` silently fails (no selection made). The correct way to select all is `ZomSelect({All=true, ...})` — the `All` parameter is a boolean, NOT a WorkingSet string value.

**⚠️ RizomUV "UV boundary as seam" approach — WORKS with Border=true + IslandGroups (2026-07-22, FINAL)**: An external advisor suggested: Blender marks seams → unwrap (seam becomes UV boundary) → export FBX (UVs preserved) → RizomUV selects UV borders → Cut → Unfold. This approach **WORKS** when using `ZomSelect({PrimType="Edge", Border=true})` (NOT a `UVBorders` WorkingSet value — `Border` is a boolean parameter on ZomSelect). The earlier failure was because we looked for `WorkingSet="UVBorders"` which doesn't exist; the correct API is the `Border=true` boolean. See the **Complete working RizomUV pipeline** below for the full verified script.

**⚠️ RizomUV UnfoldIte parameter (2026-07-22)**: `U3dSet({Path="Prefs.UnfoldIte", Value=N})` controls unfold iterations. Tested N=0,1,5 — no visible difference on QR meshes. The Unfold algorithm's quality is bounded by seam placement, not iteration count. Increasing to 50-100 (as suggested by external advisor) would likely not help because the fundamental problem is missing cuts, not insufficient relaxation.

**⚠️ Comprehensive UV research report written (2026-07-22)**: A full report documenting all tested UV approaches, root cause analysis, and recommendations was written to `E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\方案md记录\v3_QuadRemesher\UV展开问题调研报告.md`. Covers: Blender built-in (7 methods), ZEN UV (9 configurations), xatlas, pymeshlab, RizomUV (8 LUA scripts), B2RUVL, and recommendations from external advisors. The report identifies the root cause as QR uniform quad topology defeating all normal-based seam detection algorithms.

**⚠️ External UV tools research — comprehensive test (2026-07-21)**: All tested external tools fail or underperform on QR meshes:
1. Clear all seams
2. Mark ONLY back-center + L/R-leg-inner seams (455 edges, tight tolerance ±0.15%W)
3. `bpy.ops.uv.unwrap(method='CONFORMAL', ...)` (3s, fastest)
4. `bpy.ops.uv.average_islands_scale()` (texel density)
5. `bpy.ops.uv.pack_islands(rotate=True, scale=True, margin=0.003)`
Result: **84 islands, 3s, 2/10 checkerboard quality** — meets island-count goal (close to 50) but NOT quality goal (2/10 vs needed 7+/10). Usable for BAKING only (14.7% black pixels acceptable). For production-quality UVs on QR output, use RizomUV (paid) or avoid QR entirely (use template-wrap retopology instead). See `references/qr-mesh-uv-failure-analysis.md` and `UV_BACKGROUND_RESEARCH_REPORT.md` for full test matrix.

| Method | Seams | Islands~ | Vision Score | Failure Mode |
|--------|-------|----------|:------------:|--------------|
| Smart UV 66° (default) | 760 | 914 | 2/10 | Body stretched, arms/legs invisible |
| Smart UV 89° (high angle) | 0 | 1983 | 2/10 | Even MORE islands — counterintuitive |
| ANGLE_BASED unwrap + 5 seams | 2808 | 1125 | 2/10 | Body huge patches, arms near-zero UV |
| CONFORMAL (LSCM) unwrap + 5 seams | 6501 | 1196 | 2/10 | Same fragmentation as ANGLE_BASED |
| Cylinder projection (body+arms) | 0 | 4 | TERRIBLE | 4 islands but body=vertical stripes, arms=horizontal stripes |
| Manual projection | 0 | 1968 | 2/10 | Body sides stretched, arms blurred |
| ANGLE_BASED + manual UV stitch/merge | 3612 | 1157 | 2/10 | Merge collapsed distinct islands to points |

**Root cause**: QuadRemesher creates a uniform quad grid where neighboring faces have slightly different normals (not perfectly coplanar). ANY normal-based unwrap algorithm (Smart UV, ANGLE_BASED, CONFORMAL) splits at these non-coplanar edges, creating thousands of micro-islands. The fragmentation is TOPOLOGY-DRIVEN, not parameter-driven — no amount of seam tuning or angle threshold adjustment can fix it. Smart UV with HIGHER angle (89°) creates MORE islands because it tries to respect every face's orientation. See `references/qr-mesh-uv-failure-analysis.md` for full test matrix and render comparisons. See `references/b2ruvl-rizomuv-background-check.md` for B2RUVL/RizomUV plugin status and alternative architecture (skip QR, preserve UV via Decimate).

**xatlas external unwrapper — tested but also insufficient (2026-07-20)**: xatlas (pip install xatlas) was tested as an alternative. It runs in system Python (NOT Blender's bundled Python — pip install fails inside Blender's `--background` mode). Two-step workflow: export mesh as OBJ from Blender → run xatlas in system Python → import UVs back via `.npz` file. xatlas API returns a 3-tuple `(vertex_map, face_map, uvs)`, NOT the documented `vertex_array`/`uv_array` attributes. Result: ~2000 islands, vision score 3/10 — slightly better than Blender methods but arms/legs still near-zero UV area. The `texels_per_unit` PackOption didn't take effect in the Python binding (v0.0.11). See `references/xatlas-two-step-uv.md` for the complete workflow and API quirks.

**✅ BREAKTHROUGH: `average_islands_scale()` solves texel density (2026-07-20)**: After testing ALL methods above (all scored 2-3/10), the solution was found: call `bpy.ops.uv.average_islands_scale()` AFTER unwrap. This single API call equalizes all UV islands to the same texel density based on their 3D surface area. Vision score jumped from 2/10 to **8.5/10** — checkerboard squares became uniform across body, arms, and legs.

**Critical API detail — `use_uv_select_sync=True` enables UV ops in background mode**: `bpy.ops.uv.average_islands_scale()` and `bpy.ops.uv.pack_islands()` fail with "context is incorrect" in `--background` mode even with `temp_override(area=IMAGE_EDITOR)`. The fix: set `bpy.context.scene.tool_settings.use_uv_select_sync = True` BEFORE calling UV operators. With sync enabled, UV operators work directly from EDIT mode without needing an IMAGE_EDITOR area. Full working sequence:

```python
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, correct_aspect=True, margin=0.005)
bpy.context.scene.tool_settings.use_uv_select_sync = True
bpy.ops.uv.average_islands_scale()  # ← THE KEY: equalizes texel density
bpy.ops.uv.pack_islands(rotate=True, margin=0.005)
```

**Why this works**: Without `average_islands_scale()`, ANGLE_BASED/CONFORMAL unwrap assigns UV area proportional to face count, not 3D surface area. On QR meshes where the body has more faces than arms/legs, the body gets huge UV space while arms/legs get near-zero — producing the "arms invisible" artifact. `average_islands_scale()` recalculates each island's 3D area and rescales its UV area to match, achieving uniform texel density across the entire model. The 1145 islands remain (fragmentation is topology-driven), but each island now has correct proportional UV area. For BAKING purposes, this is sufficient — the bake correctly samples the high-poly at every island.

**Revised practical recommendation for QR meshes (2026-07-20, ZEN UV is best)**: Two viable approaches, in priority order:

1. **ZEN UV (BEST, 8.25/10)**: 5 manual seams → `zenuv_auto_uv_unwrap(hard_edges=False, stretch=True, texel_density=True, packing=True)` → normalize. Produces uniform texel density, minimal stretch, arms/legs fully visible. Requires ZEN UV plugin installed.

2. **Blender built-in (8.5/10 quality but more fragments)**: 5 manual seams → ANGLE_BASED unwrap → `average_islands_scale()` → `pack_islands()`. Achieves higher uniformity score but ~1145 islands vs ZEN UV's fewer meaningful fragments. Requires `use_uv_select_sync=True` for background mode.

3. **QR+UV joint workflow — Material ID guided (2026-07-27, NEW)**: Pre-QR Material ID marking → QR with `use_materials=True` → material boundary auto-seam → unwrap. Produces ~200-500 seams, ~50-100 islands, seams at natural clothing boundaries. See `blender-digital-human-pipeline/references/qr-material-id-uv-joint-workflow.md`.

Both approaches use the same 5 anatomical seams: back center (X=mid, Y>0), left arm inner (X<0, Z≈0.68-0.84H), right arm inner (X>0, Z≈0.68-0.84H), left leg inner (X=mid-1.5%W), right leg inner (X=mid+1.5%W). Tolerance: ±0.4%W for X. **Arm inner seams are MANDATORY** — omitting them produces 3.5/10 with severe arm stretching. **Never use Z-band ring cuts** (neck/waist/ankle) — they mark 128K+ edges and collapse every face into a separate island.

**⚠️ ZEN UV `zenuv_unwrap_inplace` (LSCM/CONFORMAL) — works in background (2026-07-21)**: The `zenuv_unwrap_inplace()` operator successfully applies LSCM (CONFORMAL) unwrap to existing UVs in `--background` mode. This is the ONLY way to get LSCM unwrap quality in background — Blender's built-in `bpy.ops.uv.unwrap()` with CONFORMAL produces the same fragmentation as ANGLE_BASED. The full ZEN UV pipeline: `zenuv_auto_uv_unwrap(texel_density=True, packing=True)` → `zenuv_unwrap_inplace(urp_method='CONFORMAL', fill_holes=True, correct_aspect=True, restore_location=True, restore_size=True)` → `average_islands_scale()` → normalize with margin. `zenuv_relax()` crashes on zero-length vectors (mesh may have degenerate edges).

**⚠️ Single-face island merging — CRITICAL RULE (2026-07-21)**: After ZEN UV `auto_uv_unwrap`, there are ~2890 single-face islands. To merge them: `seams_from_islands()` → bmesh flood-fill → clear seam edges ONLY on exactly 1-face islands → re-unwrap. **ONLY merge 1-face islands.** Merging ≤3-face islands clears 6347 edges and collapses the entire mesh to 1 island (loses all UV quality). Merging all tiny islands then re-unwrapping with ANGLE_BASED loses ZEN UV's LSCM quality — severe stretching on head/arms/legs. **Recommendation**: keep the tiny islands (3.2% of faces) unless they cause bake artifacts. The 2890 fragments are harmless for baking.

**⚠️ Neck ring seam for head separation (2026-07-21)**: On QR meshes, the head often gets excessive UV area (large checkerboard squares) while the body gets compressed (small squares). Add a neck ring seam (Z=80%-86%H, X≈mid_x, tolerance ±2×xt) to separate the head from body before unwrap. This allows `average_islands_scale()` to properly equalize head vs body texel density. Without this seam, the head and body are one island and cannot be independently scaled.

**⚠️ UV margin normalization after ZEN UV packing (2026-07-21)**: ZEN UV's `packing=True` produces UV islands that touch the [0,1] boundaries (0% margin). This causes texture bleeding. Fix: after unwrap, normalize UVs to [margin, 1-margin] with scale factor. Formula: `normalized = margin + (original - min) / (max - min) * (1 - 2*margin)`. For 5% margin: `margin=0.05, scale=0.90` → utilization ~62%. For 2% margin: `margin=0.02, scale=0.96` → utilization ~79%.

**⚠️ GLB triangulates quads — export OBJ for quad mesh (2026-07-21)**: `bpy.ops.export_scene.gltf()` always triangulates the mesh during export. To preserve quad faces, also export OBJ: `bpy.ops.wm.obj_export(filepath=out, export_selected_objects=True, export_materials=True, export_normals=False, export_uv=True)`. This produces `.obj` + `.mtl` (material file). The `.mtl` includes material properties but NOT a `map_Kd` reference — diffuse textures must be exported separately as PNG alongside the OBJ. The user prefers receiving BOTH GLB and OBJ.

**⚠️ Tiny island merger (2892 → 6) loses ZEN UV quality (2026-07-21)**: After `seams_from_islands()`, clearing seam edges on tiny (≤3 face) islands then re-unwrapping with ANGLE_BASED successfully merges them into large islands (2902 → 6). HOWEVER, the re-unwrap loses ZEN UV's original LSCM quality — ANGLE_BASED produces severe stretching on head, arms, and legs. **Recommendation**: keep ZEN UV's tiny islands (3.2% of faces) unless they cause bake artifacts. If merging is required, re-mark ALL anatomical seams before re-unwrap. See `references/zen-uv-final-pipeline.md` for full details.: When baking textures in one stage, then rigging in a subsequent stage, the material node tree can end up with DUPLICATE or BROKEN node chains. Symptoms: GLB imports as a plain white model (no textures visible), or renders show noise/garbage. Root causes found:
1. **Duplicate Principled BSDF + Output nodes**: After rig stage re-imports the mesh, the material accumulates two `ShaderNodeBsdfPrincipled` and two `ShaderNodeOutputMaterial` nodes. The baked Diffuse texture connects to `BSDF.001` → `Output.001`, but the GLB exporter reads `Output` (the empty one). **Fix**: `nodes.clear()` the material and rebuild a single clean chain: `TexImage(Diffuse) → BSDF(Base Color) → Output(Surface)`.
2. **Bake_Diffuse image deleted during rig stage**: The rig script's orphan purge or object cleanup can delete `bpy.data.images['Bake_Diffuse']`. After rigging, verify the image still exists and is packed.
3. **Normal map colorspace wrong**: `Bake_Normal` defaults to `sRGB` — must be `Non-Color`. Setting it AFTER baking destroys pixel data (see earlier pitfall). Set `image.colorspace_settings.name = 'Non-Color'` before `bpy.ops.object.bake(type='NORMAL')`.
4. **Old material slots from high-poly**: The retopo mesh inherits material slots from the original GLB import (8K basecolor textures, multiple shader nodes). Clear with `mesh.data.materials.clear()` before creating the fresh bake material.

**Production-safe bake→rig→export sequence** (verified 2026-07-21):
```python
# After baking, BEFORE saving 05_bake.blend:
mat = bpy.data.materials.new('Char'); mat.use_nodes = True
retopo.data.materials.clear(); retopo.data.materials.append(mat)
nodes = mat.node_tree.nodes; links = mat.node_tree.links; nodes.clear()
bsdf = nodes.new('ShaderNodeBsdfPrincipled')
out = nodes.new('ShaderNodeOutputMaterial')
tex_diff = nodes.new('ShaderNodeTexImage'); tex_diff.image = bpy.data.images['Bake_Diffuse']
tex_norm = nodes.new('ShaderNodeTexImage'); tex_norm.image = bpy.data.images['Bake_Normal']
bpy.data.images['Bake_Normal'].colorspace_settings.name = 'Non-Color'  # BEFORE bake, not after
normal_map = nodes.new('ShaderNodeNormalMap')
links.new(tex_diff.outputs['Color'], bsdf.inputs['Base Color'])
links.new(tex_norm.outputs['Color'], normal_map.inputs['Color'])
links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
for img in [bpy.data.images['Bake_Diffuse'], bpy.data.images['Bake_Normal']]: img.pack()
bpy.data.objects.remove(high, do_unlink=True)  # Delete high-poly BEFORE save
```
Then after rig stage, BEFORE export: verify material has exactly 1 BSDF + 1 Output + 1 Diffuse TexImage + 1 Normal TexImage, with links intact. If broken, rebuild from scratch with `nodes.clear()`.

**⚠️ MVP brute-force UV+bake for QR meshes (2026-07-29, VERIFIED WORKING)**: When the goal is a fast end-to-end demo (not production UV), accept Smart UV fragmentation and rely on bake margin to hide seams. Verified pipeline on 86K-face QR output: (1) `bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.03, area_weight=0.0, correct_aspect=True)` — produces ~2000 islands but UV range cleanly inside [0.014, 0.986] with zero out-of-bounds points; (2) bake with `use_selected_to_active=True, cage_extrusion=0.05, max_ray_distance=0.1, margin=16, samples=16` on CPU → mean pixel 0.337, no black regions. This is the Stage-1 MVP of the v4 three-stage route (see `blender-body-wrap/references/v4-three-stage-roadmap.md`). **First attempt produced a 100% BLACK bake** because: fresh `bpy.data.images.new()` target + `save_mode='EXTERNAL'` + missing explicit `use_selected_to_active=True` + GPU device. Fix: always set `use_selected_to_active=True` explicitly, fall back to `cycles.device='CPU'` on failure, and verify with a pixel-stat check (`np.array(img.pixels[:]).max() < 0.01` → warn) before declaring success. A `Circular dependency` info message during bake (high-poly material references the same image name) is harmless. Working scripts: `test02/mvp_pipeline/scripts/03_smart_uv.py` and `04_bake.py`.

**⚠️ xremesh license问题导致QR无法复现 (2026-07-29)**: 在当前会话环境中，xremesh.exe启动后卡在~22%进度不再前进，progress.txt停滞。杀掉重启后同样卡住。根因可能是license验证失败或运行时环境问题。之前在同一会话中成功运行过（86K面结果），但后续无法复现。**Workaround**: 复用已有的QR结果（test02/mvp_pipeline/output/02_qr_125k_final.blend），或尝试在GUI模式下运行QR插件。

**⚠️ ZED相机进程阻止xremesh启动 (2026-07-30)**: ZED相机（Zed.exe）占用GUI资源，导致xremesh.exe启动后立即退出（无输出、无错误）。杀掉ZED进程后xremesh能正常启动。但ZED会**自动重启**，需反复杀掉。xremesh运行期间ZED再次启动会导致xremesh卡住（progress停在~22%）。**Workaround**: 运行QR前检查并杀掉ZED（`taskkill /F /T /IM Zed.exe`），运行期间定期监控ZED是否复活。注意：xremesh直接调用（非Blender operator）生成的结果可能异常（104万面而非目标12.5万），说明`TargetQuadCount`参数未被正确读取——需用Blender插件operator方式调用才能正确减面。

**⚠️ Blender 5.1 OBJ导入位置变更 (2026-07-29)**: `bpy.ops.import_scene.obj` 不存在于Blender 5.1。正确位置是 `bpy.ops.wm.obj_import()` 和 `bpy.ops.wm.obj_export()`。`import_scene`下只有`fbx`和`gltf`。**教训**：不要假设operator位置，先检查`dir(bpy.ops.import_scene)`和`dir(bpy.ops.wm)`。用户直接纠正：\"blender5.1有obj导入 你做的时候都好好检查好了\"。

**⚠️ QR plugin in `--background` mode — initialization and execution (2026-07-29)**: The Quad Remesher Bridge addon (v1.3.2, `bl_ext.user_default.quadremesher`) has TWO separate issues in background mode:

1. **Initialization**: `addon_utils.enable('bl_ext.user_default.quadremesher')` raises `KeyError: 'bpy_prop_collection[key]: key "bl_ext.user_default.quadremesher" not found'` — **BUT the operator and `scene.qremesher` PropertyGroup are still registered successfully**. The KeyError is from the addon's UI panel registration (UPP function), which fails in background mode. Catch and ignore it. Using `addon_utils.enable('quadremesher')` (without the `bl_ext.user_default.` prefix) fails with `No module named 'quadremesher'` — always use the full extension ID.

2. **Execution**: `bpy.ops.qremesher.remesh()` uses `RUNNING_MODAL` + `window_manager.event_timer_add` + `modal_handler_add`, which requires a window. In `--background` mode, the operator's `cancel()` is called immediately — it exports FBX to temp dir but never runs the external engine. **Workaround**: call the external engine directly via `subprocess.Popen([xremesh_path, "-s", settings_file])`. Write a `RetopoSettings.txt` with `HostApp=Blender`, `FileIn`, `FileOut`, `ProgressFile`, `TargetQuadCount=90000`, `CurvatureAdaptivness=50`. Monitor progress via the progress file. Engine path: `<addon_dir>/EngineWin/xremesh.exe`. See `test02/mvp_pipeline/scripts/02_qr_remesh.py` for the complete working script.

**⚠️ Deleting objects while iterating crashes (StructRNA removed)**: `for o in objects: bpy.data.objects.remove(o, do_unlink=True); print(o.name)` raises `ReferenceError: StructRNA of type Object has been removed` — the loop variable holds a dead reference after removal. Collect names first, then delete by name lookup: `names = [o.name for o in objects]; for n in names: obj = bpy.data.objects.get(n); if obj: bpy.data.objects.remove(obj, do_unlink=True)`.

**⚠️ Bake produces 100% BLACK on first attempt (2026-07-29)**: Common causes and fixes for all-black bake output: (1) **Missing explicit `use_selected_to_active=True`** — without it, Cycles bakes from the active object to itself (no high-poly target), producing black. (2) **GPU device failure** — `cycles.device='GPU'` may fail silently on some systems; fall back to `cycles.device='CPU'`. (3) **Missing pixel-stat verification** — always check `np.array(img.pixels[:]).max() < 0.01` after bake; if true, the bake failed. (4) **Circular dependency info message** — harmless, caused by high-poly material referencing the same image name as the new bake target; can be ignored. Working fix: explicitly set `use_selected_to_active=True`, use CPU, and verify with pixel stats before declaring success.

**⚠️ Clothing penetration during bake — use tiny cage + ray distance (2026-07-29, VERIFIED)**: When baking high-poly with clothing (e.g., Tripo AI mesh with shirt+pants) onto a low-poly that has both body and clothing as a single surface, bake rays can pass THROUGH the clothing layer and hit the skin underneath, producing skin-colored texels in clothing areas (especially at collar, cuffs, and inner thighs). **Fix**: set `cage_extrusion=0.003` (3mm) and `max_ray_distance=0.005` (5mm) — the tiny distance ensures rays only hit the NEAREST surface (clothing), not the skin underneath. Previous values `cage_extrusion=0.05` (50mm) and `max_ray_distance=0.1` (100mm) were too large and caused penetration. User confirmed the fix resolved skin showing through at collar and inner thighs. Note: this trades coverage for correctness — some areas with >5mm gap between clothing layers may get black pixels, but this is preferable to wrong-colored texels.

**⚠️ Black patches on belly — increase cage + ray distance (2026-07-31, VERIFIED)**: User reported black patches on model's belly ("肚皮上还是有黑色的斑块"). Original params `cage_extrusion=0.005, max_ray_distance=0.01` were too small — rays couldn't reach the high-poly surface in areas with slight mesh offset. **Fix**: `cage_extrusion=0.01, max_ray_distance=0.05` (5x ray distance increase). **Balancing act**: too small = black patches from missed rays; too large = skin showing through clothing (see previous pitfall). For models with clothing, start at `cage_extrusion=0.01, max_ray_distance=0.05` and tune. User also confirmed the AI high-poly texture itself was NOT defective ("高模衣服纹理没任何问题") — the black patches were purely a bake parameter issue.\n\n**⚠️ Bake parameter progression for AI high-poly (2026-07-31, consolidated)**: The full tuning history across sessions for Tripo AI high-poly on QR low-poly:\n\n| Config | Black% | Use Case |\n|--------|:------:|---------|\n| cage=0.005, ray=0.01 | ~15-20% | Too small — belly black patches |\n| cage=0.01, ray=0.05 | ~5-10% | **Recommended starting point** for clothed models |\n| cage=0.05, ray=0.1 | ~15% | Too large — skin shows through clothing |\n| cage=0.3, ray=0.0 | 14.7% | AI meshes with 43% flipped normals + internal surfaces |\n\n**Decision tree**: If black patches appear → increase ray distance first (0.01→0.05). If skin shows through clothing → decrease ray distance. If both problems → use cage mode with `max_ray_distance=0` and tune `cage_extrusion` only.

**⚠️ AI high-poly texture has INHERENT skin/clothing color bleed (2026-07-29, CRITICAL)**: Tripo AI high-poly textures (8K basecolor) often have skin-colored pixels bleeding into clothing regions — especially at collar, inner thighs, and cuffs. This is NOT a bake ray-penetration issue; the high-poly texture itself is defective. **Detection**: sample UV-mapped pixels at collar (Z=0.72-0.82, |X|<0.1) and groin (Z=0.3-0.45, |X|<0.08) regions — if >50% of sampled pixels are skin-colored in areas that should be clothing, the texture is defective. **Fix (verified working)**: (1) Load texture as numpy array via PIL; (2) Identify clothing mask: `(R<0.15*255) & (G<0.15*255) & (B<0.15*255)`; (3) Dilate mask by 10 iterations (`scipy.ndimage.binary_dilation`); (4) Find skin pixels within dilated clothing zone: `(R>0.4*255) & (G>0.25*255) & (R>G)`; (5) Replace all bleed pixels with clothing mean color (e.g., RGB(30,30,29)); (6) Gaussian blur transition edges (sigma=1). Result: 229,644 bleed pixels → 2,674 (98.8% reduction). Save fixed texture as PNG, load into Blender high-poly material before baking. See `references/ai-texture-color-bleed-fix.md` for the complete script.

**⚠️ QR dual-layer overlap is UNFIXABLE in --background mode (2026-07-29, FINAL)**: When QR processes AI high-poly with clothing+body as dual-layer geometry, it produces overlapping faces (~29/1000 sampled) at clothing boundaries. Tested fixes that ALL FAILED: (1) Adjusting QR params (adaptive_size 20/30/50/80, hard_edges on/off) — no effect (28-30/1000); (2) Laplacian smoothing (`vertices_smooth`) — layers share neighbors, move together (29→27/1000); (3) Local bmesh Laplacian (only overlap verts) — same issue (29→27/1000); (4) Pushing all overlap verts along normal — creates NEW overlaps at edges (29→33/1000); (5) Pushing only upper-layer (Z>0 normal) verts — still creates edge overlaps (29→35/1000); (6) Deleting overlap faces — destroys topology (0→1148 non-manifold edges); (7) `remove_doubles` — no effect on face-level overlap; (8) Voxel Remesh — no effect (27/1000); (9) Sculpt SMOOTH brush — `tool_settings.sculpt.brush` is READ-ONLY in background, cannot assign brush type. **Root cause**: overlap is two independent surface layers at the same position; any operation that moves both layers together (Laplacian, Voxel) cannot separate them. Only a radius-limited manual brush in GUI can separate them (user confirmed this works manually). **Recommendation**: accept overlap for MVP, or have user manually smooth in GUI.

**⚠️ Smart UV island_margin tuning (2026-07-29, updated 2026-07-31)**: User progression: 0.03 "太保守" → 0.002 → 0.001 "UV缝隙太小了感觉都要连在一起了" → **0.01 (final, user-requested 2026-07-31)**. UV range: 0.001→[0.001,0.999], 0.01→[0.006,0.994]. **Rule**: use 0.01 for production bakes (clear island gaps), 0.002 for MVP (max UV space). User explicitly asked to "把UV岛与岛之间缝隙提升到两倍" then changed to "边距直接改成0.01".

**⚠️ 4K bake vs 2K (2026-07-29)**: User requested 4K (4096×4096) for production quality. `bpy.data.images.new(name, width=4096, height=4096)` works fine. Bake time on CPU (16 samples) is ~2-3 min for 125K-face low-poly + 1.9M-face high-poly. Mean pixel value increased from 0.315 (2K) to 0.414 (4K) due to better UV utilization at higher resolution.

**⚠️ Non-manifold edges in AI high-poly cause persistent black pixels (2026-07-20)**: Tripo AI high-poly (1.93M faces) has 16.4% non-manifold edges (516,960 of 3,153,702). These open boundaries and internal surfaces block bake rays regardless of UV quality, Cage settings, or ray distance. The 42.7% black pixels = ~15% from UV fragmentation + ~27% from high-poly internal geometry. No bake parameter can fix the latter — would require cleaning the high-poly (fill holes, remove internal faces) before baking. **Always check high-poly manifoldness** before baking: `non_manifold = sum(1 for e in bm.edges if not e.is_manifold)`. If >10% non-manifold, expect >30% black pixels and warn the user.

## Mesh Topology Impact on Baking

### Uneven edge density → uneven texture resolution
- Dense mesh areas (face) → small UV islands per face → fewer texels per face → blurry
- Sparse mesh areas (torso) → large UV islands → more texels → sharp
- This is inherent to UV mapping: edge density directly drives UV area allocation

### High-low poly mismatch
- High-poly detail in sparse low-poly regions → detail averaged away
- Low-poly vertex density uneven → normal interpolation direction deviation → "wave" artifacts
- Triangles/poles in low-poly → abnormal normal calculation → black spots/color shifts

**Pitfall**: Always check low-poly edge density uniformity before baking,
especially at high-curvature regions (nose, ears, fingers). Add support loops
where needed. Use Average Island Scale to balance UV island sizes.

## Quick-Reference Parameter Guide

| Scenario | Max Ray Distance | Cage | Margin |
|----------|-----------------|------|--------|
| Tight high-low fit | 5-10mm | No | 16px |
| Large gap between meshes | 20-50mm | Recommended | 16px |
| Clothing/hair interference | 2-5mm | Custom cage | 32px |
| Edge artifacts present | — | Yes (custom) | 32px |

## Verification Checklist

- [ ] High-poly and low-poly spatially coincide (same pose, same symmetry) — THE most common bake failure
- [ ] Flip UV enabled if using Mirror Modifier (check for overlapping UVs)
- [ ] UV test grid shows minimal distortion
- [ ] Seams hidden in non-visible areas
- [ ] Max Ray Distance tested — no black patches, no backside bleed
- [ ] Margin set to 16-32px
- [ ] Normal map space matches Image Texture node setting
- [ ] Low-poly edge density uniform at high-curvature regions
- [ ] **Bake-to-GLB**: Images packed AND connected to Principled BSDF output chain (Diffuse→Base Color, Normal→NormalMap→BSDF Normal). Verify by re-importing GLB and checking Material nodes.

## References

- `references/mirror-symmetry-test-results.md` — Complete 10-approach mirror
  symmetry testing results (128K-vertex model). Includes bmesh vertex-mirror
  verification, BFS topologymatching, curvature+geodesic, Hungarian assignment,
  Laplacian deformation, and the winning upgraded delete-half mirror with
  negative UV restoration technique.
- `references/asymmetric-baking-findings.md` — Research on baking when
  high-poly and low-poly don't spatially coincide (different poses,
  asymmetric vs symmetric). Includes solution comparison table, correct
  workflow order, facial asymmetry guidance, and UV-symmetry vs
  geometry-symmetry decision matrix. Verified against Blender 5.1 docs
  and Blender Artists forum.
- `references/blender-docs-findings.md` — Verified excerpts from Blender 5.1
  official documentation (Mirror Modifier, Render Baking, UV Unwrapping)
- `references/bmesh-geometry-mirror-keep-uv.md` — bmesh API details for
  mirroring vertex coordinates while preserving UV layers; includes working
  script template and plugin recommendations
- `references/zbrush-resymmetry-docs-findings.md` — Verbatim excerpts from
  Maxon ZBrush official documentation (SmartReSym, ReSym, Mirror and Weld,
  Poseable Symmetry) verifying that all symmetry tools operate on vertex
  positions only and do not touch UV data
- `references/zbrushcentral-resymmetry-community-findings.md` — ZBrushCentral
  forum corroboration: practitioner confirmations that Resymmetry doesn't
  handle UV-based textures, the polypaint mirror workaround, the "symmetry
  map" mechanism, and the Discourse JSON API access method
- `scripts/mirror_geometry_keep_uv.py` — Runnable script: mirrors vertex
  positions along an axis while keeping UV/materials untouched. Use with
  `blender --python scripts/mirror_geometry_keep_uv.py -- --object NAME --axis X`
- `scripts/auto_uv_pipeline.py` — Fully automated UV pipeline: dihedral-angle
  seam detection → symmetry-axis seam → Angle-Based Unwrap → pack islands.
  Designed for digital-human batch pipelines (200-250K poly). Use with
  `blender --background model.blend --python auto_uv_pipeline.py`
- `scripts/uv_merge1.py` — ZEN UV auto_uv_unwrap + single-face island merger.
  Eliminates 2892 single-face fragments → 21 clean islands (61.7% utilization).
  Only merges 1-face islands (DO NOT merge 2-3 face — cascades to 1 island).
  Use with `blender --background model.blend --python uv_merge1.py`
- `references/zen-uv-plugin-test.md` — ZEN UV commercial plugin testing on
  QR meshes. Full API discovery (225 operators), parameter quirks
  (`action='DEFAULT'` not `UNWRAP`, `UnwrapMethod='CONFORMAL'` not `LSCM`,
  angle in radians), stretch=True timeout on >50K faces, packing=True
  overlapping tiny islands (42.7% black pixels), and production recommendation
  (stretch=False for large meshes). Test results showing ZEN UV achieves
  8.25/10 with manual seams + hard_edges=False.
- `references/rizomuv-cli-lua-failure.md` — RizomUV 2025.0 CLI `/cfi` LUA
  integration (updated 2026-07-22). **Key findings**: `ZomSelect({Border=true})`
  selects UV borders (works), but `ZomUnfold` does projection not LSCM/ARAP in
  background mode (2-3/10 quality). All auto-seam (Skeleton/SharpEdges) fail
  on QR meshes. `NormalizeUVW=true` mandatory. Edge IDs mismatch after FBX.
  RizomUV headless NOT viable for production UV unfolding. Full research report
  pointer included.
- `references/uv-ecosystem-research.md` — Comprehensive UV ecosystem research
  (2026-07-21): AI 3D companies (TRIPO/Hunyuan3D/Rodin/Meshy/CSM) UV assessment,
  open-source tools (xatlas/thekla_atlas/UVAtlas/libigl/CGAL/minimize_stretch),
  academic methods (OptCuts/BFF/Neural UV), Blender plugins (ZEN UV/UVPackmaster/
  TexTools/Magic UV/RizomUV Bridge), and commercial tools (RizomUV/Wrap4D) with
  headless/CLI feasibility. Priority-ranked recommendations.
- `references/bake-to-glb-material-pitfalls.md` — GLB white-model export
  failure: duplicate material node chains, deleted Bake_Diffuse during orphan
  purge, Normal map sRGB colorspace, old high-poly material slots. Production-safe
  bake→rig→export sequence and verification script.
- `references/rizomuv-cli-lua-failure.md` — RizomUV 2025.0 CLI `/cfi` LUA **SUCCESS** (updated 2026-07-21): Running from install dir fixes ForcePython.usda error. Full verified LUA API: ZomLoad/ZomUnfold/ZomOptimize/ZomSave/ZomQuit all work. ZomCutAuto does NOT exist (no auto-seam in LUA). ZomPack slow on 90K+ faces — pack in Blender instead. See also `templates/rizomuv-unfold.lua` for working script.
- `templates/rizomuv-unfold.lua` — Verified working RizomUV headless LUA script: ZomLoad→ZomUnfold→ZomOptimize→ZomSave→ZomQuit. Replace `<FBX_IN>`/`<FBX_OUT>` with absolute paths. Run from RizomUV install dir.
- `templates/rizomuv-border-unfold.lua` — **BEST** RizomUV headless LUA script (7.0/10): ZomLoad→ZomSelect(Border=true)→ZomCut→ZomIslandGroups(CreateFromCuts)→ZomUnfold→ZomOptimize(20)→ZomSave→ZomQuit. Uses UV border approach to pass Blender seams. See `references/rizomuv-cli-lua-failure.md` for details.
- `references/external-uv-tools-test-results.md` — pymeshlab (LSCM/Voronoi timeout on 180K triangles), open3d (install fails), xatlas (3/10 quality, subprocess integration fails). All external Python UV tools are not viable for the QR pipeline.
  technique for improving utilization on QR meshes. Includes `seams_from_islands()`
  workflow, bmesh island detection in edit mode, row-first layout algorithm,
  and the critical normalize-to-[0,1] step (47.6% OOB without it).
