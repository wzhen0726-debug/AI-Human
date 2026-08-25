# Revit-export GLB quirks (verified 2026-08-07 on 发射塔/机房项目)

Source: `原始glb/assembled_nomerge/*.rvt.glb`, 32 files covering 发射塔楼 / 发射机房 / 配电机房.

## 0. Fingerprint-based dedup (added 2026-08-07 after user correction)

**Never trust `material.name` alone.** Revit's GLB writer dedups by `(name, baseColorFactor, metallic, roughness)` — not by name. Verified numbers from 2-发射机房:

| File | slots | unique names | unique fingerprints |
|---|---|---|---|
| 2_发射机房_发射机房设备 | 4  | 4 | 4 |
| 2_发射机房_建筑         | 20 | 7 | **18** (only 2 pairs真重复) |
| 2_发射机房_暖通         | 11 | 3 | **11** (every slot unique) |
| 2_发射机房_电气         | 4  | 2 | 4 |
| 2_发射机房_给排水       | 12 | 3 | **11** |

Two failure modes:

1. **Same name, different fingerprint** — `2_发射机房_暖通` has 6 entries all named `mep` but with base colors `#00FF00FF / #FFCC79FF / #800000FF / #BF7EFFFF / #00FFFFFF / #FF00FFFF`. Each is a *different* pipe type (different system in Revit). Merging by name destroys the color coding.
2. **Different name, same fingerprint** — `2_发射机房_建筑` has `#FFFFFFFF met=0 rough=0.8` under three names: `metal_alu`, `plaster`, `unknown`. These three are *visually identical* (white) but semantically different classes.

**Rule**: report and process per fingerprint. Group by name only as a second pass within the same fingerprint.

## 1. Same material name → many `materials[]` entries

Revit exports one slot per element instance, not per unique material. Examples from this project:

| File | slots | unique names |
|---|---|---|
| 2_发射机房_建筑 | 20 | 7 |
| 3_配电机房（含主题墙）_建筑 | 19 | 7 |
| 1_发射塔0.000-40.000m_建筑 | 10 | 5 |
| 1_发射塔181.500m-265.000m_钢构 | 3 | 1 (steel) |

**Implication for UV/贴图**: in Blender, run "Material Utils → Merge by name" (or write a remap script) *before* unwrapping, otherwise the same texture gets drawn N times across N slots. **But** — see §0 — merge by *fingerprint*, not by name, when colors differ.

## 2. `unknown` material = unassigned in Revit

幕墙 / 电气 / 给排水 files are the worst offenders. These meshes have NO真实材质 in Revit — someone has to decide what they actually are (metal? plastic? glass?) in DCC. Flag every occurrence in the report so the UV artist knows to ask.

For 2-发射机房, 13 unknown entries were found. Three biggest (by 面数):
- `暖通.rvt.glb mat_03` `#F2F2F2FF` **261,198 tris** — near-certainly空调箱外壳 or 风管
- `电气.rvt.glb mat_01` `#80FFFFFF` 9,152 tris — likely桥架
- `电气.rvt.glb mat_02` `#FFFFFFFF` 7,400 tris — likely配电柜

Use the unknown-feedback-loop template (see SKILL.md) to get these classified by the user before贴图.

## 3. `mep` is the default catch-all for机电

暖通 / 给排水 / 电气 / 设备 all lean on `mep` as the default. It conflates:
- 风管 (镀锌钢板)
- 水管 (PPR / PVC / 钢)
- 电缆桥架 (喷塑钢)
- 设备外壳 (喷漆钢)

**Within one file**, `mep` is color-coded by system. From `2_发射机房_给排水` (7 distinct mep fingerprints):

| hex | count | likely system |
|---|---|---|
| `#FF00FFFF` 品红 | 334,731 tris | 消防 (dominant) |
| `#FF0000FF` 红 | 53,889 | 消防 |
| `#FFFF00FF` 黄 | 44,263 | 燃气? |
| `#00FF00FF` 绿 | 26,292 | 给水 |
| `#993333FF` 暗红 | 11,700 | 污水? |
| `#999900FF` 橄榄 | 7,132 | ? |
| `#FF9966FF` 橙 | 1,693 | ? |

**Do not** treat these as one material for texturing — but per the runtime contract, do not add albedo either. They are param-only.

## 4. 幕墙 is the most uniform

All 4 幕墙 files use exactly `glass + metal_alu + unknown`. Best candidate for a shared 2K texture atlas across the whole tower.

## 5. 建筑 by elevation segment — DO NOT share atlas across segments

| Segment | materials |
|---|---|
| 0.000-40.000m | brick, concrete, glass, steel, unknown |
| 50.000-90.000m | brick, glass, steel, unknown |
| 100.000-145.000m | brick, glass, steel, unknown |
| 150.000-176.000m | brick, concrete, glass, metal_alu, steel, unknown |
| 181.500-265.000m | brick, concrete, metal_alu, steel (no glass/unknown) |

Mix varies *within* similarity. Sharing a texture atlas across segments will stretch / misalign. Share within a segment only.

## 6. 钢构 is always just `steel`

5 files, all single-material `steel` (one has 3 slots all named steel). Easiest UV job — single tiling PBR steel texture, no atlas needed.

## 7. Runtime contract (from `原始资料/材质命名.txt`)

If the GLB is fed to a runtime `MaterialRemapper` (Unreal/Unity-side name-based swapper):

- `RemapAll` swaps whole materials by category name → `Resources/Materials/{类别}.ires`.
- `material_overrides.json` swaps by *full material name* (`steel.001` only swaps that one).
- `mep / plastic / glass`: runtime only adjusts `roughness/metallic/alpha`, **never swaps the material** — preserves baseColorFactor (机电分色).
- Materials with `albedo_texture` already set: runtime **skips forever**.
- `unknown`: runtime never touches.

**DCC-side consequences**:
- Adding an albedo texture locks that material out of `RemapAll`. Do it deliberately.
- For param-only classes, only adjust PBR scalars — never attach textures, never unwrap (except lightmap UV if needed).
- `baseColorFactor` must survive every edit; multiply albedo against it, don't replace.

## 8. 素材库 naming convention (user's local library)

`原始资料/贴图素材/` (or `F:\NWT\李小龙\cztu` on the older project) directories follow:

```
{序号}.{中文用途}{glb材质名(可带.00N后缀)}_{颜色代码}/
   ├── Concrete046_2K-PNG_Color.png
   ├── Concrete046_2K-PNG_NormalGL.png
   ├── Concrete046_2K-PNG_Roughness.png
   ├── Concrete046_2K-PNG_Displacement.png
   └── (occasionally) Concrete046_2K-PNG_AmbientOcclusion.png
```

Match to GLB materials by **(hex color, class)** pair. The `.00N` suffix in the dir name refers to an *old* export's material index and won't match the current GLB's indices — ignore it. Most sets are Poly Haven CC0 2K PBR.
