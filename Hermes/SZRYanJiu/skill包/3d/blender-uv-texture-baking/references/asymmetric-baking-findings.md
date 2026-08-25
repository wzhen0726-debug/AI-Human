# Asymmetric High-Poly to Symmetric Low-Poly Baking

Research findings on the fundamental problem of baking textures when the
high-poly and low-poly models do not spatially coincide. Verified against
Blender 5.1 official docs and Blender Artists community forum, 2026-07-09.

## Core Principle: Spatial Coincidence Required

**Selected to Active baking requires the high-poly and low-poly surfaces to
occupy the same 3D space.** This is not a Blender-specific limitation — it is
the fundamental mechanism of all "cast rays from low-poly inward" baking
tools (Blender, Substance Painter, Marmoset Toolbag).

Blender 5.1 official docs (render/cycles/baking.html):
> "Bake shading on the surface of selected objects to the active object.
> The rays are cast from the low-poly object inwards towards the
> high-poly object."

The bake computes the **surface difference** (normal direction, color, etc.)
between the two meshes at each point. If the surfaces are not in the same
location, the difference is meaningless or sampled from the wrong surface.

## Pose Mismatch Breaks Baking — Confirmed

Blender Artists forum, user JA12 answering the exact question
(https://blenderartists.org/t/question-about-baking-basics/1101253):

> "No. [...] Baking those needs to happen so that high detail surface and
> low detail surface occupy the same space to get the difference. That's
> why you can't bake posed and unposed ones, the two model surfaces are
> way apart from each other."

Example: high-poly has left arm raised, right arm down. Low-poly has both
arms down (symmetric). The low-poly's right arm (down position) casts rays
inward along its normals. If those rays travel far enough, they may hit
the high-poly's raised left arm — sampling the wrong surface entirely.
The resulting texture will be incorrect.

## Solutions Summary

| Approach | When to use | Tradeoff |
|----------|-------------|----------|
| Symmetrize high-poly first | Need symmetric result (game character) | Loses original asymmetric detail |
| Keep both asymmetric | Preserve unique detail | UVs must also be asymmetric (no shared space) |
| Split by region, bake separately | Complex characters with mixed symmetry | Most flexible, more setup |
| Match poses (rig both to same armature) | Rigged characters | Requires proper rigging on both |
| Custom cage with per-region control | Fingers, complex overlapping areas | Most precise, most effort |

## Workflow Order — Critical

**Correct sequence:**
1. Determine final high-poly form (symmetric or asymmetric)
2. Symmetrize high-poly IF symmetric result needed
3. Wrap/retopologize low-poly to match high-poly's spatial form
4. UV unwrap low-poly
5. Bake (high and low now spatially coincide)

**Wrong sequence (produces errors):**
1. Wrap low-poly from asymmetric high-poly
2. Symmetrize low-poly afterwards
3. Bake → high and low no longer spatially coincide → broken texture

## Facial Asymmetry

Industry consensus (from Blender Artists forum): **do NOT force-symmetrize
faces.** User jerzygorskiart stated directly:
> "You don't really want symmetry for a head anyway, it'd be too obvious."

Human faces are naturally slightly asymmetric. Forcing symmetry produces
an uncanny, obviously fake appearance. Standard practice:
- UV layout CAN be symmetric (shared left/right UV space)
- Bake from the actual (slightly asymmetric) high-poly
- Accept minor asymmetry in the baked texture
- If truly symmetric texture needed, use Substance Painter to symmetrize
  post-bake, but this is generally avoided for faces

The slight spatial mismatch from facial asymmetry (a few mm) is usually
within the Max Ray Distance tolerance and does not cause catastrophic
projection errors — unlike a full pose mismatch (arms in different
positions, which is centimeters to tens of centimeters off).

## UV Symmetry vs Geometry Symmetry — Independent Decisions

A common confusion: UV symmetry and geometry symmetry are separate axes.

| Geometry symmetric? | UV symmetric? | Result |
|---------------------|---------------|--------|
| Yes | Yes (shared L/R space) | Standard game character, efficient |
| Yes | No (independent L/R islands) | More texture detail per side, more UV space |
| No | Yes (shared L/R space) | Symmetric UVs but asymmetric baked texture — works if mismatch is small |
| No | No | Fully independent, most detail, most UV space |

The third row (asymmetric geometry + symmetric UVs) is the common case for
realistic faces: the UV layout is symmetric for efficiency, but the bake
preserves the slight facial asymmetry from the high-poly sculpt.

## Industry Standard

1. Characters needing symmetry (generic game NPCs, base meshes):
   sculpt with symmetry from the start → wrap → bake. No post-hoc
   symmetrization needed.

2. Characters with specific poses or unique features:
   sculpt asymmetric → wrap to match → bake asymmetric. UVs as independent
   islands.

3. Faces: never force-symmetrize. Accept natural asymmetry.

4. Mixed approach: symmetrize the body (arms, torso) for UV efficiency,
   keep the face asymmetric. Bake the body and face as separate regions
   if needed.
