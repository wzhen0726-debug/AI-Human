# ZBrush Resymmetry Behavior — Official Documentation Excerpts

Sourced from Maxon ZBrush official documentation (help.maxon.net/zbr/en-us),
accessed 2026-07-08. These are verbatim excerpts used to verify claims about
how Resymmetry, Mirror and Weld, and Poseable Symmetry interact with UV and
texture data.

## SmartReSym (Tool > Deformation > SmartReSym)

> The Smart Realign Symmetry button restores symmetry to the object by
> examining all points in the mesh from beginning to end and determining
> which were originally intended to lie in mirror-symmetrical positions.
>
> This button can be used on a mesh which was originally created with mirror
> symmetry, whether created in ZBrush or imported from another source, even
> if large-scale distortion has occurred.
>
> You can 'lock' one side of an object by masking it before pressing this
> button; the opposite side then becomes adjusted to mirror the masked side.
> This is a good way to perform sculpting actions on one side of a mesh
> (which don't change the polygon count), as with Projection Master, then
> reflect them on the opposite side.
>
> Select one or more axes for this action by clicking the small X, Y and Z
> modifiers to turn them on (light) or off (dark).

**Key observation**: Description mentions only "points" and "positions of
vertices." No mention of UV coordinates, texture maps, or UV layers.

## ReSym (Tool > Deformation > ReSym)

> The Realign Symmetry button restores mirror symmetry to the object by
> adjusting the positions of vertices which lie in near-symmetrical
> positions. With symmetry restored, the object can be edited using
> mirror-symmetry modes in the Transform palette.
>
> Depending on the amount of distortion which has occurred, the vertices
> found in near-symmetrical positions may not necessarily be those originally
> intended to be symmetrical. For more sophisticated symmetry-realigning,
> use the Smart Resym button.

**Key observation**: Explicitly says "adjusting the positions of vertices."
No mention of UV.

## Mirror and Weld (Tool > Geometry > Modify Topology > Mirror And Weld)

> The Mirror and Weld button will mirror the tool along the selected axis
> (X,Y,Z) and then weld all points of the mesh. To establish the center of
> your tool move the Floor Elevation to 0. When you apply a Mirror and Weld
> along the Y axis remember that ZBrush is using the center point of the
> mesh. Moving the elevation of the floor to 0 will give you the visual of
> what will be Mirror and Weld.
>
> **Mirror and Weld will also transfer polypaint information.**

**Key observation**: Explicitly mentions polypaint transfer but says nothing
about UV. This is significant — when ZBrush docs want to note data transfer,
they say so explicitly (as with polypaint here). The absence of any UV mention
for Mirror and Weld and for SmartReSym/ReSym confirms UV is not operated on.

## Symmetry / Poseable Symmetry (User Guide > Sculpting > Symmetry)

> Poseable Symmetry utilizes ZBrush's SmartResym technology to automatically
> create symmetry based on topology instead of world space.
>
> Normal symmetry requires the model to be the same shape across either the
> X, Y or Z axis. When you pose a model, however, it is no longer the same
> across any axis and can not be sculpted symmetrically using normal symmetry
> tools.
>
> Poseable Symmetry solves this by using symmetry based on your topology. The
> topology must be symmetrical across one axis. However, it can not be
> symmetrical across two or more axis such as a sphere or cube would be.
> **It does not use UVs and is 100% dependent on your mesh being
> topologically symmetrical from one side to another.**

**Key observation**: Poseable Symmetry uses SmartResym technology and
explicitly states "It does not use UVs." This is the strongest direct evidence
that SmartResym is UV-independent.

## UV Map Sub-palette (Tool > UV Map)

The UV Map sub-palette has its own dedicated operations: Delete UV, Morph UV,
Flip U, Flip V, Cycle UV, Switch U<>V, AdjU, AdjV, ApplyAdj. These are
**separate tools** from Deformation. If SmartReSym operated on UVs, there
would be no need for these independent UV manipulation tools.

Notably, the UV Map page does not mention Resymmetry or Smart Resym anywhere.

## Texture Map Sub-palette (Tool > Texture Map)

The Texture Map sub-palette handles texture display (Texture On, Fix Seam,
etc.) and conversion between polypaint and texture:
- `New From Polypaint` — creates texture from polypaint
- `Polypaint From Texture` (in Polypaint sub-palette) — converts texture to
  polypaint

These conversion tools exist because polypaint and texture maps are
**different data representations**. Polypaint is per-vertex; texture maps are
UV-sampled. This architectural distinction is why Resymmetry (which moves
vertices) naturally preserves polypaint but not texture alignment.

## Summary of Findings

| Feature | Panel | What it operates on | UV affected? | Polypaint affected? |
|---------|-------|-------------------|-------------|-------------------|
| SmartReSym | Deformation | Vertex positions only | No | Yes (travels with verts) |
| ReSym | Deformation | Vertex positions only | No | Yes (travels with verts) |
| Mirror and Weld | Geometry > Modify Topology | Mirror + weld (topology change) | No | Yes (explicitly stated) |
| Poseable Symmetry | Transform (uses SmartResym) | Vertex positions (topology-based) | No ("does not use UVs") | Yes |

**Bottom line**: All ZBrush symmetry-resymmetry tools operate on vertex
positions. None operate on UV. Polypaint travels with vertices automatically.
If a model has existing UV + texture, Resymmetry will leave UV intact but the
texture may no longer align with the mirrored geometry unless the UV layout
was itself symmetric.
