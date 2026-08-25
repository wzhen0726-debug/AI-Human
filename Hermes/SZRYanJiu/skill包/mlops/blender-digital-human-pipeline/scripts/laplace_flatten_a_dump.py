"""Laplace flatten — STEP A (run inside Blender): dump mesh + free-region vertex sets.

Usage:
  blender --background --factory-startup --python laplace_flatten_a_dump.py

Edit CONFIG below: BLEND_IN, NPZ path, and one ellipse per bump.
Ellipse axes MUST extend well past the bump footprint (>=12-15mm beyond) so the
ellipse BOUNDARY sits on flat surrounding surface — otherwise the harmonic fill
inherits the bump's slope and leaves residual height. Verify with render+vision.

Ellipse params from connected-component/PCA analysis of the heightfield:
  (center_x, center_z, long_axis_angle_deg, half_long_axis, half_short_axis)
"""
import bpy, math
import numpy as np

# ---- CONFIG ----
BLEND_IN = r"...\01_highpoly_repair.blend"
NPZ_OUT  = r"...\_laplace_data.npz"
BUMPS = [(-0.050, 1.201, -146, 0.056, 0.034),
         ( 0.037, 1.215,  142, 0.054, 0.035)]
# ----------------

bpy.ops.wm.open_mainfile(filepath=BLEND_IN)
om = max((o for o in bpy.data.objects if o.type == "MESH"),
         key=lambda m: len(m.data.vertices))
mesh = om.data
n = len(mesh.vertices)
V = np.empty((n, 3), dtype=np.float64)
mesh.vertices.foreach_get("co", V.ravel())
E = np.empty((len(mesh.edges), 2), dtype=np.int64)
mesh.edges.foreach_get("vertices", E.ravel())
print(f"mesh: {n} verts, {len(E)} edges")

save = {"V": V, "E": E}
for k, (cx, cz, ang, a, b) in enumerate(BUMPS):
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    dx = V[:,0]-cx; dz = V[:,2]-cz
    u = dx*ca + dz*sa; t = -dx*sa + dz*ca
    rho2 = (u/a)**2 + (t/b)**2
    # front surface only (model faces -Y): y < -0.05
    free = np.where((V[:,1] < -0.05) & (rho2 < 1.0))[0]
    save[f"free{k}"] = free
    print(f"bump{k}: free={len(free)}")

np.savez_compressed(NPZ_OUT, **save)
print("saved", NPZ_OUT)
