# Eye Socket v42: Rendering + Contour Fitting Verification

> Session date: 2026-08-19. Updates to `run_eyeball.py` rendering + `socket_ops.py` contour alignment.

## 1. Workbench STUDIO lighting does NOT affect render output (Blender 5.1)

The `run_eyeball.py` render function used `BLENDER_WORKBENCH` + `scene.display.shading.light = 'STUDIO'`. STUDIO only affects the **viewport display**, not the render output. Workbench render output uses the scene's actual lights (or world background), which may be dark/unset.

**Fix**: switch to `BLENDER_EEVEE` + add three SUN lights:
```python
scene.render.engine = 'BLENDER_EEVEE'
for name, loc, energy in [("Key", (0, -1, 0.5), 120),
                           ("Fill", (0.5, 0.3, 0), 40),
                           ("Rim", (0, 1, 0.3), 60)]:
    ld = bpy.data.lights.new(name, type='SUN'); ld.energy = energy
    lo = bpy.data.objects.new(name, ld); lo.location = loc
    scene.collection.objects.link(lo)
```

## 2. World background color must set BOTH Color and Strength

Setting only `bg.inputs['Strength'].default_value = 0.8` without changing the Background node's default Color (black) renders everything dark. The EEVEE world background is black by default; strength 0.8 of black is still black.

**Fix**: also set the color:
```python
bg = scene.world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.6, 0.6, 0.6, 1.0)
    bg.inputs['Strength'].default_value = 0.8
```

## 3. Radial projection onto contour (vs nearest-point projection)

When constraining ring0 (rim boundary) vertices to a 3DDFA contour:

- **NEAREST-POINT projection** (BAD): For each vertex, find the closest discrete contour point and snap to it. Multiple vertices snap to the same point → clustering → jump max goes from 0.92mm to 6.8mm → new serration.

- **RADIAL projection** (CORRECT): Build a dense angle→radius lookup table from the contour polygon (sample each segment 16×). For each vertex, keep its angle θ = atan2(dz, dx), set its radius to r(θ) via linear interpolation from the lookup table. Vertices stay evenly distributed, contour shape is preserved.

```python
# Build (θ, r) table from contour polygon
for edge in contour_edges:
    for t in range(16):
        sx = p1 + (p2-p1)*t/16; sz = ... 
        samples.append((atan2(sz, sx), hypot(sx, sz)))
samples.sort()
thetas = [s[0] for s in samples]; radii = [s[1] for s in samples]

# For each vertex: keep angle, set radius
for v in ring0:
    theta = atan2(v.co.z - center.z, v.co.x - center.x)
    r_target = interp(theta, thetas, radii)  # linear, periodic
    v.co.x = center.x + r_target * cos(theta)
    v.co.z = center.z + r_target * sin(theta)
```

## 4. Diagnostic sampling window precision

When verifying rim position, sampling ALL vertices in the socket zone (dxz 3-18mm, y within ±1mm) includes **chamfer band vertices** (3mm outward expansion) and **skin vertices** — these are NOT part of ring0 and will always show "deviation" from the contour. This gave a false 82-96% deviation alarm.

**Correct method**: only measure ring0 vertices (the open-boundary ring before the bowl is sealed, or the vertices from the pipeline's own ring0 list). After the bowl is sealed, ring0 cannot be identified post-hoc; use the pipeline's in-line measurements (printed during make_eye_cup).

## 5. Laplace relaxation iteration scan (0/3/6/9/12, w=0.3)

| Iterations | Jump avg/max | Observation |
|---|---|---|
| 0 | 0.83/2.81mm | **Starburst topology** — vertices collapse inward |
| 3 | 0.46/1.07mm | Some serration remains |
| 6 | 0.45/1.01mm | Marginal improvement |
| 9 | 0.44/0.96mm | Diminishing returns |
| 12 | 0.44/0.92mm | **Optimal** — stable shape, radius unchanged from 9-iter |

Conclusion: relaxation is REQUIRED (0-iter = starburst), 12 iterations with w=0.3 is the inflection point.

## 6. PIL edge smoothness analysis (quantify serration from rendered image)

When vision_analyze is unavailable (503 errors), quantitatively assess edge smoothness from a rendered image:

```python
from PIL import Image
import numpy as np

img = Image.open("render.png").convert("L")
arr = np.array(img)
mask = arr < 80  # opening = dark pixels (background showing through)

# For each row, find left/right opening boundary
left_edges = []
for y in range(400, 700):
    row = np.where(mask[y])[0]
    if len(row) > 5:
        left_edges.append((y, row[0]))

# Direction reversal = serration indicator
xs = [x for y, x in left_edges]
dir_changes = sum(1 for i in range(len(xs)-2)
                  if (xs[i+1]-xs[i]) * (xs[i+2]-xs[i+1]) < 0)
serration_pct = dir_changes / (len(xs)-2) * 100
# < 30% = smooth; > 30% = serrated
```

## 7. User screenshot file-size check

Before analyzing a user's screenshot with vision_analyze, check the file size. A 8KB "screenshot" is actually a `[response interrupted]` placeholder image, not a real model screenshot. Real screenshots are 200KB+ (shaded) to 1.5MB+ (textured/rendered).

```python
import os
size = os.path.getsize(path)
if size < 50000:  # < 50KB = likely a placeholder
    print(f"WARNING: {path} is only {size} bytes — likely a placeholder, not a real screenshot")
```