# UV Ecosystem Research — AI 3D Companies, Open-Source Tools, & Commercial Solutions

> Research conducted 2026-07-21 for a digital human pipeline: high-poly AI mesh (1.93M faces) → QuadRemesher (90K quad faces) → UV unwrap → bake → rig.
> Core problem: QuadRemesher produces uniform quad grids with minimal normal variation, making all automatic UV algorithms fail to recognize body part boundaries.

## AI 3D Companies — UV/Retopology Assessment

### TRIPO (VAST AI, Shanghai)
- Product: tripo3d.ai, TripoSR, TripoSG, UniRig, SkinTokens
- UV is baked into the generation pipeline — no standalone UV tool
- Retopology output preserves UVs from generation, but cannot accept external QuadRemesher meshes
- **Not usable for external UV pipelines**

### Hunyuan3D (Tencent)
- Product: Hunyuan3D-1.0/2.0/2.1, GitHub: Tencent-Hunyuan/Hunyuan3D-1
- Has a "Baking" module (closed-source) for texture baking onto generated mesh
- UV unwrapping is internal to the generation pipeline — no standalone tool
- 2.x pipeline: Shape Generation → UV Unwrapping → Texture Synthesis
- **Not usable for external meshes**

### Rodin (Deemos, Shanghai)
- Product: Rodin Gen-1, Hyper3D
- End-to-end: multi-view image → 3D shape → auto UV → texture
- No standalone UV tool or API
- **Not usable for external pipelines**

### Meshy
- "Smart Remesh" adjusts tri/quad count and topology type
- AI texturing claims "no UV mapping needed" — uses model-internal mapping
- No standalone UV unwrap tool
- **Not usable for external UV**

### CSM (Common Sense Machines)
- End-to-end 3D generation, UV is internal
- **Not usable for external pipelines**

## Open-Source UV Tools — Detailed Assessment

| Tool | Type | Algorithm | License | Blender Background | Quality | Notes |
|------|------|-----------|---------|-------------------|---------|-------|
| **xatlas** | C++ lib | LSCM + chart packing | MIT | Via Python bindings | 6/10 | Fork of thekla_atlas; jpcy/xatlas on GitHub |
| **pymeshlab** | Python | LSCM/Spectral/ABF | GPL | ✅ | 5/10 | LSCM times out on 90K quad meshes |
| **thekla_atlas** | C++ lib | LSCM + packing | MIT | Needs compilation | 6/10 | Original repo (ignf/thekla_atlas) is 404; xatlas is its fork |
| **UVAtlas** | C++ lib (MS) | Isochart | MIT | Needs compilation | 7/10 | Microsoft; archived April 2026 |
| **libigl** | C++/Python | ARAP/LSCM/multiple | GPL | ✅ (Python) | 7/10 | Academic standard; rich method selection |
| **CGAL** | C++ lib | Multiple | GPL/LGPL | Needs compilation | 8/10 | Industrial-grade; Orbit Parameterization |
| **minimize_stretch** | libigl tutorial | ARAP energy min | GPL | ✅ | 7/10 | Quad-mesh-friendly |
| **optchar** | Tool | Auto chart segmentation | Unknown | ❌ | Unknown | GitHub repo is 404 |
| **Blender built-in** | Blender | ABF/CONFORMAL/Smart | GPL | ✅ | 5/10 | ABF=碎片化; CONFORMAL=拉伸; Smart=碎片化 |
| **Open3DStudio** | TypeScript | Integrated UV unwrap | Open-source | Self-hosted | Unknown | FishWoWater/Open3DStudio on GitHub |

### Critical Finding
All automatic tools depend on geometric features (curvature, normal variation) for chart segmentation. QuadRemesher's uniform quad grid has minimal normal variation, causing ALL tools to fail at body part boundary detection. This is a topology-driven problem, not an algorithm deficiency.

## Academic UV Research (2024-2025)

- **Classic methods**: OptCuts (SIGGRAPH 2018), BFF (SIGGRAPH 2017), Progressive Parameterizations (SIGGRAPH 2018) — all need geometric features or manual input
- **Neural UV Mapping**: UV-Net, TextureNet — need training data; poor generalization to quad-remeshed meshes
- **Learned Seam Placement**: Requires labeled training data
- **Diffusion-based UV** (2024): Early-stage research
- **No academic method directly addresses quad-remeshed uniform mesh UV unwrapping**

## Blender UV Plugins

| Plugin | Price | Background | Quality | Notes |
|--------|-------|-----------|---------|-------|
| **ZEN UV** | $35-48 | ✅ (needs license) | 7/10 | Already tested; auto_uv_unwrap + CONFORMAL inplace = 63.5% utilization |
| **UVPackmaster 3** | $30 | ✅ (CLI) | 8/10 | Packing only, not unwrapping |
| **UVPackmaster 3 Pro** | $50 | ✅ | 8/10 | GPU-accelerated packing |
| **TexTools** | Free | ✅ | 7/10 | Open-source; texture density/alignment |
| **Magic UV** | Free | ✅ | 6/10 | Open-source; basic UV editing |
| **RizomUV Bridge** | $49 | ❌ (needs GUI) | 9/10 | Blender ↔ RizomUV live bridge |
| **UV Toolkit** | $15 | ✅ | 7/10 | Professional UV editing |
| **DreamUV** | Free | ✅ | 6/10 | Experimental AI-assisted UV |

## Commercial Tools — Headless/CLI Assessment

| Tool | Price | Headless/CLI | Quality | Notes |
|------|-------|-------------|---------|-------|
| **RizomUV** | $1499 perpetual or $299/yr | ✅ RizomUVLink (ZMQ) | 10/10 | Industry standard; Lua scripting; Python API |
| **RizomUV VS** | $299/yr | ✅ | 9/10 | Feature-limited version |
| **Unfold3D** | Acquired by RizomUV | N/A | N/A | Discontinued |
| **Wrap4D** | $499/yr | ❌ GUI only | 9/10 | Topology transfer, not UV unwrap |
| **ZBrush UV Master** | $39.95/mo | ❌ | 7/10 | Interactive only |

### RizomUV Headless — Why It's the Best
- RizomUVLink: ZMQ-based Python API for headless operation
- Lua scripting for full automation: import → unwrap → pack → export
- Can accept pre-marked seams for body-part-aware unwrapping
- rizomuv-mcp (fkrn75/rizomuv-mcp on GitHub): MCP protocol bridge for RizomUV

## Recommended Approaches (Priority Order)

### 🥇 RizomUV Headless + Auto Seams (Quality: 10/10, Cost: $1499, Timeline: 1 month)
Pipeline: QuadRemesher → auto seam marking (body-part segmentation) → OBJ → RizomUV CLI → reimport to Blender

### 🥈 libigl ARAP + Manual Seams (Quality: 7/10, Cost: Free, Timeline: 2-3 weeks)
Pipeline: Blender Python → libigl ARAP parameterization (with constraint boundaries) → write back to Blender

### 🥉 UVPackmaster 3 Pro + Blender Unwrap (Quality: 7/10, Cost: $50, Timeline: 1 week)
Pipeline: Blender background → manual seams → Blender unwrap → UVPackmaster packing

### Fundamental Solution
The core insight: add an **auto-seam-marking step** between QuadRemesher and UV unwrap. Use:
1. Original high-poly normal information (closest-point transfer)
2. AI body-part segmentation (e.g., SCHP human parsing) → body part boundaries → seams
3. Or RizomUV's semi-automatic seam tools