# Quad Remesher Topology Analysis — Edge Flow vs Character Animation Requirements

Deep research (July 2026) into whether Quad Remesher produces animation-grade topology
or just clean uniform quads. Sources: Exoside official site, Blender Artists 681-post
thread (Metin_Seven FAQ), Polycount discussion, 80.lv / Lesterbanks coverage, Apple
ARKit BlendShapeLocation documentation, TopologyGuides.com.

## 1. What Quad Remesher Actually Produces

**Not uniform quads. Not character-grade flow. It's a middle ground.**

From the official Blender Artists FAQ (by Metin_Seven, beta tester):
> "Quad Remesher is not an ordinary remesher that projects faces onto a surface, but a
> cutting-edge auto-retopologizer with **smart placement of edge loops and singularities**,
> resulting in a mesh that is suitable for smooth subdivision without artifacts, proper UV
> mapping, easy rigging, and forms an optimal quad-poly base mesh for Multiresolution
> sculpting."

The algorithm:
- Analyzes surface characteristics: concavity, convexity, branching
- Strategically places edge loops (not random uniform grid)
- Minimizes singularities (poles/valence-3+ vertices)
- Result: clean all-quad mesh suitable for subdivision

**What it does NOT do:**
- Does NOT generate facial edge loops (mouth ring, eye ring, nasal ala loop)
- Does NOT generate joint deformation loops (knee, elbow, shoulder rings)
- Does NOT guarantee left/right mirror symmetry of topology
- Does NOT have a guide brush (Blender version lacks ZRemesher's Guide brush)
- Edge loops sometimes **spiral** — workaround: divide mesh into sections via Knife tool
  + material assignment, enable "Use Materials" option (like ZBrush Keep PolyGroups)

### Guiding mechanisms (how to influence edge flow without a guide brush)

| Method | What it does | When to use |
|--------|-------------|-------------|
| **Detect Hard Edges by angle** | Auto-recognizes sharp edges, places loops across them | Boolean primitives with hard edges |
| **Use Materials** | Places loops along material boundaries (like ZRemesher Keep Groups) | Pre-cut sections where you want loops |
| **Normals Splitting** | Uses normal breaks at sharp edges as guides | With Auto Smooth @180°, non-sharp edges don't split |
| **Vertex Paint** | Paints higher polygon density to specific areas (mouth) and less elsewhere (back of head) | Control density, not direction |
| **Knife tool pre-cuts** | Cut clean loops through mesh, assign materials to each section | When spiraling occurs or specific loop placement needed |

### Known limitations
- **UV preservation**: Not maintained in current version (planned for future). Workaround:
  low quad count → easy UV unwrap, or Data Transfer modifier to project UVs.
- **Face Maps**: Lost because FBX transfer doesn't support them. Converter provided as bonus.
- **Edge loop spiraling**: Common; divide mesh into sections via Knife + materials.
- **Adaptive Quad Count**: When checked, output count differs from input value.

## 2. ARKit 52 BlendShape Requirements

### What ARKit actually provides
ARKit face tracking outputs **52 coefficient values** (0.0–1.0) per frame:

**Left Eye (7)**: eyeBlinkLeft, eyeLookDownLeft, eyeLookInLeft, eyeLookOutLeft,
eyeLookUpLeft, eyeSquintLeft, eyeWideLeft
**Right Eye (7)**: same set for Right
**Mouth & Jaw (19)**: jawForward, jawLeft, jawRight, jawOpen, mouthClose, mouthFunnel,
mouthPucker, mouthLeft, mouthRight, mouthSmileLeft, mouthSmileRight, mouthFrownLeft,
mouthFrownRight, mouthDimpleLeft, mouthDimpleRight, mouthStretchLeft, mouthStretchRight,
mouthRollLower, mouthRollUpper, mouthShrugLower, mouthShrugUpper, mouthPressLeft,
mouthPressRight, mouthLowerDownLeft, mouthLowerDownRight, mouthUpperUpLeft, mouthUpperUpRight
**Brows/Cheeks/Nose (10)**: browDownLeft, browDownRight, browInnerUp, browOuterUpLeft,
browOuterUpRight, cheekPuff, cheekSquintLeft, cheekSquintRight, noseSneerLeft, noseSneerRight
**Tongue (1)**: tongueOut

### Key insight: coefficients are topology-agnostic, but BlendShape TARGETS are not
- ARKit itself does NOT require specific topology — it provides coefficient values
- Your model must have 52 BlendShape targets that deform correctly when these coefficients
  drive them
- **The topology determines deformation quality of each target**

### Impact of non-standard topology on BlendShapes

| Facial feature | Standard topology requirement | Quad Remesher result | Impact |
|---------------|------------------------------|--------------------|---------| 
| Mouth | 3 concentric edge loops around lips | No guaranteed loops | Volume loss, pinching on smile/open |
| Eyes | Double-ring around eye socket (eyelid) | No guaranteed rings | Tearing artifacts on blink |
| Brows | Horizontal flow above eyes | Random flow | Unnatural brow raise |
| Nose | Ala ring around nostrils | No guaranteed ring | Sneer distortion |
| Cheeks | Radial flow from cheekbone | Random flow | Puff/squint volume errors |
| Symmetry | Left-right mirror topology | NOT guaranteed | BlendShape asymmetry; manual fix doubles workload |

**For automated BlendShape generation tools** (e.g., Auto-Rig Pro's ARKit module):
These tools often expect or work best with topology close to a standard. Non-standard
topology from auto-retopo may cause the tool to produce poor-quality or broken targets.

## 3. Mixamo Auto-Rigging Impact

**Binding: minimal impact. Animation quality: moderate impact.**

- Mixamo auto-rigging is **geometry-based** (detects body proportions and joint positions),
  NOT topology-dependent
- Works on any mesh as long as it's humanoid, in T/A-pose, with clean geometry
- **But** animation deformation quality depends on topology:
  - No joint edge loops → knee/elbow bending causes volume loss + pinching
  - No shoulder flow → arm raise causes unnatural deformation
  - Quad Remesher's uniform-ish quads at joints: **usable but not ideal**

**Conclusion**: Mixamo binding will succeed. Joint deformation will have visible artifacts
that are acceptable for low-end use but not production-grade.

## 4. Tool Comparison Matrix — Auto/Manual Retopology for Characters

| Tool | Automation | Character flow | Guide control | Price | Best for |
|------|-----------|---------------|--------------|-------|----------|
| Quad Remesher | Full auto | ★☆☆ (smart but not char-specific) | Materials/hard edges/vertex paint only | $69 | Body, props, hard surface |
| ZRemesher + Guide Brush | Semi-auto | ★★★ | Guide brush draws loop paths | ZBrush license | Body if you have ZBrush already |
| ZRemesher + PolyGroups | Semi-auto | ★★ | Group boundaries guide loops | ZBrush license | Like QR materials approach |
| Blender Quadriflow | Full auto | ★☆☆ | None (same class as QR, slightly worse) | Free | Quick body retopo, no budget |
| Blender Voxel Remesh | Full auto | ☆ | None | Free | Sculpting base, NOT for rigging |
| Maya Quad Draw | Manual | ★★★★ | Full manual control | Maya license | Production character retopo |
| Blender manual Retopo | Manual | ★★★★ | Full manual, shrinkwrap snap | Free | Budget production retopo |
| 3DCoat Auto-Retopo | Semi-auto | ★★ | Guide lines available | 3DCoat license | More control than QR |
| MetaHuman Identity | Template wrap | ★★★★★ | Fixed template, auto-wrap | Free (UE5) | **Face — best automated option** |
| Instant Meshes | Full auto | ★☆☆ | None | Free | QR fallback, body only |

**No tool fully automates character-grade flow topology.** The closest to "auto character
topology" is template-wrap (MetaHuman) for faces, or semi-auto with guides (ZBrush/3DCoat)
for bodies.

## 5. Recommendation: Body vs Face Split

### Body → Quad Remesher (acceptable)
- Use materials to guide edge loops at joints (knee, elbow, shoulder, hip)
- 30-50K quads target
- Accept post-retopo manual cleanup at major deformation joints if production-grade needed
- Mixamo binding works fine on this topology

### Face → Template topology (mandatory, NOT Quad Remesher)
- Use MetaHuman template (`MH_Head_01.obj`, ~8K pure-quad verts) via Shrinkwrap + landmark
  anchoring (see sub-workflow B in SKILL.md)
- Or use ZBrush ZRemesher + Guide Brush for semi-auto facial retopo
- Standard facial topology (eye double-ring, mouth triple-ring, nasal ala loop) is
  **non-negotiable** for ARKit 52 BlendShape quality
- MetaHuman Identity (UE5, free) is the best automated face-topology solution

### Recommended pipeline
```
High-poly AI mesh
  ├─ Body → Quad Remesher (materials guide joints) → Mixamo auto-rig
  └─ Face → MetaHuman template wrap → ARKit 52 BlendShapes (Auto-Rig Pro)
```

## 6. Quad Remesher Workflow Tips (from community)

1. **Low quad count first** (~5000 average), then Multires + Shrinkwrap to recover detail.
   Non-destructive: changes to source mesh auto-reproject.
2. **Triangulate + Beautify Faces** before QR — balanced triangle structure helps algorithm.
3. **Adaptive Size** option: 50% = adaptive density; 0 = uniform. Test both.
4. **Apply scale** (Ctrl+A) before retopologizing — mesh scale affects results.
5. **For flat/2D meshes**: add slight bevel to sharp corners for better loop formation.
6. **Spiraling fix**: Knife tool (K) in Cut Through mode (Z) → slice sections → assign
   materials → enable "Use Materials" in QR.
7. **Avoid Detect Hard Edges** if already using materials — too many guides can conflict.
