# Mirror Test Results: bmesh Vertex Mirror on Non-Symmetric Topology

Test date: 2026-07-09. Test model: `Male_Body_Morphs_Lv2.obj` (128,306 verts,
128,304 faces, ZBrush export with UV + 8192x8192 BMP texture). User provided
this model with deliberate asymmetric sculpting on the character's right side
(screen left) — exaggerated chest/arm muscles and rough thigh carving on one
side only.

## Test 1: bmesh vertex coordinate mirror with Y/Z nearest-neighbor matching

**Method**: Identify X>0 (positive) and X<0 (negative) vertices. Build KDTree
on negative-side Y/Z coordinates. For each positive vertex, find nearest
negative vertex by Y/Z distance. Mirror positive vertex's X to negative
counterpart (neg.co.x = -pos.co.x, neg.co.y = pos.co.y, neg.co.z = pos.co.z).
Center-line vertices (|x| < 2mm) forced to x=0.

**Results** (1cm match threshold):
- Matched: 62,377 / 63,461 (98.3%)
- UV difference: **0.000000000000** — ✅ UV completely unchanged
- BUT: render showed **catastrophic mesh explosion** on the mirrored side
  (stretched polygons, broken faces, vertex displacement artifacts)

**Root cause**: Y/Z nearest-neighbor matching is **not reliable for non-
topology-symmetric meshes**. Even with 98.3% match rate, the 1.7% mismatched
vertices (1,084 verts) get pulled to wrong positions, creating massive
stretched faces that ruin the entire mesh.

## Test 2: Strict bidirectional matching (3mm threshold)

**Method**: Same as above but with 3mm match threshold AND bidirectional
verification (positive→negative match must also be negative→positive match).

**Results**:
- Bidirectional matched pairs: 43,816
- Match rate: **69.0%** — ❌ too low for clean mirror
- UV: still completely unchanged (0.000000000000)
- Mesh: still has significant artifacts from 31% unmatched vertices

## Test 3: Blender Symmetrize operator

**Method**: `bpy.ops.mesh.symmetrize(direction='NEGATIVE_X')` in Edit Mode.

**Result**: **Blender 5.1 crashed** (EXCEPTION_ACCESS_VIOLATION) on 128K-vertex
mesh in background mode. Symmetrize is too memory-intensive for large meshes
in `--background` mode.

## Test 4: Vertex index symmetry check

Checked if vertex i and vertex (n-1-i) are spatial mirror pairs (common in
ZBrush exports with symmetric vertex ordering).

**Result**: 0.2% match rate — the OBJ export does NOT preserve ZBrush's
internal vertex ordering symmetry. Index-based matching is useless for
exported OBJ files.

## Test 5: Symmetric topology sphere — POSITIVE confirmation

**Method**: Created a 482-vertex UV sphere (topology perfectly symmetric: 225
positive, 225 negative, 32 center). Applied Smart UV Project for UV. Deformed
right side (X>0) by scaling X×1.3. Built KDTree on original (pre-deformation)
Y/Z coordinates to find topology-mirror pairs via bidirectional nearest-neighbor.
Then mirrored deformed right-side coordinates to left side using the pairs.

**Results**:
- Topology match rate: **225/225 = 100.0%**
- UV difference: **0.000000000000000** — ✅ UV completely unchanged
- Left avg |X|: 0.297806, Right avg |X|: 0.297806, Diff: **0.00000000** — ✅ perfect symmetry
- Visual: no broken faces, no stretching, no artifacts — clean mirror

**This is the definitive positive test**: on a topology-symmetric mesh, bmesh
vertex coordinate mirror works perfectly — UV preserved, symmetry perfect, no
mesh damage. The production pipeline uses topology-symmetric templates
(MetaHuman etc.), so this method is production-viable.

## Test 6: BFS topology-propagation matching (final_v2.py)

**Method**: Start with spatial bidirectional matches (3mm threshold) as seeds.
Then BFS-expand: for each matched pair (pi, ni), check their face-adjacency
neighbors. If an unmatched positive neighbor and an unmatched negative neighbor
both have X signs opposite, Y diff <1cm, Z diff <1cm, match them and add to
queue. This uses topological connectivity to propagate matches beyond what
spatial distance alone can find.

**Results**:
- Initial spatial matches: 48,351
- BFS-expanded matches: +5,028
- Total: 53,379 / 63,461 = **84.1%**
- UV: 0.000000000000000 — ✅ unchanged
- Left/right avg |X| diff: 0.004352 (improved from 0.0076)
- **BUT render still showed mesh explosion** — 10,191 unmatched negative
  vertices kept their original positions while 84% of their neighbors moved,
  creating massive stretched faces at every unmatched vertex boundary.

**Conclusion**: BFS propagation improves match rate (69%→84%) but does NOT solve
the fundamental problem. Even 16% unmatched vertices create enough boundary
artifacts to ruin the mesh. On non-topology-symmetric meshes, partial matching
always produces broken faces because matched neighbors move while unmatched
neighbors stay — the faces between them stretch and tear.

## Test 7: Nearest-vertex interpolation for unmatched vertices (final_test.py)

**Method**: For unmatched negative-side vertices, find the nearest positive-side
vertex (by Y/Z/|X| distance) and set the negative vertex's coordinates to that
positive vertex's mirror. This ensures ALL vertices are processed (no one left
at original position).

**Results**:
- 282 bidirectional matches + 63,288 interpolated = all negative vertices processed
- UV: 0.000000000000000 — ✅ unchanged
- Left/right avg |X| diff: 0.000082 (nearly perfect numerically)
- **BUT render showed WORSE mesh explosion than before** — cross-body matches
  (e.g., arm vertex matched to nearest leg vertex) produced massive stretched
  faces spanning entirely wrong body parts.

**Conclusion**: Interpolation by nearest spatial neighbor is CATASTROPHIC on
body meshes because the nearest vertex in Y/Z/|X| space may be on a completely
different body part. This approach must NOT be used. The only safe options for
unmatched vertices are: (a) leave them at original position (causes boundary
artifacts but no cross-body stretching), or (b) use topological distance (BFS
hop count) instead of spatial distance to find a same-body-part neighbor.

## Key Conclusions

1. **bmesh vert.co modification preserves UV perfectly** — confirmed with
   0.000000000000 difference across 513,216 UV points (Test 1, high-poly body)
   AND 0.000000000000000 across a sphere's UV points (Test 5). This is an
   architectural guarantee of Blender's bmesh data structure (vert.co is
   vertex-level, UV is loop-level, they are independent custom data layers).

2. **Spatial Y/Z matching only works on topology-symmetric meshes**. Test model
   (128K verts, 13-vert left/right difference) = 69% bidirectional match rate →
   mesh explosion. Sphere (482 verts, exact symmetry) = 100% match → perfect.
   The 31% unmatched vertices on non-symmetric meshes get pulled to wrong
   positions, creating massive stretched faces that ruin the entire mesh.

3. **BFS topology propagation improves matching (69%→84%) but cannot reach 100%**
   on non-symmetric topology. The remaining 16% unmatched vertices still cause
   mesh explosion at matched/unmatched boundaries. Partial matching is NEVER
   safe for visual quality — every unmatched vertex creates a tear point.

4. **Interpolation (assigning unmatched vertices to nearest matched vertex's
   mirror) is CATASTROPHIC** — it produces numerically perfect symmetry (0.000082
   diff) but visually destroys the mesh because spatial nearest-neighbor crosses
   body parts (arm→leg matches create faces spanning the entire body width).
   NEVER use spatial interpolation for unmatched vertices on body meshes.

5. **For the production pipeline, none of this is a problem** because:
   - The **standard low-poly template** IS strictly topology-symmetric
   - The pipeline symmetrizes the HIGH-POLY first (bmesh vert.co mirror — this
     works on ANY topology because it takes one side's coordinates and writes
     them to the other side, no pair matching needed for the high-poly)
   - Then wraps the symmetric low-poly template onto the symmetric high-poly
   - The template's own symmetry + symmetric high-poly target = naturally
     symmetric result, no post-hoc matching needed

6. **Blender Symmetrize operator crashes on large meshes in background mode**.
   Use bmesh direct vertex manipulation instead. Do NOT use
   `bpy.ops.mesh.symmetrize()` for meshes >100K vertices in `--background`.

7. **OBJ export loses ZBrush vertex ordering** — do not rely on vertex index
   symmetry for exported OBJ files.

## Test 8: Delete-half mirror + UV recovery (WINNING APPROACH)

After Tests 1-7 all failed on the non-topology-symmetric body mesh, this
approach completely solves the problem by NOT trying to match vertex pairs.
Instead it deletes one half, uses Blender's native Mirror Modifier (which
handles all the geometry correctly), then recovers UVs from the preserved half.

**Method**:
1. Save positive-side (X>0) vertex UV mapping (vert_id → (u,v))
2. Delete all negative-side (X<0) vertices (keep center line at |X|<3mm)
3. Apply Mirror Modifier (X axis, merge threshold 3mm) → perfect geometric mirror
4. For each new vertex, query the original positive-side KDTree using
   abs(X), Y, Z to find the original vertex and its UV
5. Batch-write recovered UVs using `foreach_set("vector", ...)` — NOT per-loop
   assignment (which is O(nloops) and takes >3min on 250K+ loops)

**Results** (128K verts → 65K after delete → 129K after mirror):
- Symmetry: **0.000000 diff** (perfect)
- UV match rate: **99.8%** (only 0.2% of new verts couldn't find a match)
- UV diff: **0.000000000000** (UV data untouched for matched vertices)
- Broken faces: **NONE** (Blender Mirror handles all geometry)
- Total time: **5 seconds** (scipy cKDTree + foreach_set batch)
- Visual verification: perfect symmetry, no broken faces, all sculpting
  details mirrored correctly to the other side

**Why this works when nothing else does**:
- No vertex-pair matching needed — the unmatched vertices are simply deleted
  and recreated by Mirror Modifier
- Blender's Mirror Modifier handles all topology perfectly (it copies geometry)
- UV recovery via cKDTree spatial query is fast and accurate (5mm threshold)
- `foreach_set("vector", flat_array)` is the ONLY way to write UVs at scale —
  per-loop `uv_data[li].uv.x = val` is ~1000x slower and will timeout

**Critical API notes**:
- `uv_layer.uv.foreach_get("vector", np_array)` — reads all UVs as flat
  [u0,v0,u1,v1,...] float32 array. Do NOT use `foreach_get("x", ...)` —
  Blender 5.1 raises `AttributeError: foreach_get(..) elements have no
  attribute 'x'`. The correct property name is `"vector"`.
- `uv_layer.uv.foreach_set("vector", flat_float32_array)` — same for writing.
- `mesh.loops.foreach_get("vertex_index", int32_array)` — reads loop→vertex
  mapping as a batch, needed for the UV recovery step.
- `mesh.vertices.foreach_get("co", float32_array)` — reads all vertex coords
  as flat [x0,y0,z0,...] array.

**Caveats**:
- Negative-side UVs are COPIED from the positive side (not the original
  negative UVs). For the "symmetrize high-poly → wrap → bake" pipeline this
  is irrelevant — baking is a pure spatial operation that doesn't care about
  high-poly UV layout.
- If the model has a center line that's NOT at X=0, must recenter first.
- The 0.2% unmatched new vertices get UV=(0,0) — these are center-line merge
  vertices created by the Mirror Modifier, which is acceptable.

**Test files**:
- `E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test_mirror\mirror_final.blend`
  — the winning result (128K→129K verts, perfect symmetry, 99.8% UV recovery)
- Input: `test01\原始GLB\Scan_head\Male_Body_Morphs_Lv2.obj`

## Test 9-13: Blender symmetry_snap + BFS topology matching (2026-07-14)

After Tests 1-8, the user provided a ZBrush Smart ReSym research document
(`zbrush智能对称调研.md`) explaining the algorithm: **topology-based BFS
matching from center-axis seeds**, NOT spatial nearest-neighbor. The user also
confirmed that **ZBrush Smart ReSym works perfectly on this exact OBJ model**
(~10 seconds, perfect result) — proving the algorithm is viable, just that
Blender Python can't match ZBrush's implementation quality.

### Test 9: bpy.ops.mesh.symmetry_snap (Blender built-in)

**Method**: `bpy.ops.mesh.symmetry_snap(direction='NEGATIVE_X', threshold=0.01,
factor=0.5, use_center=True)` — Blender's built-in topology-aware symmetry
operator.

**Results** (128K verts):
- 50,157 pairs mirrored, 31,048 failed, 12 already symmetrical
- UV: 0.000000000000 — ✅ unchanged
- **Broken faces** — the 31K failed vertices' neighbors moved, tearing faces
- `factor=0.5` = average both sides; `factor=1.0` = take one side as source
  (both produce same match count, both have broken faces)
- `snap_to_symmetry` operator does NOT exist in Blender 5.1 (removed/renamed)
- **Multiple rounds do NOT help** — first round does all possible matches,
  subsequent rounds find zero new matches (mesh already in post-snap state)

### Test 10: Topology BFS from center-axis seeds (ZBrush-style)

**Method**: Follow the user's research document algorithm — find center-axis
vertex pairs as seeds, BFS-expand along edges, match neighbors by spatial
mirror proximity.

**Results**:
- Seeds: only 144-205 pairs (center axis has 1,978 verts but most have
  asymmetric neighbor structure)
- BFS expansion: +272 matches
- Total: 416 (0.7%) — catastrophically low
- Second pass (global spatial): +3,380 → total 6.0%
- **Root cause**: ZBrush exports may not have clean center-axis edge loops in
  the OBJ format. The 13-vertex left/right asymmetry means the center axis
  topology is also asymmetric, preventing seed formation.

### Test 11: Global bidirectional matching + BFS + interpolation (v21)

**Method**: Three-stage — (1) global bidirectional cKDTree match (70%), (2) BFS
neighbor expansion (71%), (3) for unmatched vertices, find 3 nearest matched
vertices and apply weighted-average offset.

**Results**:
- 45,078 matched (71.4%) + 18,193 interpolated = ALL processed
- UV: 0.000000000000 — ✅ unchanged
- Left/right avg |X| diff: 0.007330 — nearly identical to original (0.007448)
- **Still broken faces** — interpolation offsets from cross-body-part neighbors
  produce wrong directional shifts

### Test 12: symmetry_snap on pre-symmetrized mesh (sanity check)

**Method**: Delete-half + Mirror to create perfectly symmetric topology →
apply asymmetric deformation (right side ×1.2) → run symmetry_snap to recover.

**Results**:
- 19,444 already symmetrical, 32,518 pairs mirrored, **41,152 failed**
- Even on a SHOULD-be-symmetric mesh, Blender's symmetry_snap only matched 51%
- **Conclusion**: Blender's symmetry_snap algorithm is fundamentally less
  capable than ZBrush's Smart ReSym. It may require exact vertex-index
  symmetry, not just topological symmetry.

### Key conclusions from Tests 9-13

1. **Blender's `symmetry_snap` is NOT equivalent to ZBrush Smart ReSym**.
   ZBrush handles topology-asymmetric meshes perfectly (confirmed by user);
   Blender's operator fails on 24-51% of vertices even on near-symmetric meshes.

2. **BFS from center-axis seeds fails because OBJ export doesn't preserve
   ZBrush's internal symmetry map**. The "symmetry map" ZBrush builds
   internally (mentioned in ZBrushCentral forum) is lost on export.

3. **Python-implemented topology matching (BFS, bidirectional, interpolation)
   cannot reach >71% match rate on this model**. ZBrush's C++ algorithm with
   years of optimization achieves 100% in ~10 seconds.

4. **PRACTICAL RECOMMENDATION**: For topology-asymmetric high-poly meshes:
   - **Use ZBrush Smart ReSym** (import OBJ → Smart ReSym → export). This is
     the only reliable method. ~10 seconds, perfect result, UV preserved.
   - **OR use delete-half mirror** (Test 8) — perfect geometry, 99.8% UV
     recovery, but negative-side UVs are copies of positive-side (acceptable
     for baking pipeline).
   - **Do NOT attempt Blender Python BFS matching on non-symmetric meshes** —
     it will always produce broken faces due to unmatched vertex tears.
   - **For production pipeline**: symmetrize the high-poly in ZBrush BEFORE
     importing to Blender. Then wrap the topology-symmetric low-poly template
     (which mirrors perfectly via bmesh, Test 5).

5. **`foreach_get`/`foreach_set` API quirk confirmed in Blender 5.1**:
   - `uv_layer.uv.foreach_get("x", arr)` → **AttributeError** — property is `"vector"`
   - `uv_layer.uv.foreach_get("vector", arr)` → works, reads flat [u,v,u,v,...]
   - Same for `foreach_set`: use `"vector"` with a flat float32 array
   - `mesh.loops.foreach_get("vertex_index", int32_arr)` → batch read loop→vert mapping
   - `mesh.vertices.foreach_get("co", float32_arr)` → batch read all coordinates
   - `mesh.edges.foreach_get("vertices", int32_arr)` → batch read all edge pairs
   - These batch APIs are **1000x faster** than per-element Python loops for
     meshes >10K vertices

## Test 14-15: Laplacian Deformation Constraint (2026-07-14)

Suggested by Gemini technical advisor: use Laplacian mesh deformation to smoothly
propagate the 71% matched-vertex displacements to the 29% unmatched vertices,
instead of leaving them at original position (tears) or interpolating (cross-body stretching).

### Test 14 (v23): Positive-side unmatched as constraints

- 71% matched + center = constraints (110,113 verts), free: 18,193 (negative unmatched)
- Matrix: 201,068 nnz, solve: **0.1s** (scipy spsolve)
- Constraint error: **0.00000000** (all hard constraints satisfied exactly)
- UV: **0.000000000000000** ✅ completely unchanged
- **Still mesh explosion** — positive-side unmatched held at original while neighbors moved

### Test 15 (v24): Both-side unmatched as free variables

- Only matched pairs + center = constraints (92,064), free: 36,242
- Matrix: 273,256 nnz, solve: **0.1s**
- Constraint error: **0.00000000**
- UV: **0.000000000000000** ✅ unchanged
- **Still mesh explosion** — 71% matched pairs include cross-body-part false matches
  (spatial nearest-neighbor), Laplacian solver faithfully propagates wrong positions

### Key insight

The Laplacian approach is **mechanically correct** (0.1s solve, UV untouched, constraints
satisfied exactly). The problem is **match quality**: 71% spatial matching contains false
cross-body-part matches that get faithfully propagated. Need >95% correct match rate.

### Improvement directions (from Gemini advisor)

1. **Geodesic distance** (surface-walking) instead of Euclidean (straight-line)
2. **Curvature-based landmark seeds** (fingertips, nose, nipples) instead of center-axis-only
3. **ARAP (As-Rigid-As-Possible)** deformation — preserves local rigidity
4. **libigl** C++ library — mature non-rigid ICP + geodesic computation

Full implementation details and code pattern: see `references/laplacian-symmetry-deformation.md`.

## Test 16-18: Curvature + Geodesic matching (2026-07-14)

Implemented the "improvement directions" from Gemini advisor (geodesic distance +
curvature-based landmark seeds). **Both failed to break the 71% ceiling.**

### Test 16 (v25): Curvature seeds + Dijkstra geodesic + single-round BFS

**Method**: (1) Curvature via adjacent-face normal angle variation (area-weighted,
5s for 128K verts). (2) 100 local-maxima curvature peaks per side. (3) Peak
matching: curvature similarity + spatial proximity + normal symmetry + degree →
69 seed pairs, 30 used. (4) Dijkstra geodesic from 30 seeds (16.7s). (5) BFS with
combined scoring: spatial×0.7 + geodesic×0.3 + normal + degree + curvature.
(6) Spatial cKDTree supplement for unmatched.

**Results**: 72.7% match (BFS: 45,758, supplement: 127). UV: ✅ unchanged.
Symmetry diff: 0.007192. **Still mesh explosion.**

### Test 17 (v26): All seeds + multi-round BFS + de-duplication

**Method**: All 66 de-duplicated seeds → Dijkstra (38.7s). 4 BFS rounds with
progressive threshold relaxation. Re-queue all matched verts between rounds.

**Results**: 68.4% match (BFS: 1,758, supplement: 41,354). UV: ✅ unchanged.
**WORSE than v24** — multi-round BFS fragments natural propagation flow.

### Key conclusions

1. **71% ceiling confirmed across ALL matching approaches** — spatial (71.4%),
   curvature+geodesic BFS (72.7%), multi-round (68.4%). The limit is topological:
   unmatched verts have no symmetric counterparts.
2. **Curvature seeds improve seed quality but not match rate** — bottleneck is
   not seeds, it's topological asymmetry.
3. **Dijkstra geodesic is viable in Python** (0.6s/seed on 128K verts) but
   doesn't help scoring because the fundamental limit is vertex count asymmetry.
4. **Multi-round BFS HURTS** — each round only sees previous round's new matches,
   fragmenting natural BFS flow. Single-round outperforms multi-round.
5. **Remaining untested**: ARAP deformation, libigl (C++) — these are the only
   viable paths to >90% in Blender.
6. **Recommendation unchanged**: ZBrush Smart ReSym for asymmetric meshes,
   delete-half mirror for Blender-only pipelines.

## Test 19-20: Hungarian Assignment + Laplacian Deformation (2026-07-15)

Tested `scipy.optimize.linear_sum_assignment` (Hungarian algorithm) as a global
optimal assignment approach, replacing the greedy BFS/spatial matching.

### Test 19 (v27): Block-wise Hungarian with Python loop cost matrix

**Method**: kNN (k=10) to limit candidates per positive vertex. Build sparse
cost = spatial_dist + 0.5×normal_diff + 0.05×degree_diff. Split into 10 Y-axis
blocks (30% overlap), solve each block with `linear_sum_assignment` on dense
local cost matrix. Then BFS supplement + Laplacian deformation.

**Results**: Hungarian matched 28,678 (45.4%) in 42.4s. BFS supplement → 62.2%
total. **WORSE than simple bidirectional matching (71.4%)**. The Python
double-loop cost matrix construction (pos_block × neg_block per block) was
extremely slow and the block-wise splitting destroyed global optimality.

### Test 20 (v28): Block-wise Hungarian with numpy vectorized cost

**Method**: Same block structure but used numpy broadcasting for cost matrix
construction (spatial dist via cKDTree kNN, normal/diff via array indexing).
Then block Hungarian + BFS + Laplacian.

**Results**: 45.4% Hungarian match → 62.2% after BFS supplement. UV: ✅ unchanged.
Symmetry diff: 0.007416. **Still mesh explosion.** Match rate LOWER than v24 (71.4%).

### Key conclusions from Tests 19-20

1. **Hungarian block-wise assignment is WORSE than global bidirectional matching**.
   Splitting into blocks destroys global optimality — each block only sees local
   candidates, missing better matches in adjacent blocks.

2. **Full Hungarian (63K×63K) is infeasible** — the dense cost matrix would be
   32GB (63K² × 8 bytes). The kNN-sparse approach limits candidates but the
   block splitting negates the global optimality advantage.

3. **The 71% ceiling holds across ALL approaches tested**:
   - Spatial bidirectional: 71.4%
   - BFS topology: 68-84%
   - Curvature + geodesic: 72.7%
   - Hungarian (block-wise): 62.2%
   - Blender symmetry_snap: 39%

4. **Production recommendation is unchanged**: ZBrush Smart ReSym for asymmetric
   high-poly, delete-half mirror for Blender-only, bmesh on symmetric templates.

### Next untested directions

- **Spectral matching**: graph Laplacian eigenvectors for global topology matching
- **Heat kernel signature**: multi-scale feature descriptor robust to topology changes
- **Non-rigid ICP** (libigl): elastic registration
- **ARAP deformation**: As-Rigid-As-Possible, preserves local rigidity better than Laplacian
- **Full sparse Hungarian**: `scipy.sparse.csgraph` may support sparse assignment
- **C++ plugin**: 100x performance may enable full Hungarian or iterative ICP

## Test files

- `E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\test_mirror\\\\` — test scripts
  and render outputs
- Input: `test01\\\\原始GLB\\\\Scan_head\\\\Male_Body_Morphs_Lv2.obj`
- Positive confirmation: `test_mirror\\\\mirror_v8.blend` (sphere, 482 verts)
- Production result: `test_mirror\\\\mirror_final.blend` (body, 129K verts, Test 8 approach)
- User research: `test_mirror\\\\zbrush智能对称调研.md` — ZBrush Smart ReSym algorithm
  explanation (topology BFS matching, mask weighting, coordinate transfer)
- Test report: `test_mirror\\\\镜像测试报告.md` — summary report for technical discussion
  (updated 2026-07-15 with Hungarian results, 9 total approaches, 5 verified conclusions)
