# Godot-Safe GLB Batch Processing (Revit GLB → Godot)

The processing phase that follows inspection. Verified on 2-发射机房 (5 files, 188.7MB output, 2026-08-07).

## User constraints (Godot target) — non-negotiable

- Textures: **Color + NormalGL + Roughness + Metallic** (glTF 2.0 standard channels Godot reads natively). No AO/displacement/emission tricks.
- **Metallic (user-required 2026-08-08): if the texture set ships a Metallic map, wire it into the Principled `Metallic` input (Non-Color). Only when a texture set has NO Metallic map do you fall back to a scalar `metallicFactor`.** The old rule "always scalar, skip the metallic map" is REVOKED — the user explicitly called it out ("我这贴图里都有金属度贴图啊，为啥不用"). Verify after export by counting materials with `metallicRoughnessTexture` in the GLB JSON chunk.
- Normal format: **NormalGL (green-up / OpenGL / Y-up)** — never NormalDX. Godot expects OpenGL-style normals.
- metallic/roughness/alpha **snap to 0.05 steps** (0.8, 0.85) — never 0.8312. `round(v*20)/20`. (Scalar fallback only; map-driven channels need no snapping.)
- Glass: **alpha 0.35, roughness 0.95** — effect over physics. Real architectural glass has coatings and barely transmits; don't make it fully clear or interiors leak through.
- Plain Principled BSDF only. glTF can't carry node graphs anyway; keep exports boring.
- `mep`/`plastic`/`glass`: **param-only** (baseColor + metallic + roughness), no texture, no UV — runtime remaps these by name.
- Textured materials: export **baseColorFactor = white** (texture at native color). The Revit color is a placeholder, do not multiply it in.

## Blender 5.1 batch quirks (all hit in production)

- `bpy.scene` is gone → `bpy.context.scene`.
- EEVEE enum = `'BLENDER_EEVEE'` (4.x `BLENDER_EEVEE_NEXT` removed).
- glTF exporter has **no `export_texture_compression` param** — omit or it raises.
- Import renames duplicate materials with `.001/.002` suffixes → match on `(basename, colorhex)`, strip suffix with `re.sub(r'\.\d+$', '', name)`.

## UV: cube projection for tiling

```python
bpy.ops.uv.cube_project(cube_size=3.0, scale_to_bounds=False)
```

**`scale_to_bounds` MUST be False.** True compresses the whole building's UVs into 0-1 and kills the 3m tiling. Leave UVs in world scale and rely on the glTF sampler: `sampler=None` in the exported JSON defaults to REPEAT per spec, and Godot honors it.

## Color-tolerance matching — the tie trap

Blender reads back baseColorFactor with tiny drift (int-truncation vs rounding: `#F3F3F3` reported as `#F2F2F2`). Matching by `(name, hex)` with a tolerance (max-channel distance ≤ 4) can **tie**: `#F3F3F3` is distance 1 from both `#F2F2F2` and `#F4F4F4`, dict order wins → a 261k-face AC-housing got the concrete-stairs texture.

- Ambiguous/one-off materials: **explicit per-file overrides** (deterministic, no tolerance walk).
- Tolerance matching only as fallback for the generic table.
- Colors absent from the recipe table entirely (e.g. `concrete #BFBFBF` read back `#C0C0C0`, distance 11 from nearest entry) → add a global recipe entry and re-run that file.

## Texture compression before embedding

Raw 2K PNG sets ≈ 247MB → embedded GLB would be hundreds of MB. Pre-compress with Pillow to a JPEG q87 cache (≈21MB) and have the Blender script load from the cache. Blender auto-converts the Roughness map back to PNG on export (acceptable).

## Curated texture library (user workflow rule, 2026-08-07)

User rule: **raw texture assets stay untouched** in their messy original dir (`原始资料/贴图素材/`). Only materials actually used by the pipeline get copied into a **curated library** (project root, e.g. `贴图素材库/`), and ALL future texture lookups/additions go through the curated library — never the raw dir again. Only organize what's been used; don't pre-organize everything.

Layout convention:

```
贴图素材库/
├── index.md                      # index: source dir, usage, naming rules
├── concrete_混凝土/
│   ├── concrete_Color.jpg
│   ├── concrete_NormalGL.jpg
│   └── concrete_Roughness.jpg
└── steel_钢/ ...
```

- Folder name = `{key}_{中文名}` — key is the pipeline's internal identifier (lowercase ASCII + underscores, may contain underscores: `ahu_shell`, `steel_big`), Chinese name is human-readable.
- 3 standard files per folder: `{key}_Color.jpg`, `{key}_NormalGL.jpg`, `{key}_Roughness.jpg`.

### Folder lookup pitfall: never use prefix matching

Keys contain underscores but Chinese names don't, so naive `startswith(key + '_')` collides: `steel` matches BOTH `steel_钢` and `steel_big_金属楼板` (dict order decides → wrong texture loaded, export crashes on missing file). Correct match = compare the ASCII part before the first CJK character:

```python
def find_tex_folder(tex_root, key):
    for d in os.listdir(tex_root):
        fp = os.path.join(tex_root, d)
        if not os.path.isdir(fp): continue
        ci = next((i for i, ch in enumerate(d) if ord(ch) >= 0x4E00), -1)
        if ci > 0 and d[:ci].rstrip('_') == key:
            return fp
    raise FileNotFoundError(f'texture lib missing folder for {key}')
```

### Relocation verification: byte-identical re-run

After moving the texture cache to a new location / renaming the library, re-run the **smallest** file through the pipeline and compare the output byte count with the original deliverable. Identical size = migration had zero effect (confirmed 12,563,572 B both sides). Cheap, definitive; do it before deleting the old cache.

## Texture refill & normalization (user re-fills the curated library)

The user re-fills library folders with their own textures under **free vendor naming** (Poliigon `X_BaseColor/Normal/Roughness.png`, GSG `X_basecolor/normal/roughness.png`, custom `wzDB17_01_D/_N/_ARM`). The pipeline only reads `{key}_Color/NormalGL/Roughness.jpg`, so every refill round needs a normalize pass before export — see `scripts/normalize_tex.py`:

- **Classify by filename fragment** (case-insensitive): `basecolor|base_color|albedo|diffuse|_d.|_col` → Color; `normal|_n.|_nrm` → Normal; `roughness|_rough|_r.` → Roughness; `metallic|metalness|_m.` → Metallic; `arm` → packed AO/Rough/Metal.
- **ARM unpack**: `_ARM` packs AO=R, **Roughness=G**, **Metallic=B** — extract **G for Roughness AND B for Metallic** (B-channel Metallic is the only metallic source for ARM-packed sets like the wood door).
- **Normal convention**: Poliigon & GSG ship **OpenGL (green-up)** normals by default → copy as-is, do NOT flip G. Only flip if the source is known DirectX.
- **Compress**: cap longest side at 2048, save JPEG q87 (vendor PNGs run 3-9MB each; embedding raw inflates GLB to hundreds of MB).
- **Missing maps**: Color alone is acceptable — default normal=flat / roughness=0.8. Don't block export on absent Normal/Roughness.
- **User annotates a folder with a subfolder** like `concrete_混凝土/此材质需要10mUV/` — read these as instructions; the recipe cube size should already reflect it (large-area concrete 10m, walls 3m).

### Wiring maps with graceful per-channel fallback (crash fix 2026-08-08)

Once Metallic and missing maps entered the picture, the node builder must tolerate ANY channel being absent. A material whose texture set lacks Roughness (e.g. `steel_big` sourced from a Color+Normal-only concrete set) crashed the export with `AttributeError: 'NoneType' ... colorspace_settings` because the old code did `load_img(...).colorspace_settings` unconditionally. Pattern that survived:

```python
def load_img(key, suffix):           # returns None when the map file doesn't exist
    p = tex_path(key, suffix)        # None if folder or file missing
    if p is None: return None
    img = bpy.data.images.load(p)
    img.colorspace_settings.name = 'sRGB' if suffix == 'Color' else 'Non-Color'
    return img

# in the tex branch — every optional channel guarded:
rgh = load_img(k,'Roughness')
if rgh is not None: link(t_rgh -> bsdf.Roughness)
else:               bsdf.Roughness = snap(rough)      # scalar fallback
nrm = load_img(k,'NormalGL')
if nrm is not None: link(t_nrm -> NormalMap -> bsdf.Normal)
# else: leave Normal unconnected (flat)
met = load_img(k,'Metallic')
if met is not None: link(t_met(Non-Color) -> bsdf.Metallic)   # metTex
else:               bsdf.Metallic = snap(met)                  # scalar fallback
```

Only Color is hard-required (a tex recipe with no Color map is a recipe bug). Log which path each material took (`metTex` vs `met=0.8`) so a `grep` of the run log instantly shows whether the metallic maps landed — confirmed on 建筑 (concrete/wood → metTex) and 设备/电气 (cabinet → metTex).

## Material-错乱 correction (Revit tags a part with the wrong class)

Revit sometimes exports a building part under the wrong material class — e.g. 2_发射机房_建筑's **floor** was exported as `steel.002` (原始材质错乱). The user keeps the source GLB untouched and asks you to remap it only at OUTPUT time.

Correct procedure (verified 2026-08-10):

1. **Locate by fingerprint, not by the user-quoted hex.** The user often reads the hex off Godot (post color-management), which won't match the raw value — `#BCBEB5` quoted vs `#808375` actually read by Blender. Dump every same-named material in that file with a read-only Blender probe (`name`, `BaseColor` read back, per-material face count) and pin the target by `(basename, Blender-read hex)` — here `steel` + `#808375` (steel.002, 604 tris).
2. **Add the explicit override AND lock the siblings.** FILE_OVERRIDES matching takes the *nearest* color within tolerance ≤4. The same file had `steel.001 #80807E` (22,718-tri main steel frame) at distance 4 from the floor's `#818476` — inside tolerance, so it would have been dragged onto the floor texture. Fix by giving every other same-named material its own explicit entry that keeps its original mapping, so each matches itself exactly and only the target falls through to the new texture:
   ```python
   ('steel','#80807E'): ('tex','steel',3.0,0.8,0.40),       # sibling, keep steel
   ('steel','#A9A9A9'): ('tex','steel',3.0,0.8,0.40),       # sibling, keep steel
   ('steel','#818476'): ('tex','tile_floor',3.0,0.0,0.40),  # the floor -> indoor tile
   ```
3. **Register the new texture key in the V3 keep-list.** A brand-new mapping key (e.g. `tile_floor`) is NOT in `v3_config.json`'s `keep_texture`, so V3 mode intercepts it to a flat color (log shows `V3纯色` instead of `tex=`). Add it, then re-run only the affected file(s).
4. Verify post-export by parsing the GLB JSON chunk: the target material (`steel.002`) must carry `baseColorTexture`, siblings must not.

## Verification pattern

1. Render far + close-up shots (camera ~3m off a surface, 50mm, EEVEE, sun light) and `vision_analyze` both.
2. **Vision can misreport**: it flagged "concrete surface wrongly textured as wood" — it was a legitimate 0.97×2.43m wooden door. Before trusting a vision verdict, cross-check with a script that lists which objects carry a material and their bounding-box dims.
3. Validate exported GLB structure with pure Python (parse JSON chunk, check magic, count materials/textures/images/nodes).

## Batch decision tables across many building categories (13+ cats, 60+ GLBs)

When front-loading 决策表 for many categories at once (user adjusting textures, no final GLB yet):

- **Aggregate by `(name, colorhex)` across all files in the category**, tracking total tris + which files each appears in — NOT per-file rows. One category table with merged rows is far more scannable than per-file dumps.
- **Sort rows by tris descending** so the big-impact materials sit at the top and get eyes first.
- **Auto-classify the semantic greens without asking**: `#008000` / `#008800` (and any `unknown`/`plastic` where G clearly dominates, e.g. `g>100 and g>r+40 and g>b+40`) → `grass` at 10m cube. Confirmed repeatedly across buildings; the user already approved green→草地. Exclude these from the 待确认 list so it only holds genuinely ambiguous unknowns.
- Everything else that is uncertain stays **待确认** (never pre-fill). Certain known classes (mep colors, steel, concrete, glass, plaster, wood, metal_alu, brick-param) pre-fill per the established rules.
- Watch for **new semantic colors that imply a special surface** and flag them 待确认 rather than guessing — e.g. `unknown #FFFF00 α0.40 rough0.99` (115k tris, 总图给排水) reads as a translucent water/overlay surface, not a solid; don't auto-texture it.

## Batch execution

- One background Blender per file: `nice -n 19 blender --background --python proc.py -- in.glb out.glb`, `notify_on_complete=true`. Foreground cap is 600s; files >200k tris must run background.
- Log-grep for `✓/✗/导出完成` lines to confirm per-material matches; any `✗ 无匹配` = recipe gap, fix and re-run that file only.
- File names may not match expectations (`2_发射机房_设备` was actually `2_发射机房_发射机房设备.rvt.glb`) — `ls` the source dir first; "Please select a file" from the glTF importer means the path doesn't exist.

## Consolidating a messy delivery tree (user-requested reorg 2026-08-08)

When the project root accumulates a flat sprawl of delivery folders (`02_UV处理/`, `03_UV处理_配电机房/`, …, `15_UV处理_总图/` — note they start at 02, not 01, because 01 was a scratch dir), the user will eventually ask to clean it up. Safe sequence:

1. **Find every hardcoded path the pipeline depends on BEFORE moving anything.** `grep` all `*.py` for absolute path literals (`r'E:\\…'`). In this project the live scripts hardcode only three roots: `贴图素材库\`, `原始glb\assembled_nomerge\`, and one stale one-off generator pointing at `02_UV处理\`. The `NN_UV处理_*` dirs themselves are referenced ONLY by already-finished one-shot batch scripts — never by `process_room2.py` — so they are free to move/rename.
2. **Rename the batch one-shot scripts' stale paths or annotate them** (`[已完成] …勿再直接运行`) so they don't rebuild empty old-name dirs if accidentally re-run. Fix the single live one-off generator path too.
3. **Group delivery folders under one `交付/` parent with continuous numbering**: `交付/01_发射机房`, `02_配电机房`, `03_发射塔楼`, … `14_总图`. Renumber so the completed one becomes 01. Move preview PNGs into a `preview/` subfolder inside the relevant delivery dir.
4. **Move run logs / `.done` markers / probe dumps** out of `scripts/` into `scripts/logs/` (28 files here). Keep only `.py` at the top of `scripts/`.
5. **Regenerate the root index** (`交付/README.md`) as a table: 编号 / 目录 / 成品GLB数 / 待确认unknown数 / 状态. Delete the superseded root-level index file.
6. **Do NOT rename the three pipeline-locked roots** (`贴图素材库`, `原始glb`, `原始资料`) — the Blender script reads them by absolute literal; renaming breaks the pipeline until you also patch the script.
7. **Do NOT delete "duplicate" data without being asked.** Two `assembled_nomerge` copies (each 1.29GB, 71 files, identical sizes) exist; the user chose to keep both. Flag the duplication, let the user decide.

After reorg, re-verify by `ls`-ing the new tree and confirming the delivery README matches reality.
