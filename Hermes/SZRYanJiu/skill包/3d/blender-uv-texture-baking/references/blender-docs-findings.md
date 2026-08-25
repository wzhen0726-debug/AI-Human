# Blender 5.1 Official Documentation Findings

Verified excerpts from Blender 5.1 official docs, retrieved 2026-07-08.
Source URLs are the live manual pages at docs.blender.org.

## Mirror Modifier (Source: modeling/modifiers/generate/mirror.html)

### Data > Flip UV
> With this option you can mirror the UV texture coordinates across the middle
> of the image. E.g. if you have a vertex with UV coordinates of (0.3, 0.9),
> its mirror copy will have UV coordinates of (0.7, 0.1).

### Data > UV Offsets
> Amount to shift mirrored UVs on the U/V axes. It's useful for baking (as
> overlapping UVs can cause artifacts to appear in the baked map), so the UVs
> can be moved outside the image and not used for baking, but still be used
> for display.

### Data > Flip UDIM
> Mirror the texture coordinates around each tile center.

### Data > Vertex Groups
> Try to mirror existing vertex groups, with the following specific
> prerequisites: The vertex groups you want to mirror must be named following
> the usual left/right pattern (i.e. with suffixes like ".R", ".right", ".L",
> etc.). The mirror side vertex group must already exist (it will not be
> created automatically). It must also be completely empty (no vertices
> assigned to it).

**Key takeaway**: Mirror Modifier defaults to geometry-only. UV mirroring
requires explicit Flip UV / UV Offsets / Flip UDIM enablement.

---

## Render Baking (Source: render/cycles/baking.html)

### Selected to Active
> Bake shading on the surface of selected objects to the active object. The
> rays are cast from the low-poly object inwards towards the high-poly object.
> If the high-poly object is not entirely involved by the low-poly object,
> you can tweak the rays start point with Max Ray Distance or Extrusion
> (depending on whether or not you are using cage).

### Cage
> Cast rays to active object from a cage. A cage is a ballooned-out version
> of the low-poly mesh created either automatically (by adjusting the ray
> distance) or manually (by specifying an object to use). When not using a
> cage the rays will conform to the mesh normals. This produces glitches on
> the edges, but it is a preferable method when baking into planes to avoid
> the need of adding extra loops around the edges.

### Cage Object
> Object to use as cage instead of calculating the cage from the active object
> with the Cage Extrusion. Both meshes need to have the same Topology (number
> of faces and face order).

### Cage Extrusion
> Distance to use for the inward ray cast when using Selected to Active and
> Cage. The inward rays are cast from a version of the active object with
> disabled Edge Split Modifiers. Hard splits (e.g. when the Edge Split
> Modifier is applied) should be avoided because they will lead to non-smooth
> normals around the edges.

### Max Ray Distance
> Distance to use for the inward ray cast when using Selected to Active. Ray
> distance is only available when not using Cage.

### Margin
> When baking to images, by default a margin is generated around UV "islands".
> This is important to avoid discontinuities at UV seams, due to texture
> filtering and mip-mapping.
>
> Type:
> - Extend: Extend border pixels outwards.
> - Adjacent Faces: Fill margin using pixels from adjacent faces across UV seams.

### Bake from Multires
> Bakes a Normal or Displacement map directly from a mesh that has a
> Multiresolution Modifier. Viewport Levels = low-res base, Render Levels =
> high-res detail. The resulting bake represents the difference between these
> two levels.

### Normal Space
> - Object: Normals in object coordinates, independent of object
>   transformation, but dependent on deformation.
> - Tangent: Normals in tangent space coordinates, independent of object
>   transformation and deformation. This is the default, and the right choice
>   in most cases, since then the normal map can be used for animated objects
>   too.

**Key takeaway**: Without cage, rays follow normals and produce edge glitches.
Cage requires matching topology. Max Ray Distance only available without cage.

---

## UV Unwrapping (Source: modeling/meshes/uv/unwrapping/introduction.html + seams.html)

### Unwrapping workflow (official)
1. Mark Seams if necessary
2. Select mesh faces in the 3D Viewport
3. Select a UV mapping method from the UV ‣ Unwrap menu
4. Adjust the unwrap settings in the Adjust Last Operation panel
5. Add a test image to see if there will be any distortion
6. Adjust UVs in the UV editor

### Seam strategy (from Seams page)
> For many cases, using the Unwrap calculations of Cube, Cylinder, Sphere, or
> the regular "Unwrap" operators will produce a good UV layout. But for more
> complex meshes, especially those with lots of indentations, you may want to
> define a seam to limit and guide the Unwrap operator.

> The more seams there are, the less stretching there is, but this is often
> an issue for the texturing process. It is a good idea to have as few seams
> as possible while having the least amount of stretching.

> In productions where 3D paint is used, this becomes less of an issue, as
> projection painting can easily deal with seams, as opposed to 2D texturing,
> where it is difficult to match the edges of different UV islands.

### Bilateral unwrapping (from Seams page)
> When unwrapping anything that is bilateral, like a head or a body, seam it
> along the mirror axis. For example, cleave a head or a whole body right down
> the middle in front view. When you unwrap, you will be able to overlay both
> halves onto the same Texture Space, so that the image pixels for the right
> hand will be shared with the left; the right side of the face will match
> the left, etc.

### Seams from Islands
> Adds seams at the boundaries of existing UV islands. This is useful when
> modifying the UVs of already unwrapped meshes.

**Key takeaway**: Seam along mirror axis for bilateral models enables UV
overlay (shared texture pixels). Smart UV Project page was not found (404) —
its behavior is inferred from the unwrapping introduction and general
Blender knowledge.
