# Retopology Technology Landscape Research

## Wrap4D / Faceform Wrap

**Product**: Faceform Wrap (formerly R3DS Wrap), ~$500/year. Wrap4D is the 4D
sequence extension.

**Key technique — FacialWrapping node**:
- Combines BlendWrapping with a dedicated **lip detector** and **eyelid detector**
- These detectors constrain projection direction per-region, preventing vertices
  from crossing through thin structures (lips, eyelids) to the opposite surface
- Supports training a **personalized detector** from manually annotated frames
- This is exactly what our Shrinkwrap approach lacks — we have no region-specific
  projection constraints for lips/eyelids

**Workflow**: Node-based — LoadGeom(high) → LoadGeom(template) → SelectPointPairs
(manual dotting) → Wrapping → TextureTransfer

## UE5 Mesh to MetaHuman

**Architecture (5-step pipeline, confirmed by community research)**:
1. **Auto landmark detection** (local): CNN/DNN detects facial feature curves
   (eyelids, nasolabial folds, lip lines, brow arches, earlobes) from front render
2. **Identity Solve** (local): Non-rigid ICP guided by landmarks, deforms
   MetaHuman template to fit scan volume
3. **Database approximate search** (cloud): Instance-based retrieval (NOT PCA
   3DMM) in a massive facial database. "Database too large to obtain otherwise."
4. **Rig + Delta** (local): Approximation is rigged; difference between scan
   and approximation saved as Delta Shape. Final = database approximation + unique details.
5. Output: Fully rigged MetaHuman skeletal mesh

**Open source?**: NO. Completely closed — model, database, and training data
are proprietary. Cannot be replicated.

**Why it works without manual dotting**: The CNN detects full feature curves
(not just points), and the instance-based database provides a shape prior that
constrains the deformation to plausible human face shapes.

## Open-Source Alternatives

- **FLAME** (MPI-IS): Parametric head model, similar to SMPL for bodies
- **DECA** (MPI-IS): Single-image → 3D head reconstruction with FLAME params
- **NPHM**: Neural Parametric Head Models (implicit representation)
- **HRN**: Head Registration Network (CT-to-template registration)

None of these include the massive facial database that gives MetaHuman its quality.

## Paid Alternatives

| Tool | Price | Cavity Handling | Automation |
|------|-------|-----------------|------------|
| UE5 Mesh to MetaHuman | Free | ✅ Learned | Fully automatic |
| Reallusion Headshot 2.0 | $199 | ✅ Automatic | Photo/scan → CC rig |
| Faceform Wrap | $500/yr | ✅ Lip/eyelid detectors | Semi-auto (manual dots) |
| Quad Remesher | $69 | ❌ None | Auto remesh, no face-specific |
| Instant Meshes | Free | ❌ None | Auto remesh, no face-specific |

## Key Insight for Our Pipeline

The fundamental gap is not algorithm but **data and region-specific constraints**:
- Our Shrinkwrap is a generic nearest-surface operation with no knowledge of
  facial anatomy
- Wrap4D adds lip/eyelid detectors — region-specific projection constraints
- MetaHuman adds a learned shape prior — constrains deformation to plausible faces

## Encapsulation Requirements (user-confirmed)

When building a deployable tool (not just a script), the solution must be:
- **One-command runnable**: `blender --background --python fit_v3.py`
- **Zero external GUI dependencies**: No UE5, no Wrap4D, no ZBrush
- **Packageable as Hermes Skill or pip package**: `pip install head-retopo`
- **Verifiable by non-technical stakeholders**: One command, one output file,
  quantitative report

This rules out UE5 (100GB+ install, GUI-only, cloud dependency) and Wrap4D
($500/seat/year, GUI-based) as components of the deliverable. They can be
used for **research/reference** but not in the shipped pipeline.

## Next Steps for Our Blender-Only Pipeline
1. **Feature-point Procrustes alignment (DONE in v3)**: Replace centroid
  alignment with 12-point Procrustes (translate→scale→re-translate). This
  fixed a 149mm Z-axis offset between template and scan that caused total
  mouth/chin misalignment. Results: 0.372mm mean, 97.1% <1mm, 0.04mm eye symmetry.
2. Per-region projection: constrain eye/nose vertices to face-direction (-Y)
   projection only, preventing cross-surface penetration
3. FLAME shape prior: fit FLAME parameters to the scan, use as a deformation
  constraint to prevent implausible vertex positions
4. MediaPipe 3D Face Mesh mode: output 468 3D world coordinates directly,
  skipping the lossy 2D→3D raycast step
