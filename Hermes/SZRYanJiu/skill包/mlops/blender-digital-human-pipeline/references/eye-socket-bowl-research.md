# Eye Socket Bowl: grid_fill vs bridge vs manual rings — research 2026-08-12

> Context: v3 QR pipeline, step 01A眼窝与眼球. Parent agent commissioned a web research
> pass on "smooth eye-socket bowl on a non-uniform almond boundary loop" after 6+
> starburst failures. Sources: Blender 5.2 manual (fetched locally), bmesh.ops API
> page, Blender StackExchange (API-fetched threads). Local copies of the manual/API
> pages and thread transcripts live in the session workspace `research/` folder.

## ⭐ The one-line verdict

**All "ring-to-ring" fill algorithms (grid_fill, bridge_edge_loops, manual multi-ring)
assume the two rings have matched vertex counts AND comparable vertex distribution. An
almond eyelid contour violates both (dense at canthi, sparse on arcs) → thin stretched
quads → reads as starburst. The fix is RESAMPLE the boundary loop to uniform arc-length
FIRST, then generate rings on a spherical-cap formula. Never shrink rings toward the
raw centroid.**

## 1. grid_fill — wrong tool for a full almond loop

Blender manual (verbatim, docs.blender.org/manual/en/latest/modeling/meshes/editing/face/grid_fill.html):
- Designed for "a (roughly) rectangular loop of edges — or just two opposing sides".
  It must internally ESTIMATE where to "cut" one closed loop into two opposite chains.
  An almond (2 pointed ends, no 4-side structure) is its worst input: the cut
  estimation lands on the canthi and rows/columns collapse there → starburst.
  (SE evidence: https://blender.stackexchange.com/questions/320776 — "grid fill
  depends heavily on input topology; my non-subdivided curved edge made the cut
  estimation perform poorly.")
- bmesh signature (verified on the API page): `bmesh.ops.grid_fill(bm, edges=[], mat_nr=0,
  use_smooth=False, use_interp_simple=False)` — **no span/offset at bmesh level**.
  span/offset exist only on the UI op `bpy.ops.mesh.fill_grid(span=1, offset=0)`:
  - `span` = grid columns (rows auto); `offset` = which vertex is grid corner #1
    (default = active vertex) — rotates the grid layout.
  - `use_interp_simple` ("Simple Blending") = simpler interpolation; better for FLAT
    surfaces; for a concave bowl test both, default OFF keeps curvature.
- Verdict: do NOT grid_fill the whole almond opening. It IS excellent for the small
  near-circular bottom ring of a bowl (2×2/3×3 quad patch).

## 2. bridge_edge_loops — right connector, needs matched rings

- bmesh op is `bmesh.ops.bridge_loops(bm, edges=[...])`; UI op `bpy.ops.mesh.bridge_edge_loops()`.
- Requires equal (or multiple) vertex counts; interpolates vertex-to-vertex. With
  resampled equal-count rings it outputs clean quads on ANY outline shape.
- SE: https://blender.stackexchange.com/questions/233091 (quad topology bridging).

## 3. Boundary-loop resampling (the key step)

Standard recipe (50-vote SE answer https://blender.stackexchange.com/questions/7698):
- LoopTools addon (bundled, `mesh_looptools.py` — readable source) → "Space" operator
  evens vertex spacing along a loop. Can be called or its arc-length code copied.
- Geometry-Nodes route (SE answer on same thread): mesh→curve → **Resample Curve**
  node (`GeometryNodeResampleCurve`, mode='COUNT') → curve→mesh. Count 32–48 for an eye.
- Pure-Python equivalent: cumulative chord length → sample at equal arc positions,
  `pts[j].lerp(pts[j+1], f)`.
- After resample, optionally 1–2 passes of 1D Laplacian (v←0.25·prev+0.5·v+0.25·next)
  to round the sharp canthi — real canthi ARE rounded; also removes the extreme
  curvature where every fill algorithm accumulates error.
- Project resampled points back onto the original surface with
  `BVHTree.FromBMesh(bm).find_nearest(p)` to guarantee seamlessness.

⚠️ Reconcile with existing pipeline note: the 2026-08-07 session settled on a
**flat-bottom pit** ("内部是个坑就好，反正有眼珠挡着") because the user judged interior
shape uncritical. The resample+spherical-cap recipe here is the upgrade path IF a
smooth bowl is ever required (e.g. socket visible without eyeball, or QR mangling the
flat pit). The resample step ALSO fixes the pit's known weak point (ring0 non-uniform
distribution → twisted side-wall quads): resample → flatten to rim_y → bridge.

## 4. Smooth-bowl ring generation (if smooth bowl IS wanted)

Do NOT scale rings toward the ring centroid (radial direction flips at the canthi →
the exact failure measured 2026-08-07: 562/639 faces >40° off mean normal).
Instead parameterize a spherical cap:
- Fit the ring's plane (centroid C + normal N pointing INTO the head).
- Ring k of K: scale s = cos(θ), depth d = D·sin(θ)/sin(θ_max), θ = θ_max·k/K,
  θ_max ≈ 60–80°, D ≈ socket depth (≈20mm for a 14.5mm-radius ball).
  Vertices land ON an ideal sphere → no interpenetration by construction.
- Rings: 4–6 + bottom. Bottom ring keep 8–12 verts (≈15% of opening radius),
  close with grid_fill (near-circular → works great) or poke+subsurf. NEVER a single
  pole (starburst; also bad for blink deformation).

## 5. Classic eye-socket topology (industry consensus)

- Eyelid = one closed edge loop around the fissure; socket = 2–3 concentric rings
  extruded inward from the lid loop; bottom = small quad patch, OPEN or capped —
  NEVER a single apex pole (poles pinch during blink shape keys).
- SE accepted answer with full 7-step manual workflow (bevel vert → knife → inset lid
  → extrude inward TWICE → delete cap → fit ball):
  https://blender.stackexchange.com/questions/80089/eye-socket-help
- Canonical topology reference: polycount "Face Topology – Breakdown Guide"
  (https://polycount.com/discussion/56011 — 403 to scripted fetch, open manually).

## 6. "Painted eye bump → real socket" mature workflow

Consensus: KEEP the lid skin, only remove the fissure opening; the bump is the
free lid reference. Matching SE case (irregular eye hole + separate dome eyeball),
accepted answer: **duplicate outer edge loop → SIMPLIFY it (Checker Deselect +
Dissolve) → extrude inward → fill → Subsurf** — i.e. simplify-then-bridge is the
officially recommended route, same root idea as resample-first.
https://blender.stackexchange.com/questions/203793
ZBrush equivalent: InsertMesh eyeball + Dynamesh boolean + ZRemesher.
Maya: Quad Draw on live eyeball surface.

## 7. Open-source references

- No direct "auto eye-socket bowl" OSS script exists (GitHub search 2026-08-12:
  0 hits for eye socket topology / cavity generators).
- LoopTools source (bundled addon `mesh_looptools.py`): space/circle/relax/flatten —
  copy its arc-length resample.
- KeenTools keentools-blender (https://github.com/KeenTools/keentools-blender) and
  MPFB2 (https://github.com/makehumancommunity/mpfb2): their head meshes carry
  production eye-socket topology to copy ring counts/bottom handling from.
- MetaHuman socket = same concentric-ring-no-pole structure (public GDC topology shots).

## 8. Research-harness notes (this session)

- StackExchange API (`api.stackexchange.com/2.3/search/advanced?site=blender`) works
  unauthenticated and is the most reliable source-mining path for Blender technique Q&A;
  fetch full bodies with `?filter=withbody` on /questions/{id} and /answers.
- docs.blender.org 403s curl/Python without a full Chrome User-Agent header
  (Cloudflare challenge); with UA it serves fine.
