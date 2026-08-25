# ZBrush Smart ReSymmetry & Blender Mirror Analysis

Session: 2026-07-14
Test model: Male_Body_Morphs_Lv2.obj (128,306 verts, 128,304 faces, 8192×8192 BMP texture)
Topology: NOT strictly symmetric (left=63127, right=63201, diff=13 verts)

## ZBrush Smart ReSym (Maxon official docs, 2026-07-08)

| Tool | Operates on | UV affected? | Polypaint affected? |
|------|------------|-------------|---------------------|
| SmartReSym | Vertex positions only | **No** | Yes (follows vertex) |
| ReSym | Vertex positions only | **No** | Yes |
| Mirror and Weld | Mirror+weld (topology changes) | **No** | Yes |
| Poseable Symmetry | Vertex positions only | **No** ("does not use UVs") | Yes |

ZBrush workflow for UV textures: Texture → Polypaint From Texture → ReSymmetry
(Polypaint correct) → re-UV → New From Polypaint.

## Blender bmesh Architecture

- `BMVert.co` (3D position) — stored per-vertex
- `BMLoopUV.uv` (UV) — stored per-loop (per face-vertex combination)
- These are **separate custom data layers** — modifying vert.co never touches UV
- Materials assigned per-face (`bm.faces[i].material_index`) — also untouched

## The texture misalignment non-issue

After mirroring only vert.co, the high-poly texture visually misaligns (UV
unchanged, vertex moved to symmetric position). **This is irrelevant for baking**:
baking (Selected to Active) casts rays from low-poly normals, hits high-poly
surface, samples color at that 3D position. High-poly UV layout does NOT
participate. Result: symmetric low-poly mesh + left/right independent texture.

## Test Results (128K vertex model)

### Method 1: bmesh + KDTree space matching
- Bidirectional nearest-neighbor (Y/Z), 3mm threshold
- Match rate: 73.6%
- UV diff: 0.000000000000000 ✅
- Result: ❌ Breaks faces (unmatched verts stay, neighbors move → tearing)

### Method 2: bmesh + BFS topology matching
- Seed from center-line vertex neighbors, BFS expand along edges
- Neighbor count + normal direction validation
- Match rate: 84.1% (seed=205, BFS expanded to 42,976)
- UV diff: 0.000000000000000 ✅
- Result: ❌ Breaks faces (20K unmatched verts tear at boundaries)

### Method 3: Blender symmetry_snap (built-in API)
- `bpy.ops.mesh.symmetry_snap(direction, threshold, factor, use_center)`
- Match: 50,157 pairs mirrored, 31,048 failed (79.5%)
- UV diff: 0.000000000000000 ✅
- Result: ❌ Breaks faces (31K failed verts tear when neighbors move)
- Note: factor=0.5 (average) vs factor=1.0 (one-sided) — same match count,
  factor=1.0 moves fewer verts (48,922 vs 97,256) but still tears
- Multi-round doesn't help (converges after 1 round)

### Method 4: Delete-half + Mirror Modifier + UV recovery
- Save positive-side (X>0) vertex UV mapping
- Delete negative-side verts (bmesh)
- Mirror Modifier + Apply (0.0s for 65K→129K verts)
- cKDTree batch query: match new verts to original positive verts by abs(X)
- foreach_set batch UV write (critical: per-loop write >3min timeout)
- Match rate: 99.8%
- UV: ⚠️ Right-side UV = left-side copy (not original right-side UV)
- Result: ✅ Perfect symmetry (diff 0.000000), no breaking
- Total time: 5 seconds

### Method 5: UV sphere (strict symmetric topology control)
- 482-vert UV sphere, topology perfectly symmetric
- Deform positive side (×1.3), bmesh mirror negative→positive
- Match rate: 100% (225/225)
- UV diff: 0.000000000000000 ✅
- Symmetry diff: 0.00000000 ✅
- Result: ✅ Perfect, no breaking

## Key Conclusions

1. **bmesh vert.co modification preserves UV perfectly** (0.000 diff, all tests)
2. **Topology matching is the challenge**, not UV preservation
3. **For strictly topology-symmetric models** (MetaHuman template): 100% match,
   perfect mirror, no breaking
4. **For topology-asymmetric models**: all in-place methods break faces.
   Use delete-half-mirror (UV becomes copy) or ZBrush Smart ReSym
5. **Blender symmetry_snap is not robust enough** for asymmetric topology
6. **Correct production workflow**: symmetrize high-poly first → wrap symmetric
   template → bake. Low-poly (MetaHuman) is naturally symmetric, no post-wrap
   symmetrization needed.

## BFS Algorithm Pseudocode (from ZBrush research doc)

```python
def generate_symmetry_map(mesh):
    sym_map = {}
    visited = set()
    seed_pairs = find_initial_boundary_pairs(mesh)
    queue = deque(seed_pairs)
    while queue:
        left_v, right_v = queue.popleft()
        left_neighbors = mesh.get_neighbors(left_v)
        right_neighbors = mesh.get_neighbors(right_v)
        for lv_next in left_neighbors:
            if lv_next in visited: continue
            rv_next = find_best_mirror_match(lv_next, right_neighbors)
            if rv_next and rv_next not in visited:
                sym_map[lv_next] = rv_next
                visited.add(lv_next)
                visited.add(rv_next)
                queue.append((lv_next, rv_next))
    return sym_map
```

Key: "find_best_mirror_match" uses spatial position after mirroring, NOT
topology index. Tolerance for topology mismatch (different neighbor counts)
is essential — skip pairs where degree difference > 3.

## Performance Notes

- 128K vertex model: Mirror Modifier apply = 0.0s
- cKDTree query (129K points) = <0.1s
- foreach_set UV write = <0.1s
- Per-loop UV write (for loop: uv_data[li].uv.x = ...) = >3 minutes (TIMEOUT)
- **Always use foreach_set("vector", flat_array) for UV batch operations**
