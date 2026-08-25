# Mirror Symmetry: 10 Approaches Tested (2026-07-14/15)

## Test Model
`Male_Body_Morphs_Lv2.obj` (128,306 verts, 128,304 faces, 8192×8192 texture). Topology-asymmetric: left/right differ by 13 verts, 0% index symmetry. ZBrush Smart ReSym handles perfectly in ~10s.

## Results Summary

| # | Approach | Match Rate | Symmetry | Broken Faces | UV Independent | Time |
|---|----------|-----------|----------|--------------|----------------|------|
| 1 | Spatial nearest-neighbor | 98.3% | ❌ | ❌ | ✅ | 0.4s |
| 2 | Bidirectional+normal+degree | 64% | ❌ | ❌ | ✅ | 0.5s |
| 3 | Topology BFS (center-axis seeds) | 6-68% | ❌ | ❌ | ✅ | 0.3s |
| 4 | Global bidirectional+BFS | 71.4% | ❌ | ❌ | ✅ | 0.8s |
| 5 | Blender symmetry_snap | 39% | ❌ | ❌ | ✅ | 0.3s |
| 6 | Delete-half+mirror+UV restore | 99.8% | ✅ | ✅ | ❌(copy) | 5s |
| 7 | Laplacian deformation (71% constrained) | 71.4% | ⚠️ | Local stretch | ✅ | 0.6s |
| 8 | Curvature+geodesic+Laplacian | 72.7% | ❌ | ❌ | ✅ | 34s |
| 9 | Hungarian assignment+Laplacian | 62.2% | ❌ | ❌ | ✅ | 45s |
| **10** | **Upgraded delete-half+neg UV restore** | **100%** | **✅** | **✅** | **✅(65.9%)** | **5s** |

## Approach 10: Upgraded Delete-Half-Mirror with Negative UV Restoration (WINNER)

**Principle** (from Gemini consultation):
1. Save BOTH positive and negative original UV maps before deletion
2. Delete negative side, Mirror Modifier
3. Positive new vertices → match original positive → restore positive UV
4. Negative new vertices → match ORIGINAL NEGATIVE vertices (by abs(X)+Y+Z) → restore negative UV
5. Unmatched negative vertices → fall back to positive UV

**Result**: Perfect symmetry (diff 0.00000000), no broken faces, 65.9% negative UV from original negative side, 34.1% fallback to positive UV. Left/right UV independent (positive [0.705,0.144] vs negative [0.612,0.971]).

**Why 34% fallback**: Original negative side had sculpting deformation (different Y/Z from positive). After mirror, negative vertices are at positive Y/Z positions — can't match deformed negative counterparts. For baking pipeline, high-poly UV doesn't matter (baking is pure spatial operation).

**Key difference from v6**: v6 used positive UV for ALL negative vertices (100% copy). v10 preserves 65.9% of original negative UV.

## Verified Core Conclusions
1. bmesh vert.co and UV layer are independent — modifying vert.co never touches UV (0.000000000000000 diff in all tests)
2. Topology-symmetric models achieve 100% perfect mirror (sphere test verified)
3. Laplacian deformation works (128K vertex sparse matrix solve in 0.1s, constraint error 0)
4. Baking is pure spatial operation independent of high-poly UV
5. Correct flow: symmetrize high-poly → wrap symmetric low-poly → UV unwrap → bake
6. **71% match ceiling is fundamental** — spatial, geodesic, curvature, Hungarian all cap at 62-73%
7. **ZBrush Smart ReSym handles same model perfectly in 10s** — Blender Python cannot replicate
8. **Partial matching is NEVER safe** — every unmatched vertex creates a tear point
9. **Nearest-vertex interpolation for unmatched vertices is CATASTROPHIC** — crosses body parts
10. **Blender 5.1 foreach_get/foreach_set UV API**: use `"vector"` not `"x"`/`"y"` (AttributeError)

## Practical Recommendations
- For topology-asymmetric high-poly: symmetrize in ZBrush (Smart ReSym) before importing to Blender
- For topology-symmetric low-poly (MetaHuman template): use bmesh direct vertex mirror (100% success)
- For distributable toolkit: use approach 10 (delete-half + negative UV restoration)