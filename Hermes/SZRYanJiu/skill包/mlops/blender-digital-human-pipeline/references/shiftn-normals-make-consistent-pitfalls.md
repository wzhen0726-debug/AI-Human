# Shift+N (normals_make_consistent) Fails on AI/Game Meshes — Root Causes & Fix

> Use when `bpy.ops.mesh.normals_make_consistent(inside=False)` or GUI Shift+N
> flips LARGE regions that were already correct (e.g. whole legs/lower body turn
> red in Face Orientation view), or gives a different result every run.
> Real case: 01A eye-socket step, 2026-08-06 — one global Shift+N after deleting
> eye-hole faces flipped 22.4% of all faces (lower body went red).

## TL;DR

**Never run global Shift+N / normals_make_consistent on a mesh that has open
boundaries, nested shells, or non-manifold edges.** On such meshes it is
non-deterministic and propagates face direction across hole edges, flipping faraway
correct regions. If the source mesh's normals are already correct (e.g. a cleaned
01_highpoly_repair.blend), do NOT recalculate them globally at all — deleting faces
and moving verts preserves winding, so normals stay correct by themselves.

## Why Shift+N misfires (the 4 geometric root causes)

Shift+N is not "visual magic". It assumes the mesh is a **watertight closed volume**,
then walks edge adjacency like dominoes to unify winding. Hidden geometry defects
break that assumption, and the algorithm's idea of "inside vs outside" inverts:

1. **Internal faces (most common).** Nested shells (cloth outer + full body inside,
   un-booleaned inserts). The walker hits an interior face and "inside" becomes
   "outside", dragging the outer surface's normals to flip with it.
   GUI check: Edit > Select All by Trait > **Interior Faces** → delete, then retry.
2. **Non-manifold / holes.** Un-welded duplicate verts or small holes (sleeve cuffs,
   unsealed hems). The volume "leaks"; direction flips at hole rims and broken verts.
   GUI check: M > Merge by Distance; Select All by Trait > **Non Manifold** → patch holes.
3. **Self-intersection.** AI/scanned meshes fold through themselves; volume calc
   dead-locks and locally forces flips. Hard to patch by hand — use Voxel Remesh to
   regenerate a clean watertight shell.
4. **Custom split normals data.** Imported FBX/OBJ/GLB may carry locked custom
   normals; Shift+N behaves erratically. Object Data Properties > Geometry Data >
   **Clear Custom Split Normals Data**, then retry.

## Manual rescue (when cleanup is too expensive)

1. Overlays > **Face Orientation** (blue = correct, red = flipped).
2. Edit mode, box-select the red faces.
3. Alt+N > **Flip**. (Targeted flip only — never whole-mesh recalc.)

## Rule for this pipeline

- 01 repair output is already normal-correct (verified by BVH ray vote, 0 inward).
- 01A socket carving only deletes faces + pushes verts → winding unchanged → normals stay correct. Do **not** call normals_make_consistent there; only `remove_doubles` for local welding.
- Verify with BVH ray sampling: 8000–20000 rays from outside, inward-hit ratio must be < 0.5%. (01A pre-fix measured 22.4% → FAIL; post-fix 0.000% → PASS.)

Cross-ref: `法线问题深度诊断报告.md` / `法线朝向修复方案.md` in 方案md记录/v3_QuadRemesher/01高模修复与黏连检测/.
