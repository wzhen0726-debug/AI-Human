# B2RUVL / RizomUV Plugin — Background Mode Check (2026-07-20)

## B2RUVL Plugin Status

B2RUVL 0.1.6 is installed in Blender 5.1 (user's machine). It provides
`bpy.ops.b2ruvl` operators for RizomUV bridge.

### Background Mode Check

```
bpy.ops.b2ruvl  ← operator exists
Addon: B2RUVL   ← registered in prefs
import b2ruvl   ← FAILS (no Python module, it's operator-only)
```

B2RUVL is a **GUI bridge** — it exports mesh to a temp file, launches
RizomUV.exe (external application), waits for user to unwrap in the
GUI, then imports the result back. This **cannot work in `--background`
mode** because:

1. RizomUV.exe is a GUI application (no headless CLI)
2. B2RUVL operators require an interactive Blender session
3. The bridge needs a visible RizomUV window

### RizomUV Pricing (as of 2026)

- RizomUV VS (Virtual Spaces): ~$300/year
- RizomUV RS (Real Space): ~$500/year (for non-game/non-VFX)
- No free CLI version available

## Alternative Plugins Checked

| Plugin | Type | Background? | Verdict |
|--------|------|:------------:|---------|
| B2RUVL | RizomUV bridge | ❌ | Needs GUI + RizomUV.exe |
| UV Packmaster | Packing only | ✅ (SDK) | Only packs, doesn't unwrap |
| Magic-UV | UV editing utils | ❌ | No auto-unwrap |
| io_mesh_uv_layout | UV layout export | ❌ | Export only, GPU-dependent |
| lightmap_pack | Built-in auto-UV | ✅ | **Timeouts on 90K+ faces** |

## Practical UV Solution Hierarchy for QR Meshes

Best → Worst for fully-automated background UV on QuadRemesher output:

1. **RizomUV (GUI, paid)** — 9-10/10 quality, requires manual step
2. **average_islands_scale() + 5 seams** — 8.5/10, fully automated ✅
3. **xatlas (external, free)** — 3/10, fully automated
4. **Blender unwrap only (no avg_scale)** — 2/10, fully automated
5. **Cylinder projection** — 2/10, fully automated (4 islands but terrible)

**For this project's pipeline**: Option 2 is the best fully-automated
solution. Option 1 (RizomUV) is the upgrade path when budget allows.

## Alternative Architecture: Skip QR, Preserve UV

The root cause of UV fragmentation is QuadRemesher's uniform quad grid.
An alternative pipeline architecture that **avoids the problem entirely**:

1. UV unwrap the ORIGINAL high-poly mesh (1.9M faces) first
   - Smart UV or seam-based unwrap on dense mesh produces fewer islands
   - Dense mesh has natural curvature variation → Smart UV finds good cuts
2. Use Blender Decimate (not QR) to reduce face count while preserving UVs
   - `bpy.ops.mesh.decimate(ratio=0.05)` → ~95K faces
   - UV coordinates are preserved (Decimate doesn't modify UV layout)
3. Bake from original high-poly onto decimated low-poly
   - UVs are already correct from step 1
   - No QR fragmentation issue

**Trade-off**: Decimate produces triangle-only output (not quads),
which is less ideal for animation but works fine for static GLB export
and game engines. UV quality should be much better since the unwrap
was done on the original mesh topology.
