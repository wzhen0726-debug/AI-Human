# Retopology Toolchain Research (July 2026)

## Project Constraint: Zero-Budget, Solo Developer

This pipeline was built by a single developer with **no budget for software or hardware**.
All paid tools listed below are documented for reference only; the production pipeline uses
only free/open-source components (Blender built-in + MediaPipe + custom Python scripts).

**Paid tools documented but NOT used**:
- Faceform Wrap ($500/yr) — documented as industry benchmark
- Auto-Rig Pro (€$) — documented but pipeline uses Rigify (free, built-in)
- Reallusion Headshot 2.0 ($199) — documented for comparison
- Quad Remesher ($69) — documented; pipeline uses Blender Decimate + manual cleanup

**Hardware constraints**:
- No camera-array / photogrammetry rig (>$10K for 100+ camera matrix)
- No 3D scanner (>$5K for consumer-grade, >$20K for professional)
- No multi-GPU workstation (single workstation, CPU-bound for most steps)

These constraints directly shaped the decision to use **AI-generated high-poly meshes**
(from Tripo AI / image-to-3D websites) instead of photogrammetry or structured-light scans.
See the "Scheme Selection" section in the main pipeline doc for the full rationale.

## Wrap4D / Faceform Wrap

- **Product**: Faceform Wrap (formerly R3DS Wrap), standalone software, ~$500/year
- **Key mechanism**: `FacialWrapping` node combines `BlendWrapping` + dedicated **lip detector** and **eyelid detector**
- These detectors handle cavity regions (mouth, eye sockets) with normal-direction-constrained projection, preventing vertices from jumping to the opposite surface
- Supports personalized detectors trained on manually annotated frames
- **Why our Shrinkwrap fails**: No dedicated lip/eyelid detector — NEAREST_SURFACEPOINT pulls vertices to the wrong side of thin structures

## UE5 MetaHuman "Mesh to MetaHuman"

- **Free** in UE5, **closed source**, Epic-proprietary ML model
- Trained on thousands of 3D head scans with shape-prior learning
- Automatically deforms MetaHuman template to match input mesh
- Handles full head including ears, back of head, etc.
- **Cannot be replicated** without training data (thousands of 3D scans) and compute

## Open-source Alternatives

- **FLAME** (MPI-IS): Parametric head model, similar to SMPL for bodies
- **DECA** (MPI-IS): Single-image → 3D head reconstruction with FLAME params
- **NPHM**: Neural Parametric Head Models (implicit)
- **Instant Meshes**: Free, open-source quad remesher (no face-specific topology)

## Paid Alternatives

| Tool | Price | Notes |
|------|-------|-------|
| Faceform Wrap | $500/yr | Best for scan-to-template wrapping |
| Reallusion Headshot 2.0 | $199 | Photo/scan → CC character, auto-topology |
| Quad Remesher | $69 | Blender addon, general-purpose auto-retopo. **Smart edge-loop placement but NOT character-grade flow** — no facial rings, no joint loops, no symmetry guarantee. Body-only; face needs template-wrap. Full analysis: see `references/quad-remesher-topology-analysis.md` |
| ZWrap | Bundled with Wrap | Blender plugin for Wrap workflow |

## Key Insight for Our Pipeline

Wrap4D's success on thin structures comes from its **lip/eyelid detectors** that treat these regions separately. To improve our approach without buying Wrap, we need:

1. Better lip/eye contour detection (MediaPipe already has 478 points — use them better)
2. Directional projection for cavity regions (not global NEAREST/PROJECT)
3. Template vertex groups for nose/eye/mouth regions — apply different projection strategies per region

## Scheme Selection: Why Only One Pipeline Was Chosen

The original project proposal included **two schemes**:

| Scheme | Description | Cost | Status |
|--------|-------------|------|--------|
| **A** (selected) | AI image-to-3D site (Tripo AI) → high-poly mesh → retopology → rigging | Free (AI site) | **Active** |
| **B** (rejected) | Camera-array photogrammetry (100+ DSLR/matrix) → high-poly scan → retopology → rigging | >$10K hardware + studio | **Rejected** |

**Why Scheme B was rejected**:
- **Camera matrix cost**: A 100+ camera rig for photogrammetry costs $10,000–$50,000 (consumer DSLR ~$500 × 100 = $50K, or specialized matrix rigs ~$20K)
- **Studio space**: Requires a dedicated capture room with controlled lighting and rig mounting
- **Processing time**: Photogrammetry reconstruction (COLMAP / Metashape) takes hours per subject on a single workstation
- **No budget**: The project has zero hardware/software budget; all tools must be free
- **No team**: Single developer cannot simultaneously operate a camera rig and process data

**Scheme A advantages**:
- Zero hardware cost (use free tier of Tripo AI / Meshy / other image-to-3D sites)
- No studio space needed
- Single-person workflow (upload photo → download GLB → run pipeline)
- Reproducible: same input photo always produces same output (deterministic AI generation)
- Scalable: can process multiple subjects in batch

**Tradeoffs of Scheme A**:
- AI-generated meshes have ~2M–5M vertices (very high poly), requiring decimation before retopology
- AI meshes may have artifacts (floating hair, merged clothing, asymmetric features) that photogrammetry avoids
- No control over lighting/expression during capture (photo is the photo)
- Dependent on third-party AI service availability (but free tier is sufficient for testing)

**Conclusion**: Scheme A is the only viable approach under zero-budget, solo-developer constraints. The pipeline is designed to accept AI-generated high-poly meshes as input and produce animation-ready, rigged digital humans as output.