# Adaptive Mesh Welding & Overlap Removal (2026-07-31)

## Adaptive `remove_doubles` Threshold

### Problem
Fixed threshold 0.00005 (0.05mm) was designed for ~1m-tall models. When the
user rescaled the Tripo model to 1.81m height, the same 0.05mm threshold left
**172,285 unwelded duplicate vertices**, which:
1. Caused xremesh to stall at 21% (preprocessing tries to stitch fragments)
2. Produced visible chest/face overlap in the repaired model

### Formula
```python
model_height = dims[2]  # Z dimension after rotation
adaptive_threshold = max(0.0001, model_height * 0.00006)
# 1.0m → 0.0001 (0.1mm floor)
# 1.7m → 0.000102 (0.102mm)
# 1.81m → 0.000109 (0.109mm)
```

### Tuning History
| Threshold | Model Height | Welded Verts | Non-manifold | Notes |
|-----------|:------------|:-------------|:------------:|-------|
| 0.00005 (old) | 0.976m | ~250 | 0-2 | Original, too small for big models |
| 0.00005 (old) | 1.81m | 254 | 7 | Insufficient — 172K remained unwelded |
| 0.00027 (0.27mm) | 1.81m | 181,212 | **59** | Too large — non-manifold > 50 threshold |
| **0.000109 (0.109mm)** | 1.81m | 254 | **3** | ✅ Correct — 0 non-manifold after repair |

### Where Applied
1. `repair.py` step [3]: initial remove_doubles
2. `repair.py` step [8]: final remove_doubles
3. `repair.py` `final_weld_for_qr()`: pre-QR welding
4. `02_qr_auto.py` step 2.5: pre-export welding before xremesh

All four locations use the same `max(0.0001, model_height * 0.00006)` formula.

## `remove_overlapping_faces()` — BVH Coplanar Face Removal

### Purpose
Remove faces that are coplanar, same-normal-direction, and very close together
(clothing-body overlap at seams).

### Algorithm
1. Build `BVHTree.FromBMesh(bm)` from the mesh
2. For each face (up to 500K, 120s timeout):
   - Get face center + normalized normal
   - `bvh.ray_cast(center + normal*0.0001, normal, 0.002)` — 2mm ray
   - If hit face exists and is different:
     - Check normal dot product > 0.95 (same direction, coplanar)
     - Delete the smaller-area face of the pair
3. Clean up loose vertices

### Results on Tripo 1.93M-face model
- Only **1 overlapping face** found (out of 500K scanned)
- The real chest overlap was caused by **unwelded vertices**, not true face-level overlap
- Most clothing-body overlap is **opposite-normal parallel layers** (clothing
  outside, body inside) — this function only detects **same-normal** overlaps

### Limitation
This function does NOT detect:
- Opposite-normal parallel layers (clothing on body) — those are structural
- Face pairs > 2mm apart
- Non-coplanar nearby faces

For the clothing-body overlap problem (structural, unfixable by post-processing),
see `blender-body-wrap/references/qr-overlap-test-results.md`.

## QR TargetQuadCount — Scale-Dependent Tuning

### Problem
QR's `adaptive_size` scales with model dimensions. A model resized from 0.98m
to 1.81m gets more faces for the same TargetQuadCount:

| TargetQuadCount | Model Height | Output Quads | Triangle Count | ≤300K? |
|:---------------:|:-----------:|:------------:|:--------------:|:------:|
| 150,000 | 0.976m | 149,010 | 298,004 | ✅ |
| 150,000 | 1.81m | 153,728 | 307,428 | ❌ |
| 140,000 | 1.81m | 146,114 | 292,198 | ✅ |
| 140,000 | 0.976m | 133,516 | 266,984 | ✅ |

### Rule
Always verify `quads*2+tris ≤ 300000` after QR. If over, reduce TargetQuadCount
by ~10K and retry. A single fixed TargetQuadCount does NOT work across model scales.
