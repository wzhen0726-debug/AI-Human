# Quad Remesher Mesh UV Failure Analysis (2026-07-20)

## Summary

On a 90K-face Quad Remesher character mesh, ALL Blender built-in UV unwrap
methods produce 2-3/10 quality scores (vision-verified via checkerboard texture).

## Test Matrix

| Method | Seams | Islands~ | Vision Score | Failure Mode |
|--------|-------|----------|:------------:|--------------|
| Smart UV 66° (default) | 760 | 914 | 2/10 | Body stretched, arms/legs invisible |
| Smart UV 89° (high angle) | 0 | 1983 | 2/10 | Even MORE islands |
| ANGLE_BASED + 5 seams | 2808 | 1125 | 2/10 | Body huge, arms near-zero |
| CONFORMAL (LSCM) + 5 seams | 6501 | 1196 | 2/10 | Same fragmentation |
| Cylinder projection | 0 | 4 | TERRIBLE | Body=vertical stripes, arms=horizontal |
| Manual projection | 0 | 1968 | 2/10 | Body sides stretched |
| ANGLE_BASED + UV stitch/merge | 3612 | 1157 | 2/10 | Merge collapsed islands |

## Root Cause

QuadRemesher creates a uniform quad grid where neighboring faces have slightly
different normals (not perfectly coplanar). ANY normal-based unwrap algorithm
splits at these non-coplanar edges, creating thousands of micro-islands.

The fragmentation is TOPOLOGY-DRIVEN, not parameter-driven:
- No amount of seam tuning fixes it
- Higher Smart UV angle (89°) creates MORE islands (1983 vs 914 at 66°)
- CONFORMAL (LSCM) produces same fragmentation as ANGLE_BASED
- Manual UV stitch/merge makes it WORSE (collapses distinct islands to points)

## Vision Analysis Excerpts

### Cylinder projection (4 islands)
"躯干: 棋盘格被严重地横向压缩、纵向拉伸，变成了细长的垂直条纹"
"双臂: 棋盘格被严重地横向拉伸，变成了水平的宽条纹"
Overall: "不可用 (Unusable)"

### Smart UV 66° (914 islands)
"四肢几乎完全呈现纯褐色，几乎看不到棋盘格"
"躯干呈现出巨大的、严重拉伸的灰色和白色色块"
Score: 2/10

### CONFORMAL + seams (1196 islands)
Same pattern: body has large stretched patches, arms/legs compressed to near-zero.

## xatlas External Test

xatlas (v0.0.11, pip install) tested as alternative:
- Cannot install into Blender's bundled Python
- Two-step workflow: OBJ export → xatlas in system Python → import UVs
- API returns 3-tuple `(vertex_map, face_map, uvs)`, NOT `vertex_array`
- Result: ~2000 islands, 3/10 score — slightly better but still unusable
- `texels_per_unit` PackOption didn't take effect

## Practical Recommendation

For BAKING (not direct texture painting):
- CONFORMAL unwrap + 5 anatomical seams → ~1196 islands
- 14.7% black pixels in bake (acceptable for pipeline)
- Island count doesn't affect bake quality significantly

For production-quality UVs on QR output:
- RizomUV (paid, $300+/yr) — professional unwrapper
- Manual seam marking in Blender UI (not background mode)
- Or: use template-wrap topology instead of QR (avoids the issue entirely)

## Mesh Details

- Model: Tripo AI T-pose character, 0.976m tall
- QR target: 100K quads → 90331 faces output (~180K triangles)
- Orientation: X=arm span, Y=body depth (face toward -Y), Z=height
- W=0.967, D=0.164, H=0.975
