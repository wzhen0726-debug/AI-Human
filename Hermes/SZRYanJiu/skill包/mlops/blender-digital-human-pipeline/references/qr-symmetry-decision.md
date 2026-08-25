# QR Symmetry Decision — No SymAxis for Asymmetric Textures

> Date: 2026-08-01
> User decision: do NOT use SymAxis=X for models with asymmetric clothing textures.

## Problem

`SymAxis=X` in RetopoSettings.txt forces Quad Remesher to produce mirror-symmetric topology (left/right identical quads). This is good for Mixamo auto-rigging (symmetric bone detection), but **breaks when the source model has asymmetric textures**.

## Symptom

- QR produces 100% symmetric topology (L/R vertex counts identical)
- Bake produces correct textures on one side, mirrored/wrong textures on the other
- The asymmetric clothing pattern (different left/right designs) gets overwritten by the symmetric topology

## Decision

**Do NOT write `SymAxis=X` or `SymLocal=1` in RetopoSettings.txt for models with asymmetric textures.**

```python
# In RetopoSettings.txt — omit these lines for asymmetric models:
# SymAxis=X
# SymLocal=1
```

## Trade-off

| With SymAxis=X | Without SymAxis |
|----------------|-----------------|
| Perfect L/R symmetric topology | Natural asymmetric topology |
| Mixamo bone detection easier | Mixamo may have slight bone offset (<5mm) |
| Textures break (mirrored) | Textures correct |
| Weight painting symmetric | Weight painting may need manual L/R adjustment |

## When to Use SymAxis

- Model is truly symmetric (T-pose, symmetric clothing)
- No textures yet (will be created after retopo)
- Planning to do manual symmetric weight painting anyway

## When to Skip SymAxis

- Model has asymmetric clothing (different left/right patterns)
- Textures already exist and are asymmetric
- User explicitly says no symmetry (e.g., "我不需要对称啊")

## Results

| Metric | With SymAxis | Without SymAxis |
|--------|-------------|-----------------|
| L/R vertex count | 70,732 = 70,732 (100% sym) | 71,163 ≠ 70,092 (natural) |
| Texture correctness | Broken (mirrored) | Correct |
| Triangles | 283,194 | 283,194 |
| Quad ratio | 100% | 100% |
| Non-manifold | 0 | 0 |

## Implementation

In `02_qr_auto.py`, conditionally write SymAxis:

```python
# Only add SymAxis if model is symmetric AND user wants it
if use_symmetry:
    f.write('SymAxis=X\n')
    f.write('SymLocal=1\n')
# else: omit both lines
```

Default: **off** (no symmetry) for AI-generated models with textures.
