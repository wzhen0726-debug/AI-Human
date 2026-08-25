# QR Mesh UV — Background Pipeline Test Results (2026-07-20)

## Test Environment
- Blender 5.1.0 (hash adfe2921d5f3, 2026-03-17)
- Mesh: Retopo_tripo_node, 90333 verts, 90331 faces (QuadRemesher output)
- Run mode: `--background --factory-startup`
- Source mesh: `v5_run/03_remesh.blend`

## New API Discoveries (Blender 5.1)

### `bpy.ops.uv.unwrap()` — 3 methods (was 2 in 4.x)
```
ANGLE_BASED, CONFORMAL, MINIMUM_STRETCH
```
MINIMUM_STRETCH params: `iterations=10`, `no_flip`, `use_weights`, `weight_group='uv_importance'`, `weight_factor=1.0`

### `bpy.ops.uv.average_islands_scale(scale_uv=False, shear=False)`
Confirmed working in background mode.

### `bpy.ops.uv.pack_islands(...)` — full params
```
udim_source='CLOSEST_UDIM', rotate=True, rotate_method='ANY',
scale=True, merge_overlap=False, margin_method='SCALED',
margin=0.001, pin=False, pin_method='LOCKED', shape_method='CONCAVE'
```

### NEW: `bpy.ops.uv.arrange_islands(...)` — pre-pack ordering
```
initial_position='BOUNDING_BOX', axis='Y', align='MIN',
order='LARGE_TO_SMALL', margin=0.05
```

### Other UV ops available in 5.1
`stitch` (use_limit, snap_islands, limit, static_island, midpoint_snap, clear_seams, mode=VERTEX), `weld`, `remove_doubles`, `minimize_stretch` (fill_holes, blend, iterations), `follow_active_quads` (mode=LENGTH_AVERAGE)

## Test 1: 3-method comparison with 26K seams (wide tolerance)

| Method | Seams | Pre-islands | Unwrap Time | UV Bounds |
|--------|-------|-------------|-------------|----------|
| ANGLE_BASED | 26037 | 12532 | 34.26s | [0.003,0.989]×[0.003,0.997] |
| CONFORMAL | 26037 | 12532 | 4.07s | same |
| MINIMUM_STRETCH | 26037 | 12532 | 28.57s | same |

**Result**: All 3 methods produce identical fragmentation. Algorithm choice is irrelevant — seams control fragmentation.

## Test 2: Minimal seams (455 edges)

| Seam Type | Edges | Tolerance |
|-----------|-------|-----------|
| Back center (X=mid, Y>0) | 268 | ±0.15% W |
| Left leg inner | 95 | ±0.2% W |
| Right leg inner | 92 | ±0.2% W |
| **Total** | **455** | |

| Method | Pre-islands | Unwrap Time | Total Time |
|--------|-------------|-------------|------------|
| MINIMUM_STRETCH (20 iter) | 84 | 48.36s | 48.82s |
| CONFORMAL | 84 | 3.06s | 3.54s |

**Result**: 455 seams → 84 islands (down from 12532). CONFORMAL is 14x faster than MINIMUM_STRETCH with identical output.

## Test 3: Arm-inner seams (FAILED)

Adding arm-inner cuts (Y<0, X>15%W, Z 55-88%H):
- Caught 4596 edges (2185 left + 2411 right)
- Pre-unwrap islands: 2301 (WORSE than without arm seams)
- **Conclusion**: Arm-inner conditions are too broad. Skip arm seams entirely.

## Test 4: Checkerboard render (CONFORMAL + 455 seams)

Rendered front and back views with UV checkerboard (scale=8).
- Front: 1.5/10 — torso has tiny compressed squares, arms/legs/head solid color
- Back: 2/10 — spine has large stretched squares, limbs compressed

**Symptom**: Arms/legs UV fragments fold into tiny patches. This is the fundamental QR topology problem — not fixable by seam tuning or algorithm choice.

## Conclusion

| Goal | Target | Achieved | Status |
|------|--------|----------|--------|
| Island count | 10-50 | 84 | Close (acceptable) |
| Texel density uniform | Yes | Partial (avg_scale helps but folding remains) | Failed |
| No stretching | Yes | Severe folding on limbs | Failed |
| Fully automated | Yes | Yes (3s, all bpy.ops) | Met |
| Visual quality | 7+/10 | 2/10 | Failed |

**For baking**: 84 islands + CONFORMAL is acceptable (14.7% black pixels).
**For texturing**: Unusable. Requires RizomUV or topology swap (avoid QR).

## Files
- Test scripts: `scripts/uv_test_minstretch.py`, `uv_test_minimal_seams.py`, `uv_final_test.py`, `uv_render_checker.py`
- Renders: `v5_run/uv_check_front.png`, `v5_run/uv_check_back.png`
- Saved blend: `v5_run/03_remesh_uv_conformal.blend`
- Full report: `UV_BACKGROUND_RESEARCH_REPORT.md`
