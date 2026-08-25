# Pinch Repair A/B Testing Results

Session: 2026-07-08
Model: glm-5.2 (main) + gemini-3.5-flash (vision)

## Problem Definition

User reported visible "pinch" artifacts at nose bridge and nose tip in
Blender — two red arrows pointing to vertices where the mesh pinches
together. Diagnostic found:

- **Nose bridge vertex #4031**: neighbor distances [0.1, 0.7, 9.7, 10.4]mm
  — two neighbors collapsed to 0.1mm while others are 10mm apart
- **Nose tip vertex #7702**: neighbor distances [7.0, 7.3, 8.8, 8.8]mm
  — relatively uniform (not actually pinch, just visually odd from angle)

Root cause: Shrinkwrap NEAREST_SURFACEPOINT projects adjacent template
vertices to the same scan surface point at high-curvature regions.

## A/B Test Matrix

| Version | Technique | Nose bridge (mm) | Mean (mm) | <1mm% | Self-int | Verdict |
|---------|-----------|:-----------------:|:---------:|:-----:|:--------:|---------|
| v3.4 | (baseline, no pinch fix) | 0.1/0.7 | 0.402 | 96.2 | 362 | Pinch visible ❌ |
| v3.5 | Spring anchors (α→0.8) | 0.2/0.3 | 0.402 | 96.2 | 365 | Anchors not the cause |
| v3.6 | + Edge equalization (5r) | 0.9/1.3 | 0.403 | 96.1 | 421 | SW2 re-collapses |
| v3.7 | + Edge equalization (10r, 0.5 thresh) | 0.5/0.6 | 0.409 | 96.0 | 497 | Same issue |
| v3.9 | Selective Taubin (5r, face only) | 0.2/0.3 | 0.451 | 93.0 | 428 | No improvement |
| v3.10 | Selective Taubin (3r, face only) | 0.2/0.3 | 0.404 | 95.6 | 497 | Same |
| v3.11 | No SW2 + global Taubin (10r) | 2.6/4.2 | 1.362 | 53.3 | 104 | Pinch gone but accuracy destroyed |
| v3.12 | No SW2 + Taubin + PROJECT reproject | 8.1/8.2 | 0.724 | 84.5 | 1340 | PROJECT causes SI explosion |
| v3.13 | No SW2 + Taubin + find_nearest reproject | 0.3/0.5 | 0.519 | 93.8 | 375 | find_nearest re-collapses |
| v3.14 | Iterative loop (reproject→Taubin ×2) | 2.1/4.2 | 0.536 | 93.0 | 391 | Loop doesn't converge |
| v3.15 | SW2 + selective Taubin + single push (0.2mm) | 0.3/0.6 | 0.404 | 95.6 | 500 | Threshold too low |
| v3.16 | SW2 + selective Taubin + single push (0.5mm) | 0.3/0.5 | 0.407 | 95.4 | 487 | Single push ineffective |
| v3.17 | SW2 + single push (toward avg) | 0.1/0.8 | 0.405 | 95.5 | 547 | Push toward each other |
| v3.18 | SW2 + single push (away from neighbor) | 0.1/0.7 | 0.404 | 95.6 | 525 | Same — both in pinch set |
| v3.19 | SW2 + paired push (post-SI repair) | 3.2/4.1 | 0.411 | 95.3 | 762 | **Pinch fixed!** ✅ |
| v3.20 | SW2 + 2-round paired push | 8.1/8.2 | 0.415 | 95.2 | 856 | **Best pinch fix** ✅ |

## Key Lessons

1. **SW2 is needed for accuracy** but creates pinch. Cannot skip it.
2. **find_nearest ALWAYS re-collapses pinch** — any reprojection after
   push-apart undoes the fix. Pinch repair must be the LAST step.
3. **Single-vertex push fails** — both collapsed vertices are in the
   pinch set; pushing one toward "average" pulls it toward the other.
4. **Paired symmetric push works** — move both vertices apart by equal
   distance along the edge direction.
5. **2 rounds needed** — first round fixes ~295 pairs, second round
   catches ~252 residual pairs created by the first round's displacement.
6. **Self-intersection increases** — push-apart folds faces in concave
   regions. This is an inherent tradeoff with pinch repair.
7. **Taubin smoothing helps marginally** but cannot fix collapsed pairs
   alone — the two collapsed vertices are mutual neighbors, so averaging
   their neighbor positions (which include each other) keeps them together.
8. **Spring-weight anchors** (α→0.8, 0.3× smooth weight) are good practice
   but do NOT fix pinch — pinch is caused by Shrinkwrap, not anchoring.
