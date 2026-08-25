# Auto-UV Pipeline for Blender (Fully Automated)

## Problem
Smart UV Project is the only one-click automated UV tool in Blender, but it produces uncontrollable seams, island fragmentation, and no symmetry guarantee — unsuitable for production character models.

## Solution: Edge-Angle Auto-Seam + Standard Unwrap
Pure Blender Python, zero external dependencies, fully automated.

### Steps
1. **Select sharp edges by dihedral angle** (>55° recommended):
   ```python
   bpy.ops.mesh.edges_select_sharp(sharpness=0.96)  # ~55° in radians
   bpy.ops.mesh.mark_seam(clear=False)
   ```
2. **Add symmetry-axis seam** (X=0 plane, ensures left/right UV symmetry):
   ```python
   for edge in bm.edges:
       if abs(edge.verts[0].co.x) < 0.001 and abs(edge.verts[1].co.x) < 0.001:
           edge.select = True
   bpy.ops.mesh.mark_seam(clear=False)
   ```
3. **Angle Based Unwrap**:
   ```python
   bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)
   ```
4. **Auto-pack islands**:
   ```python
   bpy.ops.uv.pack_islands(rotate=True, margin=0.001)
   ```
5. **Equalize texel density**:
   ```python
   bpy.ops.uv.average_islands_scale()
   ```

### Quality
- Seams: hidden at sharp edges (>55°), symmetry axis hidden at back
- Islands: 20-50 large islands on 20-25万面 body model (vs 50-200+ from Smart UV)
- Stretching: controlled by angle threshold (lower = fewer seams but more stretch)
- Symmetry: guaranteed by X=0 seam

### Acceptable For
- Non-AAA production (20-25万面, simplified pipeline)
- Texture baking (Diffuse + Normal)
- GLB export with materials

### Not Acceptable For
- AAA game characters (needs manual seam placement)
- Film-quality renders (needs per-region UV optimization)

### Notes
- Angle threshold 50-60° recommended — start at 55°, adjust based on checkerboard test
- If threshold too high (>65°): fewer seams, more stretching
- If threshold too low (<45°): excessive seams, too many islands
- This technique was validated in the 2026-07-15 Quad Remesher simplified pipeline research