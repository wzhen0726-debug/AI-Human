# Clean Rebuild vs Experimental Geometry Steps

## Lesson (2026-08-03, chest bump + belly artifact session)
When a specific surface artifact (chest bump, belly "hole") survives the shipped pipeline, do NOT stack broad new geometry stages into `repair_pipeline`:
- ❌ global normal flipping (z-range based) — flips legitimate inward normals in other areas (neck root deformed +16.7mm)
- ❌ whole-region sculpt smooth / Laplacian on wide z-bands — pushed belly to +44mm displacement from raw
- ❌ aggressive `remove_doubles` or `holes_fill` on 2M-face models — `holes_fill` hangs indefinitely on ~10K+ holes

These fix one spot and break others. The shipped pipeline (mesh repair + adhesion) is the trusted baseline; "翻翻之前的做法" means re-run the shipped `run_repair.py`, not invent new steps.

## Correct workflow
1. **Rebuild clean from raw GLB**: import → rotation (stand, -Y forward, arms X) → adaptive `remove_doubles` → non-manifold fix → save. Verify against the raw model with KDTree (rotate raw the SAME way first; comparing raw vs fixed in different coordinate frames gives false 44mm "deviations").
2. **Diagnose the artifact precisely before touching geometry**:
   - boundary edges in the zone? → real hole
   - inward normals? → normal flip (see `belly-area-inward-normals-repair.md`)
   - tiny faces <0.5mm²? → dissolve/merge
   - actual geometric protrusion (local max Y vs ring neighborhood)? → narrow local smooth only
3. **Apply ONE narrow, targeted operation per reported artifact**, verify that zone + neighbors (non-manifold/boundary unchanged, raw-model deviation <1mm outside the zone), then re-render.

## Verification trap
Comparing fixed mesh to raw mesh with KDTree requires SAME coordinate frame: run the same `rotate_to_standard()` on the raw model first. Otherwise every vertex reports 50mm+ "deviation" and you'll chase ghosts.

## KDTree pitfalls
- `KDTree.insert` + `balance()` in a loop = 1M+ balance calls → minutes of hang. Insert all, balance once.
- Rebuilding the tree after vertex moves: create a NEW KDTree, never re-insert into the old one ("Trying to insert more items than KDTree has room for").
