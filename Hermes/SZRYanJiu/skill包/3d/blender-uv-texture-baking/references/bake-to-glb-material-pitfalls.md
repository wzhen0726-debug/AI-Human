# Bake → GLB: Material & Texture Pitfalls (2026-07-21)

## The #1 GLB Export Failure: White Model

### Symptom
GLB file imports into Blender/engine as a plain white or plastic-looking model.
No skin, no clothing texture, no normal map detail visible.

### Root Causes (in order of frequency)

#### 1. Duplicate material node chains (MOST COMMON)
After `05_bake.blend` (bake stage) → `06_rig.blend` (rig stage), the material
accumulates duplicate nodes:

```
Principled BSDF        → Material Output      (empty, no texture)
Principled BSDF.001    → Material Output.001  (has Diffuse + Normal, but unused)
Image Texture          → BSDF.001.Base Color
Image Texture.001      → Normal Map → BSDF.001.Normal
```

The glTF exporter reads the FIRST `Material Output` node it finds — which is
the empty one connected to the texture-less `BSDF`. The textured chain
(`BSDF.001 → Output.001`) is ignored.

**Fix**: `nodes.clear()` and rebuild from scratch:
```python
mat = mesh.data.materials[0]
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()
bsdf = nodes.new('ShaderNodeBsdfPrincipled')
out = nodes.new('ShaderNodeOutputMaterial')
tex = nodes.new('ShaderNodeTexImage')
tex.image = bpy.data.images['Bake_Diffuse']
links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
```

#### 2. Bake_Diffuse image deleted during rig stage
The rig script's `orphans_purge()` or object cleanup can delete images that
are not referenced by any material slot at purge time. If `Bake_Diffuse` was
connected to a node that gets removed during cleanup, the image becomes
orphaned and is purged.

**Fix**: After rig stage, check: `if 'Bake_Diffuse' not in bpy.data.images: ERROR`.
If missing, must re-bake from `04_uv.blend`.

#### 3. Normal map colorspace = sRGB (should be Non-Color)
`Bake_Normal` image defaults to sRGB colorspace. When used as a Normal Map
input, the sRGB gamma correction corrupts the normal vectors, producing
visible noise/dirt patterns on the model surface.

**Fix**: `bpy.data.images['Bake_Normal'].colorspace_settings.name = 'Non-Color'`
**CRITICAL**: Set this BEFORE `bpy.ops.object.bake(type='NORMAL')`, never after
(setting it after destroys baked pixel data — see SKILL.md for details).

#### 4. Old high-poly material slots inherited
The retopo mesh inherits material slots from the original GLB import. These
contain 8K basecolor textures and multiple shader nodes from the source model.
If not cleared, the GLB export includes both baked AND original textures,
producing a fragmented multi-material mess.

**Fix**: `mesh.data.materials.clear()` before creating the fresh bake material.

### Production-Safe Sequence
1. In bake stage: clear old materials → create fresh 'Char' material → bake →
   connect textures → pack images → delete high-poly → save `05_bake.blend`
2. In rig stage: load `05_bake.blend` → run rig script → save `06_rig.blend`
3. In export stage: load `06_rig.blend` → verify material nodes → rebuild if
   broken → export GLB with `export_apply=False, export_skins=True`
4. Verify: import GLB back → check for TEX_IMAGE nodes with non-null images

### Verification Script
```python
import bpy
bpy.ops.import_scene.gltf(filepath='final.glb')
for o in bpy.data.objects:
    if o.type == 'MESH' and 'Retopo' in o.name:
        m = o.data.materials[0]
        if m and m.use_nodes:
            tex_nodes = [n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE']
            for n in tex_nodes:
                print(f'{n.image.name if n.image else "NULL"}: {n.image.size[0]}x{n.image.size[1]}')
```

## Non-Manifold High-Poly Black Pixels (42.7%)
Tripo AI high-poly (1.93M faces) has 16.4% non-manifold edges (516,960 of
3,153,702). These open boundaries and internal surfaces block bake rays.
The 42.7% black pixels = ~15% UV overlap + ~27% high-poly internal geometry.
No bake parameter (Cage, ray distance, samples) can fix the latter — would
require cleaning the high-poly (fill holes, remove internal faces) before
baking. Always check: `non_manifold = sum(1 for e in bm.edges if not e.is_manifold)`.
If >10% non-manifold, expect >30% black pixels.
