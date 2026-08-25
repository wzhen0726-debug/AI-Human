# Mirror Symmetry Test Results (Final — Session 2026-07-14/15)

## Test Model
`Male_Body_Morphs_Lv2.obj` — 128,306 vertices, topology-asymmetric (L/R differ by 13 verts, 0% index symmetry, one side with sculpting deformation). ZBrush Smart ReSym: 10s perfect symmetry (user-confirmed).

## All Approaches Tested (vert.co only, UV never touched — diff = 0.000000000000000 in ALL cases)

| # | Approach | Match | Time | Broken | Notes |
|---|----------|-------|------|--------|-------|
| 1 | Spatial cKDTree bidirectional + normals | 71.4% | 0.5s | Yes | — |
| 2 | BFS from center-axis seeds | 6-68% | 0.3s | Yes | Seeds too few (144-205) |
| 3 | Global bidirectional + BFS correction | 71.4% | 0.8s | Yes | — |
| 4 | Curvature + Dijkstra geodesic + BFS | 72.7% | 34s | Yes | Geodesic didn't help |
| 5 | Hungarian assignment (block-wise) | 62.2% | 45s | Yes | Blocks broke global match |
| 6 | Laplacian deformation (71% constraints) | 71.4% | 0.6s | Local stretch | No tears, but wrong matches amplified |
| 7 | Topological BFS local-neighbor | 74.4% | 1.5s | Yes | Best raw match rate |
| 8 | BFS local + Laplacian | 74.4% | 1.8s | Yes | — |
| 9 | Delete-half mirror + full UV restore | 100% | 5s | No | But neg UV = pos copy |
| 10 | Delete-half + neg UV restore (upgraded) | 100% | 5s | No | 65.9% neg UV independent |

## Match Rate Ceiling: 74.4%
No approach exceeds this in Python. Remaining ~28% unmatched verts cause tears or stretch.

## Why ZBrush Wins
C++ multi-scale graph matching (not spatial KDTree), handles topology asymmetry natively.

## Proven Reliable Conclusions
1. bmesh vert.co mod NEVER touches UV — all tests 0.000000000000000
2. Strictly symmetric topology → 100% bmesh mirror (sphere verified)
3. Baking is pure spatial — high-poly UV irrelevant to bake result
4. Correct workflow: symmetrize high-poly → wrap low-poly → UV → bake
5. For Blender-only: upgraded delete-half mirror (65.9% neg UV preserved)
6. For production: ZBrush Smart ReSym → import to Blender
