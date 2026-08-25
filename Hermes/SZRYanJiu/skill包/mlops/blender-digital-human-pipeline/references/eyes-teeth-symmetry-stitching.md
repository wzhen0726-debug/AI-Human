# Eyes, Teeth, Self-Intersection, Symmetry, and Head-Body Stitching

Research date: 2026-07-08. Covers findings from the full-pipeline design session.

## Eye/Teeth Handling in Standard Digital Human Pipeline

### Standard practice (MetaHuman/industry)
- Head mesh (`MH_Head_01` / `MetaHuman_BaseMesh.obj`) does **NOT** contain
  eyeballs, teeth, or tongue geometry — those are independent mesh objects.
- However, the head mesh is **NOT** a simple open shell with holes — it has
  **interior cavity walls** for eye sockets and oral cavity (see
  `references/head-cavity-topology-analysis.md` for the definitive analysis).
- **Eye sockets**: The eyelid boundary (112-vert loop) is the eye *opening*;
  behind it, mesh continues inward ~15-26mm forming the eye socket interior
  wall (~920 inward-facing faces per eye). The eyeball sits inside this pocket.
- **Oral cavity**: The lip boundary (168-vert loop) is the mouth *opening*;
  behind it, mesh continues inward ~40mm forming the oral cavity interior wall
  (~2,400 inward-facing faces). Lips have both exterior and interior mesh
  (~4,600 interior-facing lip faces).
- **Implication for wrap**: Template interior-wall vertices MUST also fit the
  high-poly's corresponding interior surfaces. Shrinkwrap NEAREST frequently
  fails here — it pulls interior-wall vertices to the wrong surface (exterior
  cheek/brow). This is why dense contour anchors around eye rims and lips are
  critical (see Bug 4 in landmark-retopology.md).
- Eyes, teeth, tongue are **independent mesh objects**, each bound to their
  own bones:
  - Eyes → `eye_L`/`eye_R` bones (rotation only, look up/down/left/right)
  - Upper teeth → fixed to skull
  - Lower teeth → bound to `jaw` bone (opens/closes with mouth)
  - Tongue → `tongue` bone chain
- Standard eye: UV sphere, ~512 faces. Standard teeth: upper+lower arch,
  ~2K faces. These come from template assets, not from the scan/AI mesh.

### AI high-poly eye interference with Shrinkwrap
Tripo AI generates solid-sphere eyes fused to the head mesh. During
Shrinkwrap, eye-socket vertices get pulled to the **eye sphere surface**
instead of the eye-socket interior wall, causing eyelids to wrap around
the eyeball rather than forming an open socket.

### Required preprocessing: delete AI eyes/teeth before wrap
1. Use MediaPipe eye keypoints (idx 33, 263, 133, 362, etc.) → compute
   centroid of eye region
2. Find closed/connected mesh components within radius ~15mm of centroid
   (eyeball is a sphere, radius ~10-13mm, high curvature, closed surface)
3. Delete those connected components (the eyeball geometry)
4. Delete teeth similarly: MediaPipe inner/outer lip keypoints → find
   white/bright geometry between them → delete
5. Result: head with eyeball/teeth geometry removed, but eye socket and
   oral cavity **interior walls still present** (these are part of the head
   shell, not the eyeball). The cavities are now empty of solid objects
   (no eyeball/teeth), but the interior mesh walls remain.

### Post-wrap assembly
After wrap completes, separately import standard eye/teeth templates:
- Eye positioning: center = mean of eye-socket edge vertices (from
  MediaPipe eye contour → matched template vertices); radius = mean distance
  from socket edge to center × 1.1
- Teeth positioning: align to oral cavity, upper fixed, lower bound to jaw

## Self-Intersection: Structural Limit of Shrinkwrap

### The pinch vs self-intersection contradiction
- v3.4 (Laplacian + find_nearest): 178 facial self-intersections
- v3.20 (added pinch repair): self-intersections **increased to 559**
- Pinch repair pushes overlapping vertices apart → creates new folds in
  concave regions (ala, mouth corners)
- Self-intersection repair (Laplacian pull-together) → causes new pinching

**Conclusion: 178 self-intersections is the structural floor of pure
Shrinkwrap NEAREST_SURFACEPOINT.** Not a parameter-tuning problem.

### Root cause
Shrinkwrap NEAREST is anatomy-blind nearest-face projection:
- Thin structures (lips, ala, eyelids): vertices pulled to opposite side
- Concavities (nostrils, eye sockets, mouth corners): ray hits wrong face
- High curvature (nose bridge): adjacent vertices project to same point → pinch

### Improvement paths (in priority order)
1. **Region-constrained projection** (Wrap4D-style): define vertex groups
   (eye_ring, lip_ring, nose_ala, cheek), each with different wrap strategy.
   Lips/eyelids: dense MediaPipe anchors only, no Shrinkwrap for those verts.
   Nose: limit projection direction to face-forward (-Y).
2. **FLAME/DECA shape prior**: DECA estimates FLAME params from photo →
   FLAME mesh as intermediate layer (high-poly → FLAME → MetaHuman template).
   FLAME constrains vertices to plausible face shapes, prevents penetration.
3. **Auto-cleanup script** (fallback): `bmesh.ops.dissolve_degenerate` →
   `remove_doubles(0.1mm)` → 1 round Laplacian + find_nearest on residual →
   export. Fully automated, no Blender UI needed.

## Blender Symmetry: Geometry-Only, Preserve UV/Texture

### ZBrush Smart Resymmetry behavior (user's desired effect)
- Mirrors vertex positions (left→right or right→left)
- **Does NOT modify UV maps** — left/right UV islands stay as-is
- **Does NOT modify textures** — confirmed by ZBrush official docs
  (help.maxon.net/zbr): SmartReSym/ReSym descriptions only mention
  "positions of vertices/points", no UV operations. The Symmetry page
  states Poseable Symmetry "does not use UVs" and is "100% dependent on
  your mesh being topologically symmetrical." ZBrush has a separate
  Tool > UV Map panel with Flip U/V — if Resymmetry touched UV, these
  independent tools wouldn't be needed.
- **CRITICAL CAVEAT**: If model already has UV and baked textures, mirroring
  vertex positions while leaving UV unchanged causes **texture sampling errors** —
  the vertex moved to its mirror position but its UV still points to the original
  texture location. ZBrush's actual workflow for UV-textured models is:
  texture → convert to Polypaint (vertex color) → Resymmetry (Polypaint mirrors
  correctly with vertices) → regenerate UV and texture. OR: only use Resymmetry
  before UV/texture baking, when texture doesn't exist yet.
- **For our pipeline**: symmetrize the mesh BEFORE UV unwrap and texture baking.
  After symmetrization, do fresh UV unwrap + bake from high-poly — textures will
  be correct because they're baked after the geometry is finalized. This avoids
  the texture-sampling contradiction entirely.

### Blender architecture difference
- Mirror Modifier: mirrors geometry, has Flip UV option, but cannot achieve
  "geometry mirror + UV untouched" natively
- Symmetrize operator: creates new geometry → UV gets copied/mirrored too
- Blender UV lives on **loops** (`bm.loops.layers.uv`), vertex position
  lives on **verts** (`vert.co`) — these are **independent data layers**

### Solution: bmesh vertex-coordinate mirroring script
```python
import bmesh

def mirror_geometry_keep_uv(obj, axis='X', threshold=0.0001):
    """Mirror vertex coordinates only. UV and materials untouched."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()

    positive = [v for v in bm.verts if v.co.x > threshold]
    negative = [v for v in bm.verts if v.co.x < -threshold]
    center   = [v for v in bm.verts if abs(v.co.x) <= threshold]

    for pos_v in positive:
        best, best_d = None, float('inf')
        for neg_v in negative:
            d = (pos_v.co.y - neg_v.co.y)**2 + (pos_v.co.z - neg_v.co.z)**2
            if d < best_d:
                best_d, best = d, neg_v
        if best and best_d < 0.001:  # 1mm match threshold
            best.co.x = -pos_v.co.x
            best.co.y = pos_v.co.y
            best.co.z = pos_v.co.z

    for v in center:
        v.co.x = 0.0

    # UV layer is on loops — completely untouched by vert.co changes
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
```

Key: `vert.co` modification is in-place, no new verts/edges/faces created,
UV layer automatically preserved. Requires left/right topology to be
symmetric (same vertex count, 1:1 correspondence). If topology is
asymmetric, must handle topology symmetry first.

**Existing plugin**: `mio3io/mio3_symmetry` (GitHub) — can symmetrize
mesh, shape keys, vertex weights, UV map, normals independently. Supports
Blender 4.2+. May allow configuring geometry-only symmetry.

## Head-Body Topology Stitching Automation

### Problem
- Head: MetaHuman topology (~8K quad faces)
- Body: Quad Remesher or MetaHuman body topology
- Neck boundary needs stitching — team has no Blender users

### Preferred: unified boundary topology
- MetaHuman head template has fixed neck boundary (~32 vertices, pure
  quad loop)
- Force body topology to share the same 32-vertex boundary ring
- Merge by Distance (threshold 0.5mm) — no bridge needed
- This is MetaHuman's official approach (head and body share predefined
  stitching ring)

### Fallback: auto_stitch.py script
If body topology is already fixed with different boundary vertex count:
1. Detect both boundary loops (open edges → boundary ring)
2. If vertex counts differ → subdivide the smaller loop to match
3. Align by arc-length parameterization (t∈[0,1) around the loop)
4. `bmesh.ops.bridge_loops(bm, edges=head_boundary + body_boundary)`
5. Laplacian smooth + Shrinkwrap to high-poly for surface fit
6. Fully automated, runs via `blender --background --python auto_stitch.py`

### Best option: full-body wrap avoids stitching entirely
If using MetaHuman full-body template wrap (see full-body-wrap-research.md),
head and body are one continuous mesh — no stitching needed at all.
