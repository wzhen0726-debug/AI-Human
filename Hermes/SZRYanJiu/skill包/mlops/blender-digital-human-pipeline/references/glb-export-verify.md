# GLB Export + Verification (stage-06 style)

Rigged + animated character → engine-ready single `.glb`, with checks that caught
real defects (importer artifacts faking geometry changes).

## Export call

- `bpy.ops.export_scene.gltf` with `use_selection=True` and ONLY the armature + **product**
  meshes. Define product mesh = scene object of type MESH **with an ARMATURE modifier**;
  never select helper/display shapes (custom bone shapes, ARP cs_* objects).
- `export_format='GLB'`, `export_animation_mode='ACTIONS'` → each action becomes its own glTF
  animation (names = action names); `export_frame_range=False` keeps each action's own range.
- **Scene fps must match the reference** (Mixamo authoring = 30 fps). Exporting a 30 fps
  animation from a 24 fps scene silently re-times it; verify with `scene.render.fps` first.
- `export_apply=False` (never apply modifiers — the armature modifier must survive),
  `export_yup=True`, `export_skins=True`, `export_rest_position_armature=True`.
- Survive Blender API drift: filter kwargs against the operator's own properties —
  `props = {p.identifier for p in bpy.ops.export_scene.gltf.get_rna_type().properties}` →
  `kw = {k: v for k, v in want.items() if k in props}` and print what was dropped.

## Three-layer verification (never trust a single check)

1. **Parse the GLB yourself** (12-byte header + JSON chunk via `struct`): animation count,
   per-animation duration from `accessors[sampler.input].max[0]` (seconds = frames/fps),
   meshes / skins / joints / images counts. Header magic `glTF`, version 2.
2. **Reimport into a factory-clean scene AT THE SAME FPS**, compare rest height (set
   `armature.data.pose_position='REST'` for a true rest measure) and object/bone counts.
3. **Animation signature** = world-space bbox (6 numbers) of the evaluated skinned meshes at
   chosen frames — robust to the exporter's vertex reordering/merging, unlike per-vertex diffs.
   Dense per-frame keys should reproduce within ~0.1 mm (measured 0.07 mm); gate at ~5 mm.

## Pitfall that faked a failure

- The glTF **importer** creates a bone-display icosphere (42 verts, ±1 m) as an artifact —
  not asset content. Bbox code that iterates `bpy.data.objects` (or scene objects without a
  modifier filter) then reports a fake height (+0.7 m) and an extra mesh. Always filter to
  meshes with an ARMATURE modifier for both sides of the comparison.
- Source files can carry stray objects too — same filter protects the export selection.

## Pipeline integration

- Print the stage done-marker (`06_DONE`) ONLY after every check passes; consoles gate
  stages on that marker, not on Blender's exit code (bg runs exit 0 regardless).
- Deliver alongside the sibling blends so downstream users can compare standardized vs not.
