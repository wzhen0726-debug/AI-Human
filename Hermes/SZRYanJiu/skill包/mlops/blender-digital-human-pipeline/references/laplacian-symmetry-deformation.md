# Laplacian Deformation Constraint for Mesh Symmetry (Tests 14-15, 2026-07-14)

Suggested by Gemini technical advisor: use Laplacian mesh deformation to smoothly
propagate the 71% matched-vertex displacements to the 29% unmatched vertices,
instead of leaving them at original position (tears) or interpolating (cross-body stretching).

## Algorithm

1. The 71% spatially-matched vertex pairs are **hard constraints** (target = mirrored coordinates, weight=1000)
2. The 29% unmatched vertices are **free variables** (unknowns)
3. Center-axis vertices: hard constraint X=0
4. Objective: minimize change in Laplacian coordinates (vertex-to-neighbor relative vectors)
5. Solve sparse linear system L·x = b via `scipy.sparse.linalg.spsolve`

## Test 14 (v23): Positive-side unmatched as constraints

- 71% matched + center = constraints (110,113 verts), free: 18,193 (negative unmatched)
- Matrix: 201,068 nnz, solve: **0.1s**
- Constraint error: **0.00000000**
- UV: **0.000000000000000** ✅
- **Still mesh explosion** — positive-side unmatched held at original while neighbors moved

## Test 15 (v24): Both-side unmatched as free

- Only matched pairs + center = constraints (92,064), free: 36,242
- Matrix: 273,256 nnz, solve: **0.1s**
- Constraint error: **0.00000000**
- UV: **0.000000000000000** ✅
- **Still mesh explosion** — 71% matched pairs include cross-body-part false matches
  (spatial nearest-neighbor), Laplacian solver faithfully propagates wrong positions

## Key Insight

The Laplacian approach is **mechanically correct** (0.1s solve, UV untouched, constraints
satisfied exactly). The problem is **match quality**: 71% spatial matching contains false
cross-body-part matches that get faithfully propagated. Need >95% correct match rate.

## Improvement Directions (from Gemini advisor)

1. **Geodesic distance** (surface-walking) instead of Euclidean (straight-line) — avoids cross-body matches
2. **Curvature-based landmark seeds** (fingertips, nose, nipples) instead of center-axis-only seeds
3. **ARAP (As-Rigid-As-Possible)** deformation — preserves local rigidity, more robust to wrong matches
4. **libigl** C++ library — mature non-rigid ICP + geodesic computation

## Tests 16-18 (2026-07-14): Curvature + Geodesic — TESTED, INSUFFICIENT

Directions 1 and 2 above were fully implemented and tested. **Both failed to improve
match rate beyond the 71% ceiling.**

### Test 16 (v25): Curvature seeds + Dijkstra geodesic + BFS

**Method**: (1) Compute vertex curvature via adjacent-face normal angle variation
(area-weighted). (2) Extract 100 local-maxima curvature peaks per side. (3) Match
peaks by curvature similarity + spatial proximity + normal symmetry + degree → 69
seed pairs (30 used). (4) Dijkstra single-source geodesic from each seed (16.7s for
30 seeds). (5) BFS expand: for each neighbor pair, score = weighted sum of spatial
distance + geodesic distance difference + normal symmetry + degree difference +
curvature difference. (6) Supplement with global spatial cKDTree matching.

**Results**:
- Seeds: 69 (de-duplicated), 30 used for Dijkstra
- BFS matched: 45,758, spatial supplement: 127
- Total: **72.7%** (marginal improvement over 71.4%)
- UV: 0.000000000000000 ✅
- Symmetry diff: 0.007192 (same as v24's 0.007211)
- **Still mesh explosion** on right side (arm melt, thigh tear)
- Dijkstra: 16.7s for 30 seeds on 128K verts (Python heapq)

### Test 17 (v26): All seeds + multi-round BFS + de-duplication

**Method**: Same as v25 but: (1) use ALL 66 de-duplicated seed pairs for Dijkstra
(38.7s). (2) 4 rounds of BFS with progressively relaxed thresholds (spatial
0.02→0.03, geodesic 0.03→0.04, normal 2.0→2.5, degree 8→12). (3) Re-queue ALL
matched vertices between rounds to catch missed neighbors.

**Results**:
- BFS 4 rounds: 257→427→484→590 = 1,758 total BFS matches
- Spatial supplement: 41,354 (bulk came from cKDTree, not BFS)
- Total: **68.4%** (WORSE than v24's 71.4%)
- **Multi-round BFS HURT** — fragmenting the flow into rounds prevents
  natural BFS propagation; each round only sees new matches from previous round
- Dijkstra: 38.7s for 66 seeds on 128K verts

### Key conclusions from Tests 16-18

1. **Curvature-based seeds produce better quality seed pairs** (66 unique 1:1
   pairs vs 144-205 from center axis) but this does NOT translate to higher
   overall match rate. The bottleneck is NOT seed quality.

2. **Dijkstra geodesic distance is computationally viable** in Python (0.6s per
   seed on 128K verts) but using it as a scoring feature in BFS does not improve
   matching because the fundamental limit is topological: unmatched vertices
   genuinely don't have symmetric counterparts.

3. **Multi-round BFS with progressive threshold relaxation HURTS performance**
   — each round only sees new matches from the previous round's queue, fragmenting
   the natural BFS flow. Single-round BFS (v25) at 72.7% outperformed multi-round
   (v26) at 68.4%.

4. **The 71% ceiling is confirmed across ALL matching approaches tested**:
   - Pure spatial cKDTree: 71.4% (v24)
   - Curvature + geodesic BFS: 72.7% (v25)
   - Curvature + geodesic + multi-round BFS: 68.4% (v26)
   - All produce mesh explosion because 28-30% unmatched vertices tear at
     matched/unmatched boundaries.

5. **Remaining untested directions**: ARAP deformation and libigl (C++) may
   still help — they were NOT tested in this round. ARAP's local-rigidity
   constraint could prevent the cross-body-part stretching that Laplacian
   propagates. libigl's non-rigid ICP could achieve higher match rates than
   Python BFS. These remain the only viable paths to >90% match in Blender.

6. **Practical recommendation unchanged**: For topology-asymmetric high-poly
   meshes, use ZBrush Smart ReSym (10s, perfect). For Blender-only pipelines,
   use delete-half mirror (Test 8, 99.8% UV recovery). Do NOT attempt
   curvature+geodesic matching in Python on 128K-vertex topology-asymmetric
   meshes — it will not exceed 73% and will produce broken faces.

## Implementation Code Pattern

```python
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import spsolve

# Build with numpy arrays (NOT lil_matrix append — O(n²) on 128K verts)
# Constrained rows: L[i,i] = w_c, b[i] = target[i] * w_c
# Free rows: L[i,i] = w_l * degree(i), L[i,nbr] = -w_l, b[i] = w_l * laplacian_delta(i)
# Solve: new_pos = spsolve(L, b)  # (nverts, 3)
# Batch construction: 0.1s build + 0.1s solve for 128K verts
```
