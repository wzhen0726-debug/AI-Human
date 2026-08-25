---
name: glb-inspect-and-report
description: Use when inspecting GLB assets and writing material reports.
version: 1.0.0
metadata:
  hermes:
    tags: [GLB, glTF, Revit, materials, asset-inventory, reporting]
    category: 3d
    related_skills: [docx, xlsx, blender-uv-texture-baking]
---

# GLB Inspect & Report

Read glTF/GLB assets directly (no Blender needed for metadata), extract material/mesh/texture stats, and emit a deliverable (.md / .xlsx / .docx) the user can hand to a colleague.

## When to use

- "统计/列出 GLB 里的材质 / mesh / 纹理"
- "这个 GLB 有哪些材质，每个占多少面"
- "给同事一份表 / 文档 / Excel 汇总这些资产"
- UV/贴图规划前的资产盘点（Revit 导出 GLB 尤其常见）

Do NOT use this to *edit* the GLB — for UV unwrapping, retopology, baking use the relevant Blender skill.

## Material fingerprinting — same name ≠ same material (user-corrected 2026-08-07)

**Do NOT merge or report materials by `name` alone.** Revit exports one entry per (name, baseColorFactor, metallic, roughness) tuple, so the same name (`steel`, `mep`, `unknown`) can appear as multiple entries with *different* PBR params — these are NOT the same material. Conversely, the same fingerprint can appear under different names (white-painted `metal_alu` / `plaster` / `unknown` all share `#FFFFFFFF`).

The dedup key is the **fingerprint**, not the name:

```python
def fingerprint(mat):
    pbr = mat.get('pbrMetallicRoughness', {})
    base = tuple(round(x, 4) for x in pbr.get('baseColorFactor', [1,1,1,1]))
    met  = round(pbr.get('metallicFactor', 1.0), 4)
    rough= round(pbr.get('roughnessFactor', 1.0), 4)
    return (base, met, rough)
```

Report three numbers per file: `len(materials)` slots, `len(set(names))` unique names, `len(set(fingerprints))` true materials. UV/贴图 work keys off the third.

## Runtime contract (from project's `材质命名.txt`) — READ BEFORE 贴图

If the GLB is part of a pipeline with a `MaterialRemapper` (or any runtime that swaps materials by name), there are hard rules about what you may texture:

- **`mep` / `plastic` / `glass`**: param-only. Do NOT add albedo texture. Do NOT add UVs (or only lightmap UV). The runtime only adjusts `roughness` / `metallic` / alpha on these — adding `albedo_texture` makes the runtime skip its remap logic entirely.
- **`unknown`**: do not touch. Wait for human classification (see feedback loop below).
- **Anything with `albedo_texture` already set**: runtime skips — your previous work is never overwritten.
- **`baseColorFactor` is the机电分色 lifeline.** Never reset it to white when texturing; multiply the albedo texture *against* it instead.

Always ask the user which classes are texture-targets before unwrapping. For the 发射塔/机房 project: only `concrete / plaster / brick / metal_alu / steel / wood` get UV+texture.

## Unknown-material feedback loop (user prefers this format)

Generate a single .txt the user opens in their GLB viewer and fills in. Format per line:

```
[mat_XX] unknown  颜色=#RRGGBBAA  面数=N,NNN  → 你的判断: ___
```

Group by GLB file with full path. User fills the blank with a class name or free text (`空调箱外壳`, `机柜`…), saves, returns the path. Sort by 面数 descending so big-impact unknowns get eyes first.

**Critical (user-corrected 2026-08-08, file order): the per-file blocks inside the 清单 MUST follow the OS file-explorer order the user actually opens files in — natural sort (numeric runs compare as numbers, not lexicographically).** Default `glob`/`sorted()` gives lexicographic order (`100.000` before `50.000`), which mismatches Explorer and forces the user to jump file 1→4→2 losing track of progress ("文件一多，我都不知道做到了哪里了"). Sort file blocks with a natural key: `re.split(r'(\d+)', title)` → digits as `(1,int)`, text as `(0,str)`. Within a block keep rows as-is (each row already carries 面数). When REORDERING an already-filled list, preserve every filled `→ 你的判断:` line verbatim and verify row-count + filled-count match before/after (backup first — user had 20 answers filled across two lists). Reusable reorder script: `reorder_unknown_lists.py` (project scripts/).

**Critical (user-corrected 2026-08-08): NEVER guess an ambiguous unknown yourself.** If the agent is not certain what a material is, write it to the 待确认清单 and let the user classify in one pass. Do NOT pre-fill the blank with your guess, and do NOT pick a texture for it in the decision table (mark `待确认` there too). Even offering a forced multiple-choice picker for genuinely ambiguous materials is wrong — the user answers with "写到文本里，我之后统一确认". Certain items (mep colors, steel, concrete…) may be pre-filled in the decision table; uncertain ones stay blank.

**Corollary (user-corrected 2026-08-10): never auto-classify a *part* by color either.** The same hex can be roof in one file and wall/floor/threshold in another (e.g. `#7F7F7F` appears as roof AND walls across categories). When the user asks to keep a specific part's texture (e.g. "the roof concrete"), only pin the exact `(file, name, hex)` they confirmed — do not extend it to same-colored materials elsewhere. User will inspect and report more (`不能区分的话我后面检查了给你说`).

**原始材质错乱修正 (2026-08-10):** Revit may tag a part with the wrong class (a floor exported as `steel.002`). When the user reports "X in file Y is actually part Z", fix it in the OUTPUT pipeline via FILE_OVERRIDES, not the source GLB (user keeps source untouched). Lock the file's OTHER same-named materials to their own entries too, or the tolerance-nearest match will drag them into the new mapping. Match the target by `(material basename + Blender-read-back hex)` — the user often quotes the Godot-displayed hex which won't match the raw value. See `references/godot-glb-batch-processing.md` § "Material-错乱 correction".

**glTF alpha-loss on Blender import (2026-08-11, 整合版):** a semi-transparent material stored as `#RRGGBBAA` (e.g. `#0080C01A`, 10%-alpha glass) reads back from Blender's Principled `Base Color` as opaque `#0080C0FF` — the importer moves alpha into the separate `Alpha` socket. Any fingerprint/决策表 keyed on the full 8-hex **will miss** after a Blender round-trip. Match on the first 6 RGB hex digits (or register both alpha variants), and handle alpha separately. Bites when unknown-decisions authored from the raw GLB are applied to Blender-read materials.

**Color-reuse annotation on the 待确认清单 (user-requested 2026-08-11):** when delivering the fill-in list, annotate each unknown with whether its baseColor is **库内唯一 (✓唯一色)** or **与已知材质撞色 (✗撞色 + list which)**. Uniqueness tells the user the color alone can be a stable match key on future model updates; collisions (common greys/whites/reds like `#787878`/`#FFFFFF`/`#FF0000`) always need a parent-node/type disambiguator. Compute by grouping ALL materials by RGB hex and flagging which groups contain named vs unknown materials.

## Staged delivery: 前置步骤 first, final GLB later (user-corrected 2026-08-08)

When the user says they need to adjust textures first, deliver ONLY the prerequisite steps and hold the final textured GLB:

1. **体检报告** (`inspect_report.txt`) — per-file fingerprint + tris, pure Python, no Blender.
2. **决策表** (`材质处理决策表_<类别>.md`) — full mapping; texture-target rows filled, unknown rows marked 待确认.
3. **待确认清单** (`unknown待确认_<类别>.txt`) — the fill-in file above.

Then STOP and hand back. Do not proceed to texture assignment / GLB export until the user returns the filled 清单 and finishes texture adjustments. Scripts `inspect_generic.py` and `gen_unknown_generic.py` take `(glob_pattern, out_path)` so any new building category gets its own folder (`03_UV处理_配电机房/`, `04_UV处理_发射塔楼/`, …) with the same three artifacts.

## 素材库 auto-mapping via directory naming convention

User's local library (e.g. `F:\NWT\李小龙\cztu` or `原始资料/贴图素材/`) uses Chinese directory names embedding the mapping:

```
18.红色管道#FF0000FF.mep.004_1/         ← hex color + material.name (with .004 suffix from old GLB indexing)
28.墙面白灰色plaster_5/
33.纹理地砖brick_1/
```

Parse `#{8-hex}` + `material-name` from each dir name. Match against GLB materials by **(hex, class)** — NOT by `.00N` suffix, which is an artifact of an old export and won't match current indices. Each leaf dir contains a Poly-Haven-style 2K PBR set (`*_Color.png`, `*_NormalGL.png`, `*_Roughness.png`, `*_AmbientOcclusion.png`, `*_Displacement.png`).

**Curated library rule (user preference)**: raw asset dirs stay untouched; only textures the pipeline actually uses get copied into a curated library (`贴图素材库/`, folders named `{key}_{中文名}`), and all future lookups/additions go through it. See the "Curated texture library" section in `references/godot-glb-batch-processing.md` — includes the folder-lookup pitfall (keys contain underscores, so prefix matching collides; match on the ASCII part before the first CJK char).

## UV conventions user expects (发射塔/机房 project)

- **Hard surfaces** (walls / floors / ceilings / structure): 3m box projection (Cube Projection).
- **Ground / grass / outdoor**: 10m box to降低重复感.
- **Pipes / ducts**: try Follow Active Quads first (best for elbows); if stretch is bad or unwrap fails, fall back to 3m box. Don't insist on F-A-Q — pipe routing in Revit exports is messy.
- **Resolution**: 2K per material class.
- **Output**: `.glb` with embedded textures (NOT separate .bin+.png), original file untouched, write to a sibling `02_UV处理/` directory.

## Reading GLB without Blender

GLB is a 12-byte header + JSON chunk + BIN chunk. Pure-stdlib Python suffices for metadata:

```python
import json, struct
def glb_json(path):
    with open(path, 'rb') as f:
        magic, ver, total = struct.unpack('<4sII', f.read(12))
        assert magic == b'glTF'
        chunk_len, chunk_type = struct.unpack('<II', f.read(8))
        assert chunk_type == 0x4E4F534A  # 'JSON'
        return json.loads(f.read(chunk_len))
# then: data['materials'], data['meshes'], data['nodes'], data['textures'], data['images']
```

For per-material **face/vertex counts**, walk `meshes[].primitives[]`, group by `primitive['material']` index, and sum accessor `count`s (indices accessor for tris, position accessor for verts).

## Revit-export GLB quirks (verified on 发射塔/机房 project)

These bite every UV/材质 prep from Revit exports — call them out in your report:

1. **Same material name appears as many `materials[]` entries.** Revit splits slots per element. Always report BOTH `len(materials)` (slot count) and `len(set(names))` (unique-name count). UV work uses the unique count; the slot count is what gets merged.
2. **`unknown` material = element had no material assigned in Revit.** UV/贴图前必须人工指定。Flag every file containing `unknown` (yellow highlight in xlsx, ⚠ in md).
3. **`mep` is the default机电 material.** It lumps together风管/水管/桥架/设备. Recommend subdividing before贴图 (镀锌钢板 / PPR / PVC / 桥架…).
4. **幕墙 is most uniform** (glass + metal_alu + unknown) — ideal candidate for shared texture atlas across segments.
5. **Building by elevation segment** (0-40 / 50-90 / 100-145 / 150-176 / 181.5-265) has *similar but not identical* material mix — do not share UV atlas across segments, only within.

## Multi-format deliverable pattern

User typically wants md for self + xlsx or docx for同事. Generate all three from one data source:

- **Shared data module** (`glb_data.py`): walks files, returns `OrderedDict[category → [(name, slot_count, unique_count, unique_names), …]]`. Both generators import it.
- **xlsx** (openpyxl): one sheet, grouped rows, ⚠ column for unknown, subtotal row per group, grand-total row at bottom. Freeze pane at row 3. Column widths ≈ [42, 12, 12, 55, 14].
- **docx** (python-docx): title + overview table + per-category detail tables + "UV/材质制作建议" section. Highlight cells containing `unknown` with `set_cell_bg('FFF2CC')`. Chinese font: set both `w:eastAsia='微软雅黑'` and `font.name='Calibri'`.

## Pitfalls

- **Don't build a 32-row docx table in one huge python script.** Write the data module first, then a ≤3K-token generator that imports it. The 8K-token `write_file` ceiling hits fast with table logic.
- **`write_file` stream timeout**: the system warns "do not retry same large call" — decompose into data module + per-format generator, never paste the same payload twice.
- **brotlicffi ↔ urllib3 v2**: any script that hits HTTPS (requests, hf_hub, etc.) on this Windows Python 3.11 env may throw `decoder process called with data when 'can_accept_more_data()' is False`. Patch at top of script — see `scripts/brotli_urllib3_fix.py`.
- **Don't call `python-docx` cell `.text =` on a merged cell's non-anchor** — same MergedCell trap as openpyxl.
- **Verify both files open** before declaring done: `load_workbook(path)` and `Document(path)` round-trip; print sheet/paragraph/table counts.

## Reference files

- `references/revit-glb-quirks.md` — deeper dive on Revit GLB material duplication patterns & UV planning implications.
- `references/godot-glb-batch-processing.md` — the processing phase: Godot-safe constraints, Blender 5.1 batch quirks, color-tolerance tie trap, texture compression, curated texture library, verification pattern, and the delivery-tree reorg (consolidating flat `NN_UV处理_*` folders into `交付/` with continuous numbering while protecting pipeline-locked paths).
- `scripts/brotli_urllib3_fix.py` — runtime patch for brotlicffi/urllib3 v2 incompatibility.
- `scripts/normalize_tex.py` — run after every texture refill: classifies freely-named vendor maps (Poliigon/GSG/custom `_D/_N/_ARM`) into the standard `{key}_Color/NormalGL/Roughness/Metallic.jpg` set, unpacks ARM→Roughness (G) + Metallic (B), caps at 2048 JPEG q87. Metallic is USED (not skipped) when present. See "Texture refill & normalization" in `references/godot-glb-batch-processing.md`.
- `scripts/glb_data.py` — reusable parser + classifier template (drop into project, edit `classify()` for new building groupings).
- `scripts/inspect_glb_materials.py` — fingerprint-based material inspector. Prints per-slot name+color+PBR+tris AND groups by fingerprint. Use this whenever the user asks "what materials are in these GLBs" or before any UV/贴图 work.
- `scripts/inspect_generic.py` / `scripts/gen_unknown_generic.py` — project-side parameterized variants (`argv: glob_pattern, out_path`) for batch inspection of a whole building category and 待确认清单 generation. In the 20260807_GD project they live in `scripts/`; copy the pattern for new projects.
- `scripts/batch_inspect_rest.py` / `scripts/batch_decision_rest.py` (project-side) — multi-category loop wrappers: one run inspects + emits 决策表 for many building categories at once (each into its own `NN_UV处理_<类别>/` folder), auto-classifying greens→grass and pre-filling known classes. Reuse the loop pattern when front-loading many categories.
- `scripts/gen_xlsx.py`, `scripts/gen_docx.py` — starter generators; copy + restyle per project.
