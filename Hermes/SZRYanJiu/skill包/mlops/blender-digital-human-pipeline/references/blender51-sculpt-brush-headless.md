# Blender 5.1 sculpt-brush automation in --background (status: UNVERIFIED)

User request pattern: "我自己用雕刻平滑笔刷能解决，你不能用笔刷吗？" — they want scripted equivalent of the GUI Smooth brush on a local region.

## Verified API facts (Blender 5.1, via rna inspection)
- `Brush` has NO `mode`/`sculpt_tool`; use `brush.sculpt_brush_type = 'SMOOTH'`, `brush.use_paint_sculpt = True`.
- `tool_settings.sculpt.brush` is READ-ONLY in 5.1. Pass the brush via `bpy.ops.sculpt.brush_stroke(stroke=[...], brush_toggle='SMOOTH')` — `brush_toggle` is an ENUM string (`'SMOOTH'|'ERASE'|'MASK'`), NOT a Brush object.
- Old `bpy.ops.sculpt.sculpt_stroke` is gone; it is `bpy.ops.sculpt.brush_stroke`.
- Stroke element = `OperatorStrokeElement`: `location`(3f object space), `mouse`(2f), `mouse_event`(2f — REQUIRED, was missing pre-5.1), `pressure`, `size`(float), `x_tilt`, `y_tilt`, `time`, `is_start`.
- `brush.size` is INT pixels; for scene-unit size set `brush.use_locked_size='SCENE'` + `brush.unprojected_size` (float meters).
- **PITFALL: `sculpt.use_symmetry_x` defaults to True.** Must set False for models with asymmetric textures/details, or the stroke mirrors.
- `brush_stroke.poll()` needs `context.area` — in `--background`, area is None. Fix: `temp_override(window=..., screen=..., area=<VIEW_3D area>, region=<WINDOW region>)` where the area MUST belong to the CURRENT window's screen (`bpy.context.window.screen`), else "Area not found in screen".

## UNRESOLVED
With all of the above correct, `brush_stroke` executes without error but **changes 0 vertices** in `--background`. Likely cause: no real viewport for falloff/projection. Do NOT claim this approach works; treat as unverified until a test shows changed_verts > 0.

## Deterministic fallback (recommended direction)
Instead of emulating the brush, do bmesh local Laplacian smoothing with anchored boundary: select region verts by 3D distance to feature center, freeze the boundary ring, iterate `co = avg(neighbors)` N small steps, compare vs original after each step (see `geometric-anomaly-diagnosis.md`). This is reproducible, region-controlled, and needs no viewport.
