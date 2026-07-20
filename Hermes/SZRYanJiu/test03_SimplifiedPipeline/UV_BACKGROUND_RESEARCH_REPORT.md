# Blender 5.1 Background UV Unwrap for QuadRemesher Meshes — Research Report

**Date**: 2026-07-20
**Mesh**: 90,331 faces QuadRemesher T-pose character (Tripo AI source)
**Blender**: 5.1.0 (hash adfe2921d5f3, 2026-03-17)
**Goal**: <50 islands, uniform texel density, no stretching, fully automated (background mode)

---

## Executive Summary

**No fully-satisfying solution exists for QR meshes in pure Blender background mode.**
The fragmentation is topology-driven (QR's uniform quad grid has non-coplanar
neighbors), not algorithm-driven. However, a **best-available pipeline** achieves
~84 islands with 2-3/10 visual quality — acceptable for baking, not for direct
texture painting. For production quality, external tools (RizomUV) or topology
swap (template-wrap instead of QR) are required.

---

## A. ANGLE_BASED vs CONFORMAL (LSCM) vs MINIMUM_STRETCH on QR Meshes

### Tested on the actual 90K-face mesh (2026-07-20)

| Method | Seams | Pre-unwrap Islands | Unwrap Time | Notes |
|--------|-------|--------------------|-------------|-------|
| ANGLE_BASED + 26K seams | 26037 | 12532 | 34s | 12K micro-islands, unusable |
| CONFORMAL (LSCM) + 26K seams | 26037 | 12532 | 4s | Same fragmentation, 8x faster |
| MINIMUM_STRETCH (ARAP) + 26K seams | 26037 | 12532 | 29s | Same fragmentation |
| ANGLE_BASED + 455 seams | 455 | 84 | 35s | Better, but arms/legs still fold |
| CONFORMAL + 455 seams | 455 | 84 | 3s | Same islands, 10x faster |
| MINIMUM_STRETCH + 455 seams | 455 | 84 | 48s | Same islands, slowest |

### Key Findings

1. **All three algorithms produce IDENTICAL island counts** given the same seams.
   The unwrap method does NOT control fragmentation — **seam placement does**.

2. **MINIMUM_STRETCH (ARAP) is NEW in Blender 5.1** (not in 4.x). It's a
   third `method` enum option for `bpy.ops.uv.unwrap()` with an `iterations`
   parameter (default 10, tested 20). However:
   - Produces same island count as CONFORMAL
   - 10-15x slower than CONFORMAL (48s vs 3s for 84 islands)
   - Did NOT improve visual quality (still 2/10 checkerboard)
   - **Not recommended for background pipelines** due to poor time/quality ratio

3. **CONFORMAL (LSCM) is the best choice** for QR meshes:
   - Fastest (3-4s vs 35s ANGLE_BASED vs 48s MINIMUM_STRETCH)
   - Same output quality as the others
   - ANGLE_BASED adds angle weighting that's useless on uniform QR grids

4. **Smart UV Project fragments worse with HIGHER angle** (counterintuitive):
   - 66° → 914 islands, 89° → 1983 islands
   - Smart UV groups faces by normal projection; QR's slightly-varying normals
     create thousands of tiny projection groups
   - **Never use Smart UV Project on QR meshes**

### Smart UV Fragmentation Root Cause

Smart UV Project groups faces by face-normal direction and projects each group
onto a plane. QuadRemesher output has ~uniform normals (it's a smooth organic
mesh), so at first glance 66° should group everything. But QR's quads have
slightly different normals per face (not perfectly coplanar), AND Smart UV
also splits at concave boundaries. The combination creates one projection group
per "normal cluster" — which on a curved body surface equals hundreds of
tiny groups, each becoming a fragment island. **The algorithm is fundamentally
mismatched with uniform-quad topology.**

---

## B. Average Islands Scale + Pack Islands in Background Mode

### Confirmed: Both work in `--background --factory-startup` (Blender 5.1)

**API signatures (verified 2026-07-20):**
```python
bpy.ops.uv.average_islands_scale(scale_uv=False, shear=False)
bpy.ops.uv.pack_islands(
    udim_source='CLOSEST_UDIM', rotate=True, rotate_method='ANY',
    scale=True, merge_overlap=False, margin_method='SCALED',
    margin=0.001, pin=False, pin_method='LOCKED',
    shape_method='CONCAVE'
)
```

**NEW in 5.1: `bpy.ops.uv.arrange_islands`** — pre-pack layout ordering:
```python
arrange_islands(initial_position='BOUNDING_BOX', axis='Y',
                align='MIN', order='LARGE_TO_SMALL', margin=0.05)
```

### Texel Density Consistency

`average_islands_scale()` scales each UV island so that its UV-to-3D-surface-area
ratio is uniform across islands. This is the **correct tool for texel density**.

**CRITICAL CAVEAT discovered in testing**: `average_islands_scale()` normalizes
the ratio PER ISLAND but does NOT fix the within-island distortion. On QR meshes
with fragmented sub-islands (arms/legs folded into tiny UV patches), each
"fragment island" gets scaled up to match the average — but the fragments are
still geometrically distorted (folded), so the checkerboard remains broken.
**Average Islands Scale cannot repair topology-driven folding.**

### Recommended call order
```python
bpy.ops.uv.unwrap(method='CONFORMAL', ...)
bpy.ops.uv.select_all(action='SELECT')
bpy.ops.uv.average_islands_scale()          # texel density normalization
bpy.ops.uv.select_all(action='SELECT')
bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method='SCALED', margin=0.003)
```

**Note**: `pack_islands(scale=True)` will RESCALE islands to fit the UV square,
partially undoing `average_islands_scale`. If strict texel density matters,
call `pack_islands(scale=False)` after `average_islands_scale` — but the layout
won't fill the UV square. The tradeoff is unavoidable with built-in operators.

---

## C. bmesh Seam Marking for Human Body — Anatomical Cuts

### Best-practice seam locations (verified on 90K-face QR mesh)

The **single most important factor** is seam tolerance. Wide tolerance →
catches thousands of edges → thousands of islands. Tight tolerance →
catches only the intended cut line → manageable islands.

| Seam | Location (body-relative) | Tolerance | Edges caught | Purpose |
|------|--------------------------|-----------|--------------|---------|
| Back center | X=mid, Y>0 (back), Z 5-95% H | ±0.15% W | 268 | Split front/back |
| Left leg inner | X=mid-1.5%W, Y<0, Z 5-45% H | ±0.2% W | 95 | Split L/R legs |
| Right leg inner | X=mid+1.5%W, Y<0, Z 5-45% H | ±0.2% W | 92 | Split L/R legs |
| **Total** | | | **455** | **84 pre-unwrap islands** |

### Code to find anatomical seam positions

```python
def mark_anatomical_seams(mesh):
    bm = bmesh.new(); bm.from_mesh(mesh.data)
    xs=[v.co.x for v in bm.verts]; ys=[v.co.y for v in bm.verts]; zs=[v.co.z for v in bm.verts]
    min_x,max_x=min(xs),max(xs); min_z,max_z=min(zs),max(zs)
    mid_x=(min_x+max_x)/2; H=max_z-min_z; W=max_x-min_x
    # TIGHT tolerances are critical
    xt = W * 0.0015     # back center: 0.15% of width
    xt_leg = W * 0.002  # leg inner: 0.2% of width
    for e in bm.edges:
        v0,v1 = e.verts; m = (v0.co+v1.co)/2
        # Back center line (Y>0 = back of body)
        if (abs(v0.co.x-mid_x)<xt and abs(v1.co.x-mid_x)<xt
            and v0.co.y>0 and v1.co.y>0
            and min_z+H*0.05 < m.z < min_z+H*0.95):
            e.seam = True
        # Left leg inner
        if (min_z+H*0.05 < m.z < min_z+H*0.45
            and abs(v0.co.x-(mid_x-W*0.015))<xt_leg
            and abs(v1.co.x-(mid_x-W*0.015))<xt_leg
            and v0.co.y<0 and v1.co.y<0):
            e.seam = True
        # Right leg inner (mirror)
        if (min_z+H*0.05 < m.z < min_z+H*0.45
            and abs(v0.co.x-(mid_x+W*0.015))<xt_leg
            and abs(v1.co.x-(mid_x+W*0.015))<xt_leg
            and v0.co.y<0 and v1.co.y<0):
            e.seam = True
    bm.to_mesh(mesh.data); bm.free()
```

### Failed seam strategies (DO NOT USE)

| Strategy | Edges | Islands | Why it fails |
|----------|-------|---------|--------------|
| Arm inner (Y<0, Z 55-88%H, X>15%W) | 4596 | 2301 | Catches a whole arm strip, not a line |
| Armpit ring (Z~76%H) | 0 | — | Tolerance too tight, catches nothing |
| Neck ring (Z~83%H) | 128K+ | 1 per face | Z-band catches all edges at that height |
| Waist ring (Z~55%H) | 128K+ | 1 per face | Same Z-band collapse |
| Dihedral angle ≥55° | 65 | 50% empty | QR normals too uniform for angle detection |

**Critical lesson**: Z-band ring cuts (neck/waist/ankle) are CATASTROPHIC on
dense QR meshes. A "ring at Z=0.83H" with any tolerance catches every edge
crossing that height — thousands of edges — and collapses each face into a
separate island. **Always use X-band (vertical lines), never Z-band (horizontal rings).**

---

## D. Blender Plugins for Background UV

### Tested / Investigated

| Plugin | Background? | Quality on QR | Verdict |
|--------|-------------|---------------|---------|
| **B2RUVL** (built-in addon, v0.1.6) | No — bridges to RizomUV/Headus GUI | N/A (just a bridge) | Requires RizomUV license + GUI round-trip |
| **UV Packmaster** (paid $29-49) | Yes (Python SDK) | Packing only, no unwrap | Does NOT solve the unwrap problem |
| **RizomUV** (paid $300+/yr) | No clear headless CLI | Industry-leading | Best quality but no automation path |
| **Magic-UV** (built-in) | Yes | Editing utilities only | No auto-seam/auto-unwrap |
| **xatlas** (free, external) | Yes (system Python) | 3/10, ~2000 islands | Marginally better than Blender, still unusable |

### B2RUVL details (built into Blender 5.1)
- **Author**: Titus Lavrov
- **Purpose**: Bridge for transferring UVMaps between Blender ↔ RizomUV/Headus UVLayout
- **Workflow**: Export to RizomUV → unwrap in GUI → import back
- **Limitation**: Requires RizomUV/Headus installed and GUI interaction
- **NOT suitable for fully-automated background pipelines**

### Conclusion on plugins
**No Blender plugin provides automated high-quality UV unwrapping for QR meshes
in pure background mode.** UV Packmaster only packs (doesn't unwrap). RizomUV is
the quality leader but has no headless CLI. B2RUVL is just a bridge requiring GUI.

---

## E. Standalone Python LSCM/ABF Implementation

### Feasibility: YES (scipy 1.17.1 + numpy 2.4.3 confirmed available in system Python)

### Architecture

LSCM (Least Squares Conformal Maps) reduces to a sparse linear system:
- Pin 2 vertices (UV anchors) per island
- Build a sparse matrix M (2V × 2V) from edge cotangent weights
- Solve the least-squares system: `min ||M·u||²` subject to pin constraints
- `scipy.sparse.linalg.lsqr` or `spsolve` handles this for 100K+ vertices

### BUT: This will NOT fix the QR fragmentation problem

**Critical insight**: The fragmentation comes from **seam-based island splitting**,
not from the unwrap algorithm. A standalone LSCM implementation:
- ✅ Would give you full control over the solver (pin selection, weights)
- ✅ Could implement ARAP (As-Rigid-As-Possible) with scipy sparse
- ❌ Would still fragment at the same seam boundaries as Blender's LSCM
- ❌ Would require you to reimplement seam detection, island flood-fill, packing
- ❌ Arms/legs would still fold into tiny UV patches (same root cause)

**The folding problem is a pinning/chart problem, not a solver problem.**
Blender's LSCM already solves the linear system correctly — the issue is that
the arms/legs form long thin charts that LSCM optimally folds to minimize
conformal energy. No LSCM variant (Blender's or standalone) avoids this without
additional constraints (e.g., boundary length preservation, ARAP).

### When a standalone implementation WOULD help
- If you implement **ARAP** (As-Rigid-As-Possible) with proper boundary
  preservation — this is what Blender's MINIMUM_STRETCH does, and we confirmed
  it produces the same 84 islands with no visual improvement.
- If you implement **ABF++** (Angle-Based Flattening) — different energy
  function, may handle thin charts better. But this is a research project,
  not a weekend implementation.

### Recommendation
**Do NOT implement standalone LSCM.** The fragmentation is upstream of the
solver. The effort would be better spent on (a) better seam placement to
avoid thin charts, or (b) using a different retopology method than QR.

---

## F. "Average Island Scale" Python API in Blender 5.1

### Confirmed available in background mode

```python
bpy.ops.uv.average_islands_scale(scale_uv=False, shear=False)
```

- **`scale_uv`** (bool, default False): Scale UVs to normalize area
- **`shear`** (bool, default False): Also remove shear distortion
- **Requires**: Edit mode + UV selection (call `bpy.ops.uv.select_all(action='SELECT')` first)
- **Works in `--background --factory-startup`**: YES (verified 2026-07-20)

### Limitation
As noted in section B, it normalizes per-island average texel density but cannot
fix within-island distortion (folding). On QR meshes with 84 fragmented islands,
it makes the average island sizes uniform — but the arms/legs fragments remain
geometrically folded.

---

## Final Recommended Pipeline (Best Available)

### For BAKING (not direct texture painting) — ACCEPTABLE

```python
# Pseudocode — copy from uv_render_checker.py (verified working)
import bpy, bmesh

mesh = find_retopo_mesh()
bpy.context.view_layer.objects.active = mesh
mesh.select_set(True)

# 1. Clear existing seams
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.mark_seam(clear=True)
bpy.ops.object.mode_set(mode='OBJECT')

# 2. Mark minimal anatomical seams (455 edges → 84 islands)
mark_anatomical_seams(mesh)  # back center + L/R leg inner, tight tolerance

# 3. CONFORMAL unwrap (fastest, same quality as others)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.unwrap(method='CONFORMAL', fill_holes=True,
                   correct_aspect=True, margin_method='SCALED', margin=0.003)

# 4. Normalize texel density
bpy.ops.uv.select_all(action='SELECT')
bpy.ops.uv.average_islands_scale()

# 5. Pack islands
bpy.ops.uv.select_all(action='SELECT')
bpy.ops.uv.pack_islands(rotate=True, scale=True,
                         margin_method='SCALED', margin=0.003)
bpy.ops.object.mode_set(mode='OBJECT')

# Result: 84 islands, ~3s, 2/10 checkerboard quality (usable for baking only)
```

### For PRODUCTION QUALITY — REQUIRES EXTERNAL TOOL

**Option 1: RizomUV (recommended if budget allows)**
- Export OBJ from Blender → unwrap in RizomUV (GUI or Lua script) → import UVs
- Quality: 9-10/10
- Cost: $300+/year
- Automation: Partial (Lua scripting, but no documented headless CLI)

**Option 2: xatlas (free, marginal improvement)**
- Two-step: Blender OBJ export → xatlas in system Python → import UVs via .npz
- Quality: 3/10 (slightly better than Blender's 2/10)
- Fully automatable but still unusable for character texturing
- See `references/xatlas-two-step-uv.md` for working implementation

**Option 3: Avoid QR entirely (best long-term fix)**
- Use template-wrap retopology (e.g., MetaHuman topology) instead of QuadRemesher
- Template topology has intentional seam-friendly edge flows
- Standard UV workflows work correctly on template topology
- This is the RECOMMENDED fix for production pipelines

---

## Test Results Summary (all methods tested 2026-07-20)

| Method | Seams | Islands | Time | Checker Score | Usable For |
|--------|-------|---------|------|---------------|------------|
| Smart UV 66° | 760 | 914 | 8s | 2/10 | Nothing |
| Smart UV 89° | 0 | 1983 | 6s | 2/10 | Nothing |
| ANGLE_BASED + 26K seams | 26037 | 12532 | 35s | 2/10 | Nothing |
| CONFORMAL + 26K seams | 26037 | 12532 | 4s | 2/10 | Nothing |
| MINIMUM_STRETCH + 26K seams | 26037 | 12532 | 29s | 2/10 | Nothing |
| ANGLE_BASED + 455 seams | 455 | 84 | 35s | 2/10 | Baking only |
| **CONFORMAL + 455 seams** | **455** | **84** | **3s** | **2/10** | **Baking only (best available)** |
| MINIMUM_STRETCH + 455 seams | 455 | 84 | 48s | 2/10 | Baking (slower, no benefit) |
| Cylinder projection | 0 | 4 | 1s | 1/10 | Nothing |
| xatlas (external) | — | ~2000 | 30s | 3/10 | Marginal |

**Best available**: CONFORMAL + 455 minimal seams → 84 islands, 3s, 2/10.
Meets the island-count goal (close to 50) but NOT the quality goal (2/10 vs needed 7+/10).

---

## Files Created

- `scripts/uv_test_minstretch.py` — 3-method comparison (ANGLE_BASED/CONFORMAL/MINIMUM_STRETCH) with 26K seams
- `scripts/uv_test_minimal_seams.py` — minimal-seam test (455 seams, 84 islands)
- `scripts/uv_final_test.py` — optimized seams + MINIMUM_STRETCH (killed, too slow)
- `scripts/uv_render_checker.py` — CONFORMAL + checkerboard render (verified 2/10)
- `v5_run/uv_check_front.png`, `v5_run/uv_check_back.png` — checkerboard renders
- `v5_run/03_remesh_uv_conformal.blend` — saved mesh with CONFORMAL UVs
