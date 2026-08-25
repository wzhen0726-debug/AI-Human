# RizomUV Headless Integration Attempt (2026-07-21)

## Environment
- RizomUV 2025.0 installed at: `D:\Program Files\Rizom Lab\RizomUV 2025.0\`
- Executable: `rizomuv.exe` (GUI), `python.exe` (Rizom's bundled Python)
- B2RUVL addon v0.1.6 installed in Blender 5.1
- B2RUVL configured at: `bpy.context.preferences.addons['B2RUVL'].preferences.rizomuv_app_path`

## B2RUVL Operator
- `bpy.ops.b2ruvl.send_to_rizomuv()` — sends mesh to RizomUV
- `bpy.ops.b2ruvl.send_to_uvlayout()` — sends to UVLayout
- Both operators have NO parameters (one-click)
- In `--background` mode: fails with `AttributeError: 'NoneType' object has no attribute 'local_view'`
- Requires VIEW_3D context — needs `temp_override(area=VIEW_3D, region=WINDOW, active_object=mesh)`

## RizomUV Headless Modes
1. **Lua scripting**: `rizomuv.exe -cf script.lua` — runs Lua script, does operations, exits
2. **RizomUVLink (ZMQ)**: TCP-based API for headless control
3. **B2RUVL bridge**: Sends OBJ → RizomUV runs Lua preset → imports result back

## Other UV Options Tested
- pymeshlab LSCM: timeout on 180K triangles
- pymeshlab Voronoi atlas: timeout
- xatlas (system Python): subprocess from Blender failed
- open3d: install failed
- ZEN UV relax: crashes on zero-length vectors
- ZEN UV auto_uv_unwrap + CONFORMAL unwrap_inplace: 63.5% utilization, quality is acceptable but still has issues

## Recommended Path Forward
1. Use RizomUV's Lua scripting for fully automated UV
2. Or: use the B2RUVL bridge with VIEW_3D context override
3. The Lua script approach: export OBJ → run RizomUV with Lua → import result