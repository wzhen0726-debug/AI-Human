# Local Geometry Anomaly Repair — Diagnose Before Fix

> Date: 2026-08-03
> Hard-won lesson: NEVER blindly smooth/push local geometry anomalies without first comparing against the raw model.

## Symptom

User reports a "hole" or "bump" in the chest/belly area of the repaired high-poly model. Multiple rounds of smoothing, pushing, and sculpting made it WORSE — created symmetric double pits on both pectoral muscles.

## Root Cause

The "anomalies" were **original model features**, not repair-introduced defects. The repair pipeline's local smoothing/pushing operations moved vertices away from their original positions, creating NEW deformations.

Specific technical bug: the "ring reference surface" for local pushing used **XZ-plane distance** (`sqrt((x-cx)² + (z-cz)²)`) to find reference vertices. This caused left and right pectoral muscles to project onto overlapping regions in the XZ plane — the left chest's reference ring included right chest vertices and vice versa, polluting the reference surface and pulling normal geometry into pits.

## Correct Approach

1. **Diagnose first**: Load the raw model alongside the repaired model. Compare vertex positions in the suspect region. If deviation from raw is <1mm, the anomaly is original geometry — do NOT "fix" it.
2. **Only fix actual deviations**: If a vertex deviates >1mm from its raw position, push it back to the raw position.
3. **Reference ring must use 3D Euclidean distance**: `sqrt((x-cx)² + (y-cy)² + (z-cz)²)`, not XZ-plane distance. This prevents left/right overlap in the reference ring.
4. **Small steps, verify after each**: Push strength ≤0.5, iterations ≤5, then verify deviation from raw before continuing.

## What NOT to Do

| Bad Approach | Why It Fails |
|-------------|-------------|
| Global Laplacian smooth | Moves ALL vertices, destroys original detail |
| Taubin smooth | Same problem — global operation |
| Sculpt smooth (bmesh Laplacian) | Cannot distinguish original features from defects |
| XZ-plane ring reference | Left/right projection overlap pollutes reference |
| Blind push to "average" | "Average" surface is not the correct surface |

## Inward-Facing Normals — The Real Visual "Hole"

The visual "hole" or "dent" the user sees is often **inward-facing normals**, not a geometric hole. Detection:

```python
center = Vector((0, 0, target_z))
inward = [f for f in bm.faces
    if f.normal.dot(f.calc_center_median() - center) < 0]
```

Fix: flip those faces' normals. This is a **local, safe operation** that doesn't move vertices.

## Pipeline Integration

- `repair.py` should do ONLY: rotation correction, remove_doubles weld, non-manifold fix, overlap removal
- NO Laplacian smooth, NO Taubin, NO sculpt_smooth_chest
- Adhesion repair (`adhesion.py`) handles clothing-body junctions separately
- Any local anomaly requires user confirmation of location BEFORE attempting fix

## Verification

After any local fix, compare against raw model:
```python
# Load raw, rotate to same orientation
# For each vertex in suspect region:
dist = (v.co - kd.find(v.co)[0]).length
# If dist > 1mm: deviation introduced by repair
```
