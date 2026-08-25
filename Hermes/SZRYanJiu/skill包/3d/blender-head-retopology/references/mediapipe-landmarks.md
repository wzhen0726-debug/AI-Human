# MediaPipe Facial Landmark Reference

## Key Points (12, used for centroid alignment)
| Name | MP Index | Template Vertex |
|------|----------|-----------------|
| nose_tip | 1 | 7883 |
| right_eye_inner | 133 | 4395 |
| right_eye_outer | 33 | 7219 |
| left_eye_inner | 362 | 2791 |
| left_eye_outer | 263 | 2772 |
| right_mouth_corner | 61 | 6600 |
| left_mouth_corner | 291 | 2299 |
| chin | 199 | 8023 |
| forehead | 10 | 7694 |
| nose_bridge | 6 | 7878 |
| right_brow | 105 | 4274 |
| left_brow | 334 | 72 |

## Contour Points (81, for anchor anchoring)
### Right Eye (16, MP indices: 33,7,163,144,145,153,154,155,133,173,157,158,159,160,161,246)
Template vertices matched via KDTree nearest-neighbor (2cm threshold).

### Left Eye (16, MP indices: 362,382,381,380,374,373,390,249,263,466,388,387,386,385,384,398)

### Outer Lip (20, MP: 61,185,40,39,37,0,267,269,270,409,291,375,321,405,314,17,84,181,91,146)
Only ~8/20 match template vertices (2cm threshold) due to template sparsity.

### Inner Lip (20, MP: 78,191,80,81,82,13,312,311,310,415,308,324,318,402,317,14,87,178,88,95)
~17/20 match template vertices.

### Nose Ala (9, MP: 49,131,134,51,3,248,281,279,440)
~3-4/9 match. mp280 excluded (Y=-75.5mm vs median -100.8mm, 25mm outlier).

## Excluded Groups
### Eyebrows (10+10, MP: 70,63,105,66,107,55,65,52,53,46 / 300,293,334,296,336,285,295,282,283,276)
Y range 16-22mm, unreliable 3D mapping. Excluded from anchors.

## Filtering Strategy
For each contour group with ≥4 points:
1. Sort by Y coordinate, compute median
2. Discard points with |Y - median| > 15mm
3. Recompute median and repeat

## Geometric Points (computed from scan extrema, verification only)
- top_of_head: Z max region center
- back_of_head: Y max region center
- back_neck: Y max + Z min region
- left/right_ear_top/mid/bottom: X extrema near eye Z height

## Template Vertex Landmarks
```json
{
  "nose_tip": 7883, "left_eye_inner": 2791, "left_eye_outer": 2772,
  "right_eye_inner": 4395, "right_eye_outer": 7219,
  "left_mouth_corner": 2299, "right_mouth_corner": 6600,
  "chin": 8023, "nose_bridge": 7878, "forehead": 7694,
  "left_brow": 72, "right_brow": 4274,
  "top_of_head": 5187, "left_ear_top": 983, "left_ear_mid": 996,
  "left_ear_bottom": 966, "right_ear_top": 5349, "right_ear_mid": 5307,
  "right_ear_bottom": 5256, "back_of_head": 7730, "back_neck": 6027
}
```

## Coordinate System
- Scan: Z-up, face direction -Y, centered at origin
- Template: Z-up, face direction -Y, centered at origin (same as scan)
- MediaPipe best view: -Y (478 landmarks detected)
- No rotation needed between models