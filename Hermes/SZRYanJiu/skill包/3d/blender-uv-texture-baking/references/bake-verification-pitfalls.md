# Bake Verification Pitfalls & Guards (2026-08-05 full-pipeline rerun)

Learnings from re-running the v3 QR delivery pipeline end-to-end (02 QR → 03 UV → 04 bake) and auditing the scripts.

## 1. Preview renders blue-purple ⇒ you're viewing the normal map, not a bad bake

When rewiring a baked material for a flat-lit preview (plug a texture into
Emission to exclude lighting), a node scan like:

```python
if n.type == 'TEX_IMAGE': tex = n   # WRONG: grabs the LAST image node
```

picks up the last TEX_IMAGE in the node tree — after a DIFFUSE+NORMAL bake
that is usually the **normal map**. The render then shows a uniform lavender
body ≈ RGB(128,128,255) with slight iridescent noise at high-curvature areas —
the classic tangent-space normal-map look.

**Fix**: lock the node by image name:

```python
if n.type == 'TEX_IMAGE' and n.image and 'Diffuse' in n.image.name: tex = n
```

Before concluding a bake is wrong, check the diffuse PNG pixels directly:
the non-black region (UV coverage) should be warm-toned for skin (R/G > 1,
e.g. 1.38); a normal map would average near (0.5, 0.5, 1.0).

## 2. Pre-bake alignment guard (must-have)

The low-poly survives FBX round-trips (Blender → QR → Blender) and can pick up
transforms; the high-poly is appended from the step-01 blend. If they are
misaligned, baking silently produces a shifted, useless texture.

Guard added to `04_bake.py`: compare world-space bounding boxes, abort loudly if

- center deviation > 5 mm, or
- size deviation > 1%.

Real rerun passed at center deviation 0.37 mm / size deviation 0.12%.

```python
def _wbbox(o):
    cs = [o.matrix_world @ v.co for v in o.data.vertices]
    mn = [min(c[i] for c in cs) for i in range(3)]
    mx = [max(c[i] for c in cs) for i in range(3)]
    return mn, mx
```

## 3. UV island counting — geometric BFS is wrong

BFS over `edge.link_faces` ignores UV seams entirely: on any connected mesh it
ALWAYS reports **1 island**, making the metric useless. Correct rule: two faces
sharing an edge belong to the same island only if the loop UVs match
(epsilon ~1e-6) at BOTH endpoints of the shared edge.

After the fix, the rerun reported 360 islands (largest 15,391 faces) instead of 1.

Headless probe: `scripts/verify_uv_island_count.py` — synthetic 2-island mesh
asserts new-algorithm=2 / old-algorithm=1, plus cube+smart_project >1.

## 4. Blender 5.1 render-API quirks hit during verification

- EEVEE enum: `scene.render.engine = 'BLENDER_EEVEE'` — 4.x's
  `BLENDER_EEVEE_NEXT` raises TypeError on 5.1.
- `Material.use_nodes` access emits a DeprecationWarning (removal expected in 6.0).
- For render-check cameras, use a TRACK_TO constraint
  (`TRACK_NEGATIVE_Z` / `UP_Y`) aimed at a target empty instead of
  hand-computed Euler angles.
