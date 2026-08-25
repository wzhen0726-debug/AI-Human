# Curvature + Geodesic Matching for Mesh Symmetry (Tests 16-18, 2026-07-14)

Implementation details for curvature-based landmark seeds + Dijkstra geodesic
distance + BFS matching. While this approach did NOT break the 71% match ceiling
on topology-asymmetric meshes, the individual algorithms are reusable and the
code patterns are documented here for future reference (e.g., for ARAP or
libigl-based approaches).

## 1. Vertex Curvature via Adjacent Face Normal Variation

Computes an area-weighted average of the angle between adjacent face normals at
each vertex. This approximates mean curvature — high values indicate sharp
features (edges, tips), low values indicate flat regions.

```python
# Batch-read face data
npoly = len(mesh.polygons)
poly_verts = np.empty(nloops, dtype=np.int32)
mesh.loops.foreach_get("vertex_index", poly_verts)
loop_start = np.empty(npoly, dtype=np.int32)
loop_total = np.empty(npoly, dtype=np.int32)
mesh.polygons.foreach_get("loop_start", loop_start)
mesh.polygons.foreach_get("loop_total", loop_total)

# Compute face normals and areas via cross product
poly_normals = np.zeros((npoly, 3), dtype=np.float64)
poly_areas = np.zeros(npoly, dtype=np.float64)
for i in range(npoly):
    ls = loop_start[i]
    pvs = poly_verts[ls:ls+loop_total[i]]
    if len(pvs) >= 3:
        v0, v1, v2 = verts[pvs[0]], verts[pvs[1]], verts[pvs[2]]
        cross = np.cross(v1 - v0, v2 - v0)
        norm = np.linalg.norm(cross)
        if norm > 1e-12:
            poly_normals[i] = cross / norm
            poly_areas[i] = norm * 0.5

# Build vert→face adjacency
vert_faces = [[] for _ in range(nverts)]
for i in range(npoly):
    for vi in poly_verts[loop_start[i]:loop_start[i]+loop_total[i]]:
        vert_faces[vi].append(i)

# Curvature = area-weighted average of normal angles between adjacent face pairs
vertex_curvature = np.zeros(nverts, dtype=np.float64)
for vi in range(nverts):
    faces = vert_faces[vi]
    if len(faces) < 2:
        continue
    total_w, total_c = 0.0, 0.0
    for fi in faces:
        for fj in faces:
            if fi >= fj:
                continue
            dot = max(-1.0, min(1.0, poly_normals[fi] @ poly_normals[fj]))
            angle = np.arccos(dot)
            w = poly_areas[fi] + poly_areas[fj]
            total_c += angle * w
            total_w += w
    if total_w > 0:
        vertex_curvature[vi] = total_c / total_w
```

**Performance**: ~5-6 seconds for 128K vertices (Python loop). Could be
vectorized with scipy sparse matrix operations but was fast enough.

**Curvature range** on the test body model: [0.004, 2.078], mean 0.127.

## 2. Curvature Peak Extraction (Local Maxima)

Extracts local maxima of curvature with non-maximum suppression (2-hop neighbors
are suppressed to spread peaks across the mesh):

```python
def extract_curvature_peaks(indices, curvature, adj_list, top_n=120):
    peaks = []
    curv_vals = curvature[indices]
    sorted_order = np.argsort(-curv_vals)  # descending
    used = set()
    for idx in sorted_order:
        vi = indices[idx]
        if vi in used:
            continue
        # Check if local maximum (higher than all neighbors)
        is_peak = all(curvature[nj] <= curvature[vi] for nj in adj_list[vi])
        if is_peak:
            peaks.append((vi, curvature[vi]))
            # Suppress 2-hop neighbors
            used.add(vi)
            for nj in adj_list[vi]:
                used.add(nj)
                for nj2 in adj_list[nj]:
                    used.add(nj2)
        if len(peaks) >= top_n:
            break
    return peaks
```

**Result**: 100-120 peaks per side on 128K-vertex body mesh.

## 3. Seed Matching (Greedy 1:1 De-duplication)

Critical fix from v25→v26: multiple positive peaks can match the same negative
peak. Use greedy assignment sorted by combined score to ensure 1:1:

```python
# Build candidate list with combined score
seed_candidates = []
for i, pi in enumerate(pos_peak_idx):
    dist, idx = neg_peak_tree.query(pos_peak_coords[i], k=5)
    for j in range(min(5, len(idx))):
        ni = neg_peak_idx[idx[j]]
        curv_diff = abs(vertex_curvature[pi] - vertex_curvature[ni])
        norm_sym = (abs(normals[pi, 0] + normals[ni, 0]) +
                    abs(normals[pi, 1] - normals[ni, 1]) +
                    abs(normals[pi, 2] - normals[ni, 2]))
        deg_diff = abs(deg[pi] - deg[ni])
        if (dist[j] < 0.05 and curv_diff < 0.3 and
            norm_sym < 1.0 and deg_diff <= 6):
            score = dist[j] * 10 + curv_diff + norm_sym * 0.3 + deg_diff * 0.05
            seed_candidates.append((score, pi, ni))
            break

# Greedy 1:1 assignment
seed_candidates.sort()
used_pos, used_neg = set(), set()
seed_pairs = []
for score, pi, ni in seed_candidates:
    if pi in used_pos or ni in used_neg:
        continue
    seed_pairs.append((pi, ni))
    used_pos.add(pi); used_neg.add(ni)
```

**Result**: 66 unique seed pairs from 120 peaks per side.

## 4. Dijkstra Geodesic Distance (Python heapq)

Single-source shortest path on the mesh edge graph with edge length as weight.
O(V log V + E) per source.

```python
import heapq

def dijkstra(source, adj_dist, nverts):
    """adj_dist[vi] = (neighbor_indices_array, edge_lengths_array)"""
    dist = np.full(nverts, np.inf, dtype=np.float64)
    dist[source] = 0.0
    visited = np.zeros(nverts, dtype=bool)
    heap = [(0.0, source)]
    while heap:
        d, u = heapq.heappop(heap)
        if visited[u]:
            continue
        visited[u] = True
        nbrs, ndists = adj_dist[u]
        for k in range(len(nbrs)):
            v = nbrs[k]
            nd = d + ndists[k]
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist
```

**Performance**: ~0.6 seconds per source on 128K vertices (Python heapq + numpy
arrays). 66 seeds = 38.7 seconds total. Could be accelerated with scipy.sparse.csgraph.dijkstra
but was acceptable.

## 5. BFS Matching with Combined Scoring

For each matched pair (pv, nv), examine their graph neighbors. For each
unmatched positive neighbor pn, find the best-scoring unmatched negative
neighbor nn:

```python
# Combined score (lower = better match)
score = (spatial_weight * spatial_dist * 50 +
         geo_weight * min(geo_score, threshold) * 100 +
         norm_sym * 0.3 +
         deg_diff * 0.1 +
         curv_diff * 0.3)

# Where geo_score = average |geodesic_from_seed_pos[pn] - geodesic_from_seed_neg[nn]|
# across all seed pairs
```

**Pitfall discovered**: Multi-round BFS (re-queuing all matched vertices between
rounds with progressively relaxed thresholds) is WORSE than single-round BFS.
Single-round: 72.7%. Multi-round (4 rounds): 68.4%. The fragmentation of the
BFS flow prevents natural propagation — each round only sees new matches from
the previous round's queue, missing neighbors that could have been matched if
the entire matched set was re-queued in a single pass.

**Correct approach**: If doing multiple passes, re-queue ALL matched vertices
(not just newly matched ones) in a single pass, not across multiple separate
rounds. Better yet, just do a single BFS pass with the most permissive threshold
that doesn't produce false matches.

## 6. Laplacian Deformation (Unchanged from v24)

The Laplacian solver itself works perfectly — 0.1s solve, UV untouched,
constraints satisfied exactly (error 0.00000000). The problem is match quality,
not the solver. See `references/laplacian-symmetry-deformation.md` for the full
code pattern.

## Summary of What Was Learned

| Component | Status | Notes |
|-----------|--------|-------|
| Curvature computation | ✅ Works | 5s for 128K verts, range [0.004, 2.078] |
| Peak extraction | ✅ Works | 100-120 peaks per side, good spatial distribution |
| Seed matching (greedy 1:1) | ✅ Works | 66 unique pairs from 120 peaks |
| Dijkstra geodesic | ✅ Works | 0.6s/seed, 38.7s for 66 seeds |
| BFS with geodesic scoring | ⚠️ Marginal | 72.7% single-round, 68.4% multi-round |
| Laplacian deformation | ✅ Works | 0.1s solve, UV untouched |
| **Overall match rate** | ❌ ~71-73% | Cannot break ceiling on topology-asymmetric mesh |
