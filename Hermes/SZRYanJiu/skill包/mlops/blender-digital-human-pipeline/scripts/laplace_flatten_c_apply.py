"""Laplace flatten — STEP C (run inside Blender): apply solved y back to mesh.

Usage:
  blender --background --factory-startup --python laplace_flatten_c_apply.py

Clamps any OUTWARD push (dy<0) to 0 — the harmonic fill can request a tiny
outward move where the boundary ring dips; allowing it risks new protrusions.
Observed: clamp affects ~1% of verts and changes the result negligibly.
"""
import bpy
import numpy as np

BLEND_IN  = r"...\01_highpoly_repair.blend"
BLEND_OUT = r"...\01_highpoly_repair_chestflat.blend"
SOL       = r"...\_laplace_solution.npz"

bpy.ops.wm.open_mainfile(filepath=BLEND_IN)
om = max((o for o in bpy.data.objects if o.type == "MESH"),
         key=lambda m: len(m.data.vertices))
mesh = om.data
n = len(mesh.vertices)
V = np.empty((n, 3), dtype=np.float64)
mesh.vertices.foreach_get("co", V.ravel())

sol = np.load(SOL)
moved = 0
for k in range(2):
    free = sol[f"free{k}"]; y = sol[f"y{k}"]
    dy = y - V[free, 1]
    n_clamped = (dy < 0).sum()
    dy = np.clip(dy, 0.0, None)   # inward only, never outward
    V[free, 1] = V[free, 1] + dy
    moved += len(free)
    print(f"bump{k}: {len(free)} verts, push +{dy.min()*1000:.2f}..+{dy.max()*1000:.2f}mm, "
          f"clamped_outward={n_clamped}")

mesh.vertices.foreach_set("co", V.ravel())
mesh.update()
bpy.ops.wm.save_mainfile(filepath=BLEND_OUT)
print(f"total moved={moved}, saved")
