"""
uv_merge1.py — ZEN UV auto_uv_unwrap + single-face island merger.

Workflow:
1. ZEN UV zenuv_auto_uv_unwrap(packing=True, texel_density=True)
2. seams_from_islands() → convert UV island boundaries to seams
3. bmesh flood-fill → find all islands
4. For each exact 1-face island: clear all its seam edges
5. Re-unwrap with ANGLE_BASED
6. average_islands_scale() + normalize with 5% margin

Result: ~21 islands, 0 single-face fragments.
Only merge 1-face islands (do NOT merge 2-3 face islands — they cascade).

Pitfalls:
- Must run WITHOUT --factory-startup (ZEN UV addon must load)
- zenuv_unwrap() crashes in background — use zenuv_auto_uv_unwrap() only
- quads=True and cut=True produce WinError 2 — use defaults
- Need preset dir: ~/AppData/Roaming/Blender Foundation/Blender/5.1/scripts/presets/zen_uv/auto_uv_unwrap/
