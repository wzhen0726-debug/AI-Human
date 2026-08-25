# Auto-Rigging Tool Packaging Research (2026-07-09)

## Context
Researching which body auto-rigging tools (skeleton placement + skinning weights,
no face BlendShape, no control rig — pure deformation skeleton for game engines)
can be **packaged into a local/offline toolkit** and distributed to others.

## Tool Comparison Matrix

| Tool | Type | Skeleton | Weights | Packagable | License | Quality |
|------|------|----------|---------|------------|---------|---------|
| **Mixamo** | Adobe online service | Auto (ML) | Auto | ❌ No | Proprietary | Medium |
| **Auto-Rig Pro** | Blender addon (paid) | Auto | Auto | ❌ No (per-user license) | Commercial | High |
| **Rigify** | Blender built-in | Semi-auto (metarig) | ❌ No (Blender auto-weights separate) | ✅ Yes (GPL) | Med skeleton / Med weights |
| **AccuRIG** | Reallusion free standalone app | Auto | Auto | ❌ No (standalone app, not a library) | Free proprietary | High |
| **RigNet** | Python research code (open source) | Auto (neural net) | Auto (neural net) | ✅ Yes (GPL v3) | Medium (research-grade) |
| **Puppeteer / MagicArticulate** | Python research code (open source) | Auto (Transformer) | Auto | ✅ Yes (open source) | Medium-High (SOTA) |
| **3DAIGC-API** | Python + Docker (integrates UniRig) | Auto | Auto | ✅ Yes (self-hosted) | Open source | Medium |

## Key Findings

### Mixamo — CANNOT be packaged
- Pure Adobe web service (www.mixamo.com). Auto-rigger runs ML on **server-side**.
- **No public API, SDK, or CLI.** Must use browser: upload → wait → download.
- Adobe provides no offline version. Mixamo is in maintenance mode (no new features).
- Source: Wikipedia "Mixamo" — "cloud-based service offering animations and automatic character rigging"; auto-rigger "applies machine learning to understand where the limbs of a 3D model are."
- **Implication**: Any pipeline document that lists Mixamo as a "free fallback" must note it requires internet + Adobe account + manual browser interaction. It cannot be automated or scripted.

### Rigify — Does NOT compute skinning weights
- Blender official docs (docs.blender.org, Rigify > Introduction) explicitly state:
  > "Rigify only automates the creation of the rig controls and bones. It does not attach the rig to a mesh, so you still have to do skinning etc. yourself."
- To get weights: select mesh + armature → `bpy.ops.object.parent_set(type='ARMATURE', use_auto_weights=True)` — this uses Blender's heat diffusion algorithm (medium quality, may need manual cleanup at shoulders/elbows/knees).
- **Implication**: Rigify alone is not a complete auto-rigging solution. It must be paired with Blender's built-in auto-weights or an external weight calculator.

### Auto-Rig Pro — Cannot be distributed
- ~$50 Blender addon, license tied to individual Blender Market / Superhive account.
- Excellent quality + has Game Rig Tools module for engine export (bone renaming, deformation-skeleton-only export, UE5 Mannequin / Unity Humanoid naming).
- **Can be used personally** but **cannot be packaged or redistributed** in a toolkit for others.

### AccuRIG — Free but standalone
- Reallusion's free auto-rigging desktop application (actorcore.reallusion.com/auto-rig/accurig).
- 210,000+ users. Automatic skeleton + optimized skin weights + joint refinement.
- Exports to all major 3D platforms (FBX, GLB).
- **Cannot be packaged** as a library/Python module — it's a standalone GUI application.
- Advanced features (multi-mesh, skin weight editing) require Character Creator 4.1 (paid).

### RigNet — Best open-source Python option (packagable)
- **GitHub**: https://github.com/zhan-xu/RigNet (1.5k stars, 205 forks)
- **Paper**: SIGGRAPH 2020 "RigNet: Neural Rigging for Articulated Characters"
- **Input**: OBJ mesh (must be simplified to 1K-5K vertices via quadratic edge collapse)
- **Output**: `_rig.txt` containing joints (name + XYZ), hierarchy, root, skinning weights per vertex
- **Tech**: Graph Convolutional Network predicts joint positions → minimum spanning tree builds hierarchy → neural net predicts skinning weights
- **Environment**: Python 3.7+ / PyTorch 1.12 / PyTorch Geometric / CUDA GPU
- **License**: GPL v3 — **can be packaged and distributed**
- **Blender integration**: Two community Blender addons exist (@pKrime, @L-Medici)
- **Limitations**: mesh must be pre-simplified; results have randomness (slightly different each run); primarily tested on humanoid/animal shapes; requires GPU

### Puppeteer / MagicArticulate — SOTA open-source (packagable)
- **Puppeteer**: https://github.com/Seed3D/Puppeteer (407 stars, NeurIPS 2025 Spotlight)
  - Full pipeline: rigging (skeleton + skinning) + video-guided animation
  - `export.py` exports rigged mesh to FBX via `bpy==4.2.0`
  - Environment: Python 3.10, PyTorch 2.1, flash-attn 2.6.3, pytorch3d
- **MagicArticulate**: https://github.com/Seed3D/MagicArticulate (412 stars, CVPR 2025)
  - Skeleton generation only (autoregressive transformer formulates skeleton as sequence)
  - Only 4.6 GB VRAM, 1-2 seconds per inference
  - Dataset: Articulation-XL2.0 (48K+ 3D models with high-quality articulation annotations)
  - Supports non-humanoid characters (animals, objects)
- **License**: Open source — **can be packaged**
- **Limitations**: Complex environment setup (flash-attn compilation is notoriously difficult); research-grade code, not production-stable

### 3DAIGC-API — Docker-deployable auto-rigging service
- **GitHub**: https://github.com/FishWoWater/3DAIGC-API (48 stars)
- FastAPI backend integrating multiple 3D AI models including **UniRig** (automatic rigging, 9GB VRAM)
- Docker deployment: `docker compose up -d` — one command
- Also includes mesh segmentation (PartField, P3SAM), texture generation, UV unwrapping
- **Can be self-hosted** as a local REST API service
- **Limitations**: Requires Linux + CUDA GPU; UniRig model details not separately documented

## Recommendation by Use Case

| Use Case | Recommended Tool | Why |
|----------|-----------------|-----|
| Self-use, fast results | Auto-Rig Pro (if owned) | Best quality, direct engine export |
| Package for others, simple reliable | Rigify + Blender auto-weights + Python rename script | Zero dependencies, ships with Blender |
| Package for others, AI-automated high quality | Puppeteer / MagicArticulate | SOTA quality, open source, supports non-humanoid |
| Package as API service | 3DAIGC-API + Docker | REST API, self-hosted, scalable |
| Quick one-off, no setup | AccuRIG (standalone app) | Free, GUI, good quality |

## Rigify-to-Engine Scripted Pipeline (packagable)

```python
# Conceptual flow — Rigify + auto-weights + rename + export
# 1. Add metarig, adjust bone positions (scripted or preset)
# 2. bpy.ops.pose.rigify_generate()  → generates full control rig
# 3. Select mesh + armature
# 4. bpy.ops.object.parent_set(type='ARMATURE', use_auto_weights=True)  → heat diffusion weights
# 5. Delete control bones, keep deformation bones only
# 6. Rename bones to engine naming convention (UE5: root, pelvis, spine_01...; Unity: Hips, Spine, LeftArm...)
# 7. bpy.ops.export_scene.fbx(filepath='output.fbx', ...)
```

**Known issues with Rigify → engine**:
- Default bone names are Rigify-specific (`torso`, `upper_arm.L`), not engine-standard
- Need Game Rig Tools (community addon) or manual rename script
- Auto-weights (heat diffusion) quality is medium — shoulders/elbows/knees may need manual cleanup
- For UE5: also need to match Mannequin bone hierarchy for retargeting

## Sources
- Mixamo Wikipedia: https://en.wikipedia.org/wiki/Mixamo
- Rigify docs: https://docs.blender.org/manual/en/latest/addons/rigging/rigify/introduction.html
- AccuRIG: https://actorcore.reallusion.com/auto-rig/accurig
- RigNet: https://github.com/zhan-xu/RigNet
- Puppeteer: https://github.com/Seed3D/Puppeteer
- MagicArticulate: https://github.com/Seed3D/MagicArticulate
- 3DAIGC-API: https://github.com/FishWoWater/3DAIGC-API
- EA dem-bones (LBS extraction, C++): https://github.com/electronicarts/dem-bones
