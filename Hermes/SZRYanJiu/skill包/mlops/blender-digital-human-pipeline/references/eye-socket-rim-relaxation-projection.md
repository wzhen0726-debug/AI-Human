# Rim Relaxation & Contour Projection (v41-v42, 2026-08-19)

User feedback "rim 不符合眼睑轮廓" (GUI shading screenshot showed opening drooping to eye-bag position). Diagnosis + fix chain below.

## 1. Root cause: Laplace relaxation distorts rim away from 3DDFA contour

After v41 (margin→0), `check_rim_vs_3ddfa.py` measured rim→3DDFA deviation **avg 6.4mm / max 14.7mm**. Worst vertices at z=-17.9mm (below the lower lid, into eye-bag territory). The rim0 ring comes from the input mesh's open boundary edges, NOT directly from the 3DDFA contour — Laplace smoothing then drifts these vertices outward.

**Key measurement pitfall**: `check_rim_xz.py` reported "82-96% of rim vertices deviate" — this was a **false alarm**. The script sampled ALL vertices in the eye zone (dxz 3-18mm, depth <1mm), which includes chamfer-band vertices that are *supposed* to be outside the contour. **Measuring rim accuracy must only use ring0 itself**, not surrounding vertices.

## 2. Relaxation iteration sweep (0/3/6/9/12 times, weight 0.3)

| Iterations | jump avg/max | Result |
|---|---|---|
| 0 | 0.83/2.81mm | **Starburst topology**: rim vertices collapse to center, mesh breaks |
| 3 | 0.46/1.07mm | Still jagged |
| 6 | 0.45/1.01mm | Slight improvement |
| 9 | 0.44/0.96mm | Diminishing returns |
| 12 | 0.44/0.92mm | Optimal, shape stable |

**Relaxation is mandatory** (0 iterations = starburst collapse). 12 iterations is the payoff knee. Contour densification 24→48→72 points gives no additional benefit (jump unchanged).

## 3. Projection: nearest-point FAILED → radial projection SUCCEEDED

### Failed: nearest-point projection
Snap each ring0 vertex to nearest 3DDFA contour discrete point → multiple vertices cluster onto the same point → **jump max spiked to 6.8mm** (was 0.92mm before projection). Created new, worse jaggedness.

### Working: radial projection
Densify contour polyline (16 subdivisions per segment) → build angle θ→radius r(θ) interpolation table → for each ring0 vertex, **keep its angle θ, set radius = r(θ)**. Vertices stay uniformly distributed, shape strictly follows contour.

```python
# Build θ→r table from contour points (relative to eye center)
_samples = []
for i in range(n):
    p1, p2 = pts[i], pts[(i+1)%n]
    for t in range(16):
        f = t/16
        sx = p1[0]+(p2[0]-p1[0])*f; sz = p1[1]+(p2[1]-p1[1])*f
        _samples.append((math.atan2(sz, sx), math.sqrt(sx*sx+sz*sz)))
_samples.sort()
_thetas = [s[0] for s in _samples]; _radii_tab = [s[1] for s in _samples]

# Project each vertex: keep angle, set radius from interpolation
for v in ring0:
    dx = v.co.x - center.x; dz = v.co.z - center.z
    theta = math.atan2(dz, dx)
    r_target = _radius_at(theta)  # bisect + periodic interpolation
    v.co.x = center.x + r_target * math.cos(theta)
    v.co.z = center.z + r_target * math.sin(theta)
```

Result: only 12/70 (L) + 6/69 (R) vertices moved (>0.5mm threshold) — confirms most ring0 vertices were already within 0.5mm of the contour after relaxation; only outlier vertices needed correction.

## 4. v42 final metrics

| Metric | L | R |
|---|---|---|
| rim radius | [3.9,13.8] avg 8.7mm | [3.4,13.6] avg 8.6mm |
| jump avg/max | 0.50/1.24mm | 0.49/1.11mm |
| still wrong | 0 | 0 |
| dark pixels (<60) | 0% | 0% |
| skin RGB | (222,192,178) | (219,189,175) |

## 5. PIL edge-smoothness analysis (when vision unavailable)

Gemini vision was 503 all day. PIL pixel analysis substituted:
- **Direction-reversal rate**: left 4% / right 12% (< 30% threshold = smooth)
- **Edge jump avg**: left 1.3px / right 2.7px (sub-pixel, no jaggedness)
- **Opening aspect ratio**: 2.7:1 (matches 3DDFA fissure 2.8:1)
- **Opening centroid offset**: 16/19px from image center (~1-2mm, essentially centered)

Also: **user screenshots must be checked for file size before vision analysis**. An 8KB file is a "[response interrupted]" placeholder, not a model screenshot — analyzing it wastes multiple vision calls.

## 6. Lessons

1. **Discrete nearest-neighbor projection clusters continuous rings** — use angle-parameterized interpolation (radial projection) instead.
2. **Relaxation and shape preservation trade off**: pure relaxation drifts, pure contour starbursts; relaxation + radial projection achieves both.
3. **Diagnostic script sampling windows must be precise**: including chamfer-band vertices in "rim" measurement produces false 82-96% deviation alarms.
