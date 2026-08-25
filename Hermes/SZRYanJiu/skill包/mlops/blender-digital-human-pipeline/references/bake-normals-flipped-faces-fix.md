# Bake Texture: Flipped Normals + Orientation Mismatch + Cage Tuning (2026-07-16/17)

## Problem #1: High-poly/Low-poly orientation mismatch (#1 cause of broken textures)

When the low-poly is rotated in the repair stage (arms along Y→X via bmesh vertex swap),
but the bake stage imports the ORIGINAL raw GLB as high-poly source, the high-poly is
STILL in original orientation (arms along Y). The two meshes are rotated 90° relative
to each other — bake rays miss entirely, producing 55-95% black pixels.

**Fix**: After importing the raw GLB in the bake stage, detect and rotate the high-poly
the SAME way the low-poly was rotated:
```python
for o in bpy.data.objects:
    if o.type == 'MESH' and 'Retopo' not in o.name and len(o.data.vertices) > 100000:
        xs = [v.co.x for v in o.data.vertices]
        ys = [v.co.y for v in o.data.vertices]
        if max(ys) - min(ys) > (max(xs) - min(xs)) * 2:
            bm = bmesh.new(); bm.from_mesh(o.data)
            for v in bm.verts:
                old_x, old_y = v.co.x, v.co.y
                v.co.x = old_y; v.co.y = -old_x
            bm.to_mesh(o.data); bm.free(); o.data.update()
```

Verify both meshes have the same bbox orientation before baking.
Without this fix, the user rated the bake "基本上完全不对" (basically completely wrong) —
a 10/100 score. With the fix + Cage, black pixels dropped from 55-95% to 14-16%.

## Problem #2: Flipped normals (43% on both meshes)

## Root Cause

**43% of faces on BOTH the high-poly and low-poly meshes had flipped normals** (normals pointing inward). The bake rays shoot along the low-poly normal direction — if the normal points inward, the ray shoots into the mesh interior and misses the high-poly surface, producing a black pixel.

Detection:
```python
import bmesh
bm = bmesh.new(); bm.from_mesh(obj.data)
flipped = sum(1 for f in bm.faces if f.normal.dot(f.calc_center_median()) < 0)
print(f"faces={len(bm.faces)}, potentially flipped={flipped} ({100*flipped/len(bm.faces):.0f}%)")
bm.free()
```

## Fix

> ⚠ CAVEAT (2026-08-06): global `normals_make_consistent` (Shift+N) is NON-DETERMINISTIC
> and dangerous on meshes with open boundaries, nested shells, or non-manifold edges —
> it can flip faraway correct regions (see `references/shiftn-normals-make-consistent-pitfalls.md`).
> The recalc below is only acceptable because BOTH meshes here still had ~43% genuinely
> flipped normals and the goal was to unify them pre-bake. If the input high-poly has
> ALREADY been normal-repaired (e.g. the 01-repair output, verified clean), do NOT
> re-run global recalc on it — treat those normals as ground truth and fix only the
> locally-edited ring.

Always recalculate normals before baking:
```python
for obj in [low_poly, high_poly]:
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
```

## Bake Distance Tuning Results

After fixing normals, black pixels decreased progressively with larger bake distances:

| Bake Distance | Black Pixels | Notes |
|--------------|-------------|-------|
| 0.02m (2% of model) | 55.9% | Way too small — many ray misses |
| 0.03m (3%) | ~40% | Still insufficient |
| 0.05m (5%) | 34.5% | Head/legs clear, torso still dark |
| 0.08m (8%) | 28.5% | Significant improvement |
| 0.12m (12%) | 28.5% | Diminishing returns, risk of back-face bleed |

**Recommended**: `max(0.005, model_size * 0.05)` — 5% of the largest bbox dimension. For a 1m-tall model, this is 0.05m. Increase to 0.08m if torso/pelvis areas still have black patches, but watch for back-face bleed-through.

## Smart UV Project vs Angle-Based Seams for Retopo Meshes

**Critical discovery**: The angle-based seam detection pipeline (55° threshold) produces only 65 angle seams on a Quad Remesher output (mostly flat, low-curvature quads) — insufficient for full UV coverage. Result: ~50% of the texture was empty black space.

**Fix**: Use `bpy.ops.uv.smart_project(angle_limit=math.radians(45))` instead of the angle-based seam pipeline for retopo meshes. Smart UV Project produces near-100% UV coverage (U[0.004, 0.996] V[0.004, 0.996]).

**Rule**: The angle-based seam pipeline works well on high-curvature meshes (scans, original AI models). For retopologized/quad-dominant meshes, use Smart UV Project.

## UV Strategy for Retopo Meshes — Critical Lessons (2026-07-16)

### Smart UV Project creates 841-894 islands on Quad Remesher output — UNUSABLE

**Discovery**: `bpy.ops.uv.smart_project(angle_limit=math.radians(45))` on a 224K-face Quad Remesher retopo mesh creates **841-894 UV islands** (measured by sampling 1000 UV positions and counting unique quantized coordinates). This produces 82-95% black texture pixels because each island is so tiny that bake rays miss most of them.

**Why**: Quad Remesher output is nearly-flat uniform quads with similar edge angles. Smart UV Project splits at nearly every angle discontinuity, creating thousands of tiny islands. Angle-based seam detection (55° threshold) produces too few seams (65) on the same mesh — the opposite extreme.

### Strategic seam approach — 8304 seams → 420 islands → 63.5% black

The best approach found: mark **only a few strategic seams** with very tight tolerance, then use Angle-Based Unwrap:

```python
# Only 4 seam types, tight tolerance (0.5% of width for X, 8% for Y):
# 1. Back center line (X≈mid, Y>0, hip→neck)
# 2. Crotch (X≈mid, Y<0, between legs)
# 3. Left armpit (X<0.3*min, Y<0, shoulder height)
# 4. Right armpit (X>0.3*max, Y<0, shoulder height)
```

Results: 8304 seams → 420 UV islands → 63.5% black pixels (down from 82-95%). UV range U[0.002, 0.980] V[0.002, 0.998] — full coverage.

### Ring cuts (neck/waist/ankle) with wide tolerance = CATASTROPHIC

An earlier attempt marked ring cuts at neck, waist, wrist, and ankle Z-heights with `height * 0.02` tolerance. This marked **128,820 edges as seams** — over half the mesh — collapsing every face into a separate UV island. The baked texture was 95.4% black (single-pixel dots). **Never use Z-band ring cuts with wide tolerance on retopo meshes** — they catch too many edges.

### Remaining black pixels (63.5% → needs further work)

Even with 420 islands and 0.12m bake distance, 63.5% black remains. The root cause is that the high-poly (1.9M faces, raw Tripo) and low-poly (224K faces, Quad Remesher retopo) surfaces don't perfectly coincide in the torso/pelvis region — the retopo surface is slightly offset from the original, causing ray misses. Potential fixes: larger bake distance (0.15m+), Cage baking, or using the voxel-remeshed model (34K, watertight, clean normals) as the high-poly source instead of the raw 1.9M model.

## Cage Baking — the winning configuration (2026-07-17)

For AI-generated high-poly (Tripo, 193万面) with internal surfaces and 43% flipped
normals, the optimal bake config is:
```python
bs.use_cage = True
bs.cage_extrusion = 0.3      # 30cm cage — generous
bs.max_ray_distance = 0.0    # let Cage fully control ray direction
bs.margin = 16
scene.cycles.samples = 128   # higher samples for cleaner result
```

Results progression:
| Config | Black Pixels |
|--------|-------------|
| No cage, 0.02m distance | 55.9% |
| No cage, 0.08m distance | 28.5% |
| No cage, 0.12m distance | 28.5% |
| Cage 0.15m extrusion | 19.2% |
| **Cage 0.3m extrusion, max_ray=0, 128 samples** | **14.7-16.1%** |

Combined with `normals_make_consistent(inside=False)` on both meshes. Remaining ~15%
black is from Tripo's internal surfaces that no ray can reach — would require high-poly
cleanup before baking. Image resolution: 2048×2048 (2K).

## Face count: quads vs triangles (2026-07-17)

Quad Remesher's `target_count` specifies QUAD count, not triangle count. A target of
200K produces 200K quads = ~400K triangles. The user requested "20万三角面" (200K
triangles) = ~100K quads. Set `target_count=100000` for 200K triangle output. Always
clarify with the user whether they mean quads or triangles when discussing face counts.
