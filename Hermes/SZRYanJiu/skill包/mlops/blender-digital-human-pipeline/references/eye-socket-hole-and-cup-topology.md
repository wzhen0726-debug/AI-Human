# Eye Socket Hole + Cup: Verified Topology Recipe (2026-08-07)

Hard-won recipe for cutting eye socket openings in a closed head mesh and sealing them with concave cups that are **topologically clean** (0 open edges, 0 non-manifold, all normals outward). Verified end-to-end ALL_PASS (12/12 quantitative checks). Full history: `方案md记录/v3_QuadRemesher/01A眼窝与眼球/眼窝破面根治记录.md`.

## Final working recipe (order matters)

1. **Delete faces by BFS flood-fill, not per-face centroid test.**
   Testing "face centroid inside eyelid contour AND y < y_cut" per-face leaves disconnected islands (observed: 5 separate open rings / 45 open edges). Flood-fill from a seed face through neighbors that pass the test → the deleted region is guaranteed one connected patch with one boundary ring.

2. **Seed = face closest to eye center by FULL 3D distance.**
   XZ-nearest picks the back-of-skull face (a closed head has front/back layers at the same x/z) — flood then deletes 1 face and punches a hole in the rear of the skull.

3. **Walk the boundary ring in TOPOLOGICAL order — never sort by atan2 angle.**
   Build open-edge adjacency and walk the longest closed loop. Angle-sorting scrambles adjacency: quads between ring and inner rings use crossing edges that don't share the original boundary edges → those boundary edges dangle as open edges (starburst + jagged rim). This was the #1 root cause of "broken faces".

4. **Relax ring0 (3× Laplace: v = 0.5v + 0.25(prev+next)).**
   Removes rim zigzag/spikes. Safe: ring verts are shared with the skin, so moving them smooths the hole edge too. This eliminated the persistent 0.3mm sliver non-manifold edge.

5. **Cup = concentric rings shrunk radially in SAME order + shared-pole triangle fan.**
   8 rings, spherical profile (scale=cos, depth=sin). Inner-ring vertex i sits at exactly ring0[i]'s angle (no resampling) → quads can't cross. Bottom sealed with ONE shared pole vertex + fan — every edge has exactly 2 faces → manifold by construction.

6. **Never weld ring0 or cup verts with remove_doubles.**
   Welding merged ring0 into the skin: non-manifold went 0 → 10. ring0 already shares skin verts; welding only breaks things.

7. **Dissolve slivers (<0.5mm² faces) in two passes, strictly interior only.**
   Pass 1 after hole-cut: interior slivers (all their edges have exactly 2 faces). Pass 2 after cup sealing: rim slivers that became interior once sealed. Never dissolve faces touching the boundary ring (opens holes).

8. **Call `bm.normal_update()` before reading `f.normal` after any edit.**
   `update_edit_mesh` leaves STALE normals. Filtering by `f.normal.y > 0` to flip inward faces silently skips truly-flipped slivers (observed 3 escapees).

9. **Normal-flip criterion: eyelid polygon OR socket zone.**
   Some rim slivers sit inside the socket zone but OUTSIDE the eyelid polygon. Use polygon OR (xz-dist to eye center < 22mm AND y within cup depth band).

## Verification (quantitative, not vision)

Per eye, assert: open edges in zone == 0, non-manifold edges == 0, degenerate faces == 0, cup concave (bottom y > rim y by ≥8mm), zero cup faces with normal.y > +0.3. Vision is unreliable for concavity — one render was judged "convex" because the measurement zone accidentally included the back-of-skull wall. Filter measurement zones TIGHTLY (cup zone = 14mm xz radius around eye center + depth band).

## Dead ends (do not retry)

- **ngon bottom seal** → triangulation slivers + open edge + non-manifold edges.
- **pointmerge last ring** → overlapping faces at cup bottom → non-manifold.
- **remove_doubles on cup verts** → 10 non-manifold edges.
- **Uniform-angle resampling of inner rings** → quad twist; inner rings must keep exact ring0[i] correspondence.
- **Global normals recalc (Shift+N equivalent)** on a mesh with holes → nondeterministic propagation flips faces across hole edges. Local per-face flips only.
