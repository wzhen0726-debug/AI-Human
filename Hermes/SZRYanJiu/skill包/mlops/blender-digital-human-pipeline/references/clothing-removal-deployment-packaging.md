# Clothing Removal — Local Deployment & Packaging Research

Research session: 2026-07-08. Verified model sizes from HuggingFace file listings.

## Model Size Comparison (verified from HuggingFace)

| Model | Weight Size | Params | Framework | License | Best For |
|-------|------------|--------|-----------|---------|----------|
| SAM ViT-H | 2.4 GB | ~636M | PyTorch/ONNX | Apache-2.0 | Max accuracy, not for distribution |
| SAM ViT-B | 375 MB | ~91M | PyTorch/ONNX | Apache-2.0 | Good accuracy, medium package |
| **MobileSAM** | **40.7 MB** | 9.66M | PyTorch/ONNX | MIT | **Lightweight SAM distribution** |
| **SegFormer B0 Clothes** | **14.9 MB** | 3.72M | transformers/ONNX | MIT | **Smallest clothing-specific model** |
| SegFormer B2 Clothes | 109 MB | ~25M | transformers/ONNX | other* | Higher accuracy clothing parsing |
| SCHP (LIP) | ~250 MB | — | PyTorch+C++ext | MIT | Legacy, needs inplace_abn compile |
| PP-HumanSeg | 20-100 MB | — | PaddlePaddle | Apache-2.0 | Extra framework dependency |

*SegFormer B2 license is "other" — ATR dataset may be non-commercial. B0 is MIT.

## Key Insight: ONNX Runtime Eliminates PyTorch Dependency

Export any model to ONNX, then users only need `pip install onnxruntime` (15MB, pure C++ engine, MIT license, Windows/Linux/macOS, Python 3.11-3.14). No PyTorch (2GB+), no GPU required, no separate weight download.

**Recommended package: SegFormer B0 Clothes ONNX (14.9MB) + onnxruntime (15MB) = ~30MB total increment.**

SAM ONNX export:
```bash
python scripts/export_onnx_model.py \
    --checkpoint sam_vit_b_01ec64.pth --model-type vit_b \
    --output sam_onnx.onnx --return-single-mask
```

SegFormer B2 already has ONNX files in its HuggingFace repo (`onnx/` directory).

## Complete Pipeline — Only 1 External Dependency Point

| Step | Tool | External Dep |
|------|------|-------------|
| 1. Import + preprocess | Blender+bmesh | None |
| 2. Multi-view render (6-8 views) | Blender | None |
| **3. 2D AI segmentation** | **Python+onnxruntime+ONNX** | **onnxruntime+model weight** |
| 4. 2D→3D projection + multi-view voting | Blender+BVHTree | None |
| 5. Delete clothing faces | Blender+bmesh | None |
| 6. Hole repair (small: holes_fill, medium: Shrinkwrap to SMPL, large: SMPL transplant) | Blender+bmesh+Shrinkwrap | SMPL template .obj |
| 7. Post-process (hair removal, symmetrize) | Blender+bmesh | None |

## Non-AI Fallback: Rule-Based Multi-Feature Fusion

When no AI model is available, use color + curvature + normal + distance fusion:

- **Color** (most effective if texture exists): skin detection (R>G>B, 95<R<240, 40<(R-B)<80), delete non-skin non-hair regions. Fails on light-colored clothing.
- **Curvature**: hair/clothing edges = high curvature deviation from neighbor normals. Fails on flat clothing.
- **Normal direction**: clothing surface normals deviate from SMPL template normals. Same limits as distance threshold.
- **Distance from SMPL surface**: >5mm = clothing. Works for tight clothes, fails for loose (no body geometry underneath — Tripo is single-surface).

Fusion score = w1*color_confidence + w2*curvature + w3*normal_angle + w4*distance.
Expected accuracy: 50-70% (vs 75-85% with AI). Best used as a coarse first pass before AI refinement.

## Recommended Toolkit Structure

```
clothes-removal-toolkit/
├── blender_scripts/        # render_multiview, vote_and_delete, repair_holes, postprocess
├── ai_inference/           # segment.py + models/segformer_b0.onnx (14.9MB)
├── templates/              # smpl_body.obj
└── run_pipeline.py         # orchestrates Blender→AI→Blender via subprocess
```

User install: `pip install onnxruntime numpy pillow opencv-python` (~50MB). No PyTorch, no GPU, no weight download.

## EdgeSAM: Complete ONNX Deployment Alternative

Researched 2026-07-08 (second pass). EdgeSAM (`chongzhou96/EdgeSAM`, Apache-2.0)
provides **complete ONNX deployment** — both encoder AND decoder as ONNX, unlike
official SAM which only exports the decoder.

| File | Size |
|------|------|
| `edge_sam_3x_encoder.onnx` | 22.1 MB |
| `edge_sam_3x_decoder.onnx` | 15.9 MB |
| **Total** | **38 MB** |

- Speed: >30 FPS on iPhone 14, 40× faster than original SAM
- Precision: mIoU 2.3-3.2 higher than MobileSAM on COCO/LVIS
- CPU-usable (unlike SAM ViT-H which is impractical on CPU)
- License: Apache 2.0 (commercial-safe)

**Combined with LaMa ONNX (~50MB) for inpainting**:
EdgeSAM (38MB) + LaMa (50MB) + onnxruntime (20MB) = **~108MB total**
— no PyTorch, no GPU, no cloud API. Can be packaged as a Blender plugin.

LaMa is specialized for large-area image inpainting (removing clothing regions
from texture maps). Quality is high and speed is fast.

### When to use EdgeSAM vs SegFormer B0

- **SegFormer B0** (14.9MB): clothing-class-aware (18 categories), best for
  automatic pipeline where you need to know "this pixel = upper-clothes vs skin"
- **EdgeSAM** (38MB): general interactive segmentation, needs point/box prompts,
  but higher accuracy than MobileSAM. Best when combined with SCHP point prompts
  or when SegFormer's clothing parsing is insufficient for unusual garments.
- **Recommended**: SegFormer B0 as primary (automatic, tiny), EdgeSAM as upgrade
  path when accuracy is insufficient.

## SegFormer B0 vs B2 vs MobileSAM — When to Use Each

- **SegFormer B0** (14.9MB, MIT): Best for distribution. 18-class clothing parsing. ~65% mIoU, multi-view voting lifts to ~75-80%.
- **SegFormer B2** (109MB): Higher per-image accuracy (IoU 0.78-0.84 on clothes). Use when package size is acceptable.
- **MobileSAM** (40.7MB, MIT): General zero-shot segmentation, needs point/box prompts. Use when you need interactive segmentation or non-clothing objects. Not clothing-class-aware.
- **SAM ViT-B/H**: Only for local development where size doesn't matter. Not for distribution.
