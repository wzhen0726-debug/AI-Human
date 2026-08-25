# Chest Region Fix: 3-Step Normal Flip + Merge + Smooth (2026-08-03)

## Discovery
Diagnosis of Tripo 1.93M-face model (z=1.20~1.40m chest area) revealed two root causes for the "bumpy/messy" look:

| Problem | Scale | Effect |
|---------|-------|--------|
| **Inward-facing normals** | 49,328 faces (17.5%) | Dark patches, weird shadows |
| **Tiny faces <0.5mm²** | ~125K faces (44%) | Sawtooth/锯齿 surface |

Smooth alone can't fix these — the render looks unchanged after smooth.

## 3-Step Fix

### Step A: Flip inward normals
Chest is convex — test face_center-to-body_center dot normal:
```python
center = Vector((bbox_center.x, bbox_center.y, z_mid))
for f in chest_faces:
    outward = f.calc_center_median() - center
    if outward.length > 1e-8 and f.normal.dot(outward) < 0:
        f.normal_flip()
```

### Step B: Merge tiny faces (NOT delete+fill_holes)
**CRITICAL**: `bmesh.ops.delete` + `bmesh.ops.holes_fill` HANGS on 2M-face models with ~50K holes. Use `remove_doubles` on the region's verts instead:
```python
chest_verts = [v for v in bm.verts if z_min <= v.co.z <= z_max]
bmesh.ops.remove_doubles(bm, verts=chest_verts, dist=0.00015)  # 0.15mm
```
This merges tiny-face vertices, dissolving tiny faces without creating holes. Normal faces (edge ~1mm) unaffected.

### Step C: Regional Laplacian smooth
Standard bmesh Laplacian (same as sculpt smooth brush), iterations=5, strength=0.3

## Results
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Inward normals | 49,328 (17.5%) | 1,926 (0.7%) | ↓96% |
| Tiny faces <0.5mm² | ~21,700 | 15,686 | ↓28% |
| Surface smoothness (pixel diff) | 0.59 | 0.32 | ↓46% |
| Non-manifold edges | 2 | 6 | OK (< 50) |

## Pitfalls
1. **holes_fill hang**: NEVER delete tiny faces + fill holes on 2M-face models
2. **Convex-only**: normal flip dot-test only works for convex surfaces (chest, abdomen)
3. **Temp file naming**: avoid `bisect.py` in Temp — shadows stdlib, breaks PIL
4. **Vision QC**: downscale RGBA PNG to 960×540 RGB JPEG before vision_analyze

## Diagnosis snippet
```python
chest_faces = [f for f in bm.faces if 1.20 <= f.calc_center_median().z <= 1.40]
center = Vector((0, 0, 1.30))
inward = sum(1 for f in chest_faces if f.normal.dot(f.calc_center_median()-center) < 0)
tiny = sum(1 for f in chest_faces if f.calc_area() < 0.5e-6)
print(f"Inward: {inward}/{len(chest_faces)} ({inward*100//len(chest_faces)}%)")
print(f"Tiny: {tiny}/{len(chest_faces)} ({tiny*100//len(chest_faces)}%)")
```

## ⚠️ CRITICAL OUTCOME WARNING (same session, later)
This 3-step fix was **REJECTED by the user after visual inspection**, despite the numbers above:
- The z=1.20~1.40 wide-band normal flip ALSO flipped legitimate inward normals elsewhere → neck root deformed **+16.7mm** vs raw
- The regional smooth/merge on a wide z-band pushed the belly to **+44mm** displacement ("肚子上还出现了新错误")
- User: "别雕刻了" (stop sculpting) + "翻翻之前的做法" (use the shipped pipeline, not experimental steps)

**Do NOT integrate this as a wide-band pipeline step (7.6).** The correct pattern is:
1. Rebuild clean from raw GLB (rotation + weld + non-manifold only)
2. Diagnose the artifact precisely FIRST (boundary edges? inward normals? tiny faces? real protrusion?)
3. Apply ONE narrow targeted op per artifact; verify neighbors + raw deviation <1mm outside zone

The ONLY piece that survived user review is the **local belly normal flip** — see `references/belly-area-inward-normals-repair.md` (narrow zone, normals only, no geometry change). The `holes_fill` hang and convex-only dot-test pitfalls below remain valid.

## Integration
Original intent: add to repair_pipeline as step 7.6 — **DO NOT DO THIS** (see warning above).