# AI Texture Color Bleed Fix

> Verified 2026-07-29 on Tripo AI high-poly (8192×8192 basecolor)

## Problem

Tripo AI high-poly textures have skin-colored pixels bleeding into clothing
regions — especially at collar, inner thighs, and cuffs. This is NOT a bake
ray-penetration issue; the high-poly texture itself is defective.

## Detection

Sample UV-mapped pixels at problem regions:

| Region | Z range | X range | Skin % | Clothing % |
|--------|---------|---------|--------|------------|
| Collar | 0.72-0.82 | <0.1 | 55.2% | 21.6% |
| Groin | 0.3-0.45 | <0.08 | 58.9% | 15.3% |

If >50% of sampled pixels in a clothing area are skin-colored, the texture
is defective.

## Fix Script (system Python, NOT Blender Python)

```python
import numpy as np
from PIL import Image
from scipy import ndimage

img = Image.open('highpoly_tex.png')
arr = np.array(img)

# 1. Identify clothing (dark pixels)
r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
dark_mask = (r < 0.15*255) & (g < 0.15*255) & (b < 0.15*255)

# 2. Dilate clothing region (include boundary transition)
dark_dilated = ndimage.binary_dilation(dark_mask, iterations=10)

# 3. Find skin pixels within dilated clothing zone
skin_mask = (r > 0.4*255) & (g > 0.25*255) & (b > 0.15*255) & (r > g)
bleed = skin_mask & dark_dilated

# 4. Get clothing mean color
dark_mean = np.mean(arr[dark_mask], axis=0).astype(np.uint8)

# 5. Replace all bleed pixels with clothing mean color
fixed = arr.copy()
fixed[bleed] = dark_mean

# 6. Smooth transition edges
from scipy.ndimage import gaussian_filter
transition = ndimage.binary_dilation(bleed, iterations=3) & ~bleed
for c in range(3):
    blurred = gaussian_filter(arr[:,:,c].astype(float), sigma=1)
    fixed[:,:,c] = np.where(transition, blurred.astype(np.uint8), fixed[:,:,c])

# 7. Save
Image.fromarray(fixed).save('highpoly_tex_fixed.png')
```

## Result

- Before: 229,644 bleed pixels in clothing zone
- After: 2,674 bleed pixels (98.8% reduction)

## Integration with bake pipeline

1. Run this fix on the high-poly texture BEFORE baking
2. Load the fixed texture into the high-poly material:
   ```python
   new_img = bpy.data.images.load('highpoly_tex_fixed.png')
   node.image = new_img
   ```
3. Bake normally with `cage_extrusion=0.005, max_ray_distance=0.01`

The small cage/ray values prevent any residual penetration, while the texture
fix eliminates the source of the skin-colored bleed.
