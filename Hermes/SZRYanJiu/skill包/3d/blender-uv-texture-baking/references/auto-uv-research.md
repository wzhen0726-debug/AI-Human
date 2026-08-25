# Auto UV Unwrap Research — Human Body Models (200-250K poly)

Research session: 2026-07-15. Sources: Blender 5.1 API docs, UVPackmaster
website, RizomUV website, Magic-UV GitHub, existing blender-uv-texture-baking
and blender-digital-human-pipeline skill knowledge.

## Smart UV Project Quality on Human Body Models

Smart UV Project groups faces by normal direction and projects each group
onto a plane. Parameters: `angle_limit` (default 66° = 1.15192 rad),
`island_margin`, `area_weight`, `correct_aspect`, `scale_to_bounds`.

### Quality assessment for 200-250K poly human models:

| Dimension | Finding | Severity |
|-----------|---------|----------|
| Seam placement | Uncontrollable — cuts appear at sharp-angled face boundaries. On human models, seams inevitably appear on face (nose, ears), joints, and fingers | High |
| Island fragmentation | Severe — 50-200+ UV islands. Fingers, ears, facial details produce many tiny fragments | High |
| Stretching | Can be reduced by lowering `angle_limit`, but at the cost of more islands. Default settings show visible stretch at ears and nose | Medium |
| Symmetry | No guarantee — left and right UV layouts may differ. Fatal for character models requiring symmetric textures | Critical |
| UV space utilization | Low due to fragmentation — many gaps between islands | Medium |

**Verdict**: Smart UV Project alone is **unsuitable** for human body models,
even at non-AAA quality standards. The core issue is not visual fidelity but
structural: uncontrollable seams and missing symmetry break texture workflows.

## Auto Seam Detection Algorithm

### Blender 5.1 API available primitives:

- `bpy.ops.mesh.edges_select_sharp(sharpness)` — select edges by sharpness threshold
- `bpy.ops.mesh.mark_seam(clear=False)` — mark selected edges as seams
- `bpy.ops.mesh.set_sharpness_by_angle(angle, extend)` — set sharp edges by angle
- `bpy.ops.uv.seams_from_islands(mark_seams=True)` — reverse: create seams from UV island boundaries
- `bpy.ops.uv.unwrap(method='ANGLE_BASED'|'CONFORMAL'|'MINIMUM_STRETCH')` — standard unwrap
- `edge.calc_face_angle()` — bmesh: get dihedral angle between two faces

### Recommended approach (implemented in `scripts/auto_uv_pipeline.py`):

1. Iterate all non-boundary edges via bmesh
2. Compute dihedral angle via `edge.calc_face_angle()`
3. Mark edges with angle ≥ threshold (55° default) as seams
4. Additionally mark edges on X=0 symmetry plane as seams
5. Run `bpy.ops.uv.unwrap(method='ANGLE_BASED')`
6. Run `bpy.ops.uv.pack_islands(rotate=True, scale=True)`

## Alternative Tools Comparison

### UVPackmaster
- Type: Blender/Maya/3ds Max plugin (paid, $29-49)
- Function: GPU-accelerated UV **packing** (not unwrapping)
- Automation: Python SDK embedded in engine, fully scriptable
- Free SDK available for development
- Does NOT handle seam marking or unwrapping — packing only

### RizomUV
- Type: Standalone application (paid, $300+/yr)
- Function: Professional UV unwrapping and packing
- Automation: Lua scripting API, no clear headless/CLI mode documented
- Pipeline: Export OBJ/FBX → RizomUV process → import back
- Quality: Industry-leading auto-unwrap, far better than Smart UV Project

### Magic-UV
- Type: Blender built-in addon (free, Release support level)
- Function: UV editing utilities (copy/paste, flip/rotate, mirror, align, pack)
- Automation: All features accessible via `bpy.ops.uv.*`
- Does NOT include auto-seam detection or auto-unwrap

### Blender Built-in Unwrap (Angle Based)
- Type: Blender built-in (free)
- Function: UV unwrapping from existing seams
- Quality: Good for organic models when seams are properly placed
- Requires: Existing seam marks (manual or auto-detected)

## Post-Processing Capabilities

- `bpy.ops.uv.pack_islands(rotate, scale, margin, shape_method)` — layout optimization
- `bpy.ops.uv.average_islands_scale()` — balance texel density
- No automatic island stitching API exists — `bpy.ops.uv.stitch()` requires manual edge selection

## Recommendation

**Fully automated, acceptable quality: FEASIBLE.**

Recommended pipeline: `edge-angle seam detection → symmetry-axis seam → Angle-Based Unwrap → pack_islands`

All Blender-built-in, zero cost, zero external dependencies, 100% scriptable.
If higher UV space utilization is needed, add UVPackmaster for the packing step.
RizomUV is overkill for non-AAA pipelines given the cost and integration complexity.