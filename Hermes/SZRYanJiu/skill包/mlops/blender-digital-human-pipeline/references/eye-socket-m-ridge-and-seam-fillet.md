# Eye Socket: M-Ridge Diagnosis, Inward Fillet, Weld-Collapse Lessons (v46j→v48)

2026-08-20/21 session. Supersedes the outward-chamfer fillet in `eye-socket-normals-and-fillet.md`
(that design CAUSES the M-ridge; kept only for history). Current pipeline: `SOCKET_VARIANT` switch
in `eye_socket_config.py`.

## 1. The "M-line" has TWO layers — diagnose separately

| Layer | What it is | Visible in | Fix |
|---|---|---|---|
| Topological seam | ring where two mesh patches meet (ring1) | wireframe | merge into one continuous ring sequence (v46i) |
| Geometric bulge ridge | convex ridge where chamfer rings expand outward then contract back | clay/shaded render ONLY | remove outward expansion (v47/v48) |

Fixing topology does NOT remove the ridge; wireframe renders cannot confirm ridge removal.
**Always verify seam/ridge quality with clay (untextured) renders**, and let the user judge in GUI —
wireframe + vision gave a false "M-line gone" pass here because the ridge was geometric, not topological.

## 2. Bulge-ridge root cause and fixes

Root cause: chamfer rings first expand outward by W past the rim, then the bowl contracts inward —
the max-expansion ring forms a circular convex ridge under lighting.

Three variants (config `SOCKET_VARIANT`):
- `no_chamfer` (v47): W=D=F=0, bowl shrinks+descends from rim in one
  smoothstep (16 rings). No outward section → no ridge possible. Face count lower & uniform
  (L 1428 / R 1258). Known blemish: slight pinch at inner eye corner (comes from rim contour
  curvature there, pre-existing, not introduced). User liked the ridge-free result but wanted
  the face↔socket seam smoothed.
- `chamfer_relax` (v47 alternate): keep 8 chamfer rings + Jacobi Laplacian relaxation on interior
  rings (ring0 + bowl pole locked, 8 passes λ=0.5). Works (ridges ground down, measured
  18.06→17.58mm max radius) but user preferred no_chamfer.
- `inward_fillet` (v48, **FINAL user-approved baseline 2026-08-21**): seam smoothing = fillet that
  ONLY moves inward+down (W=+1.2mm inward, D=0.6mm, F=4 rings, quintic zero-slope start →
  tangent-continuous with skin, no hard edge). Outward expansion is geometrically impossible →
  no M-ridge possible. Verified: seam smooth, no ridge, no internal ring lines, integrity all
  green (L 1764 / R 1554 faces). User: "效果满意, 暂时就按照这个做". Backup:
  `01_1_eye_socket_v48_final.blend`. Known residue: inner-corner crease (pre-existing rim
  contour curvature, accepted for now).

**Sign convention trap**: `rad_dirs` point TOWARD eye center, so in
`pos = base + rad_dirs * radial`, **positive W = inward**, negative W = outward (would recreate
the M-ridge). Confirmed by the chamfer self-check printout (positive "倒角宽度" = radius decrease).

## 3. Weld-collapse accident (remesh/weld thresholds vs ring spacing)

- `remove_doubles`/merge threshold MUST be smaller than the smallest normal vertex spacing.
  Bowl last-ring shrunk to 10% → radius ≈1.2mm, 84 verts → spacing 0.09mm < 0.1mm threshold →
  normal ring vertices welded together, pole fan collapsed 84→58 triangles.
- Fix: shrink bowl to 25% (spacing 0.22mm > threshold). Rule: `spacing = 2π·r_last/M`, verify
  against every weld threshold in the pipeline before choosing shrink ratio.
- Duplicate-vertex DETECTION must use KD-tree ≤0.01mm, not grid hashing (0.1mm grid falsely reports
  dense-ring neighbors as duplicates — the false report then tempts a destructive weld).
- Classify before welding: exact distance + connection direction (true dup ≈0.000mm random;
  adjacent ring verts ≈spacing, tangential). Rim-seam duplicates live at rim/chamfer outer edge
  (16-20mm radius); bowl-bottom "duplicates" are almost always false positives.

## 4. bmesh API traps

- After `bm.verts.new()`, **`v.index` is stale** until `bm.verts.ensure_lookup_table()`.
  Locking/mapping by index silently matched wrong verts → relaxation moved 0 vertices.
  Use object identity `id(v)` for lock sets/delta maps, or ensure_lookup_table first.
- Relaxation/smoothing loops MUST print per-pass moved-vertex counts and a before/after metric
  (e.g. max radius). Silent no-ops are invisible otherwise (caught only because "20.39→20.39mm"
  didn't change).

## 5. Integrity verification suite (check_integrity_local.py)

Run after every socket rebuild; all must pass:
1. Duplicate verts (KD-tree 0.01mm, attributed via `v44tag_<side>` face layer = new structure vs base mesh)
2. Loose verts = 0, degenerate faces = 0, non-manifold edges = 0
3. Boundary edges = 0 in the 30mm eye zone (rim fully stitched to skin)
4. Bowl pole fan intact: pole (radial <0.5mm, deepest) must connect exactly M triangles (L=84, R=74)

## 6. Verification rendering

- Wireframe render (`render_wireframe.py`): topology only.
- Clay render (`render_clay_eye.py`): ridge/seam quality. Both take `RENDER_TAG` env var for
  variant-tagged output (`RENDER_TAG=v48 ...`). Overexposed clay washes out subtle creases —
  when in doubt, deliver the .blend and let the user judge in GUI (this user verifies models
  personally and does not trust agent-render verdicts).
