# RizomUV 2025.0 CLI / LUA Headless Integration — FINAL VERDICT (updated 2026-07-22)

## VERDICT: RizomUV headless ZomUnfold does PROJECTION, not LSCM/ARAP — NOT viable for production UV

**The earlier claim of "7.0/10 with ZomIslandGroups" was a FALSE POSITIVE.**
The vision score of 7.0 was from a render where UV import had a silent bug
(the import script selected the wrong mesh object — the original retopo instead
of the imported one — so 04_uv.blend still contained the old Blender projection
UVs, not RizomUV's output). When the user opened the file in Blender GUI, they
saw circular/projection UVs. Final confirmed testing with correct import +
no average_islands_scale showed 4.5/10 with clear circular projection artifacts.

### Progression of false hope
1. Border=true+Cut alone: 2/10 (vision said 2, confirmed projection)
2. Border+Cut+IslandGroups+Unfold: vision said 7.0/10 — **FALSE** (import bug)
3. Same script, correct import, no average: vision said 4.5/10 — **TRUE** (still projection)
4. User screenshot confirmed: "circular/disc-like UV island" = projection

### Why ZomUnfold does projection in background mode
RizomUV's ZomUnfold in `/cfi` + `/nu` + `/nle` headless mode behaves differently
from GUI Unfold. The GUI Unfold triggers LSCM/ARAP energy minimization; the
LUA ZomUnfold appears to default to orthogonal projection regardless of:
- IslandGroups({Mode="CreateFromCuts"}) — helps Island segmentation but Unfold still projects
- Iterations parameter — no effect on projection vs real unfold
- NormalizeUVW — resets UV but Unfold still projects after reset
- Border=true selection + Cut — correctly cuts but Unfold still projects

This is likely a RizomUV 2025.0 limitation: the LSCM/ARAP solver may require
a GUI rendering context or OpenGL initialization that doesn't happen in
headless `/cfi` mode.

## Environment
- RizomUV 2025.0 at `D:\Program Files\Rizom Lab\RizomUV 2025.0\rizomuv.exe`
- B2RUVL bridge addon v0.1.6 (GUI only, not for headless)
- `ForcePython.usda` exists at install dir root — must run from there

## Verified Working LUA API

| Function | Status | Notes |
|----------|--------|-------|
| `ZomLoad` | ✅ | `XYZUVW=true, UVWProps=true` for UV border; `NormalizeUVW=true` for reset |
| `ZomSet` | ✅ | `ZomSet({Path="Prefs.FileSuffix", Value=""})` |
| `ZomSelect({Border=true})` | ✅ | Select UV island border edges — WORKS correctly |
| `ZomSelect({All=true})` | ✅ | Select all (boolean param, not WorkingSet) |
| `ZomSelect({Auto={Skeleton=true}})` | ⚠️ | Fails on QR meshes (uniform normals) |
| `ZomSelect({Auto={SharpEdges={AngleMin=N}}})` | ⚠️ | 1° = cut all edges = 2/10 |
| `ZomCut` | ✅ | `WorkingSet="Selected"` only |
| `ZomIslandGroups({Mode="CreateFromCuts"})` | ✅ | Rebuilds island segmentation — works but doesn't fix Unfold |
| `ZomUnfold` | ❌ | **DOES PROJECTION NOT LSCM/ARAP** — 2-4.5/10 quality |
| `ZomOptimize` | ✅ | `Iterations=20` — minor improvement on projection |
| `ZomPack` | ⚠️ | Hangs on 90K+ faces — pack in Blender instead |
| `ZomSave` | ✅ | `ZomSave({File={Path="..."}})` |
| `ZomQuit` | ✅ | Required to exit headless mode |
| `ZomCutAuto` | ❌ | Does NOT exist |
| `ZomUVSet` | ❌ | nil at runtime (documented but doesn't exist) |
| `ZomIslandGroup` (singular) | ❌ | nil — use `ZomIslandGroups` (plural) |
| `U3dSet Prefs.PackOptions.MapResolution` | ❌ | Variable not found |

### WorkingSet enum values
Only: `"Visible"`, `"Selected"`, `"Flat"`, `"NotFlat"`
Combinations: `"Visible&Selected&Flat"` allowed.
NO `"All"` (use `ZomSelect({All=true})`), NO `"UVBorders"` (use `Border=true`).

### Key lessons
1. `ZomIslandGroups({Mode="CreateFromCuts"})` correctly rebuilds islands but ZomUnfold STILL projects
2. FBX does NOT preserve edge seam info — use UV border approach (Border=true)
3. `NormalizeUVW=true` resets UV (90333 unique UVs) but Unfold still projects
4. Edge IDs mismatch after FBX import — never pass Blender edge IDs to RizomUV
5. Auto-seam (Skeleton/SharpEdges) fails on QR meshes — uniform normals
6. ZomPack hangs on 90K+ faces — always pack in Blender
7. Must run from RizomUV install directory (ForcePython.usda dependency)
8. **UV import verification is CRITICAL**: always check a known vertex (head-top V≠Z/height)
9. **Vision scores can be wrong**: always verify UV is not projection before trusting vision score

## Best Available UV Approaches (none are production-ready)

### 1. ZEN UV (8.25/10 — BEST, Blender internal)
5 manual seams → `zenuv_auto_uv_unwrap(hard_edges=False, texel_density=True, packing=True)` → average
**Drawback**: ~2000 fragment islands, 60-70% utilization

### 2. Blender ANGLE_BASED + average (8.5/10 — highest score)
5 manual seams → `unwrap(method='ANGLE_BASED')` → `average_islands_scale()`
**Drawback**: 1145 islands, fragmentation

### 3. RizomUV headless (2-4.5/10 — NOT viable)
All approaches produce projection, not real unfold. Do not use for production.

## Full Research Report
`E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\方案md记录\v3_QuadRemesher\UV展开问题调研报告.md`
