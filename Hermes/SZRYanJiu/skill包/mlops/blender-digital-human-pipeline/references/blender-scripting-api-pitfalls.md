# Blender headless-scripting API pitfalls & testing methodology (validated 2026-08-05)

Discovered while running the 01 repair pipeline on a real 1.93M-face mesh in
Blender 5.1 (`--background --factory-startup`). Rotation-specific numpy pitfalls
(view-aliasing copies, `ndarray.ptp` removal, arm-span≥height assertion trap)
already live in `rotation-correction-footscore.md` §Pitfalls — not repeated here.

## 1. BMFace has NO `link_faces` attribute

`link_faces` exists on `BMVert` and `BMEdge` only. For face adjacency, build the
union over the face's edges:

```python
neighbors = set()
for e in f.edges:
    neighbors.update(lf for lf in e.link_faces if lf != f)
```

Crash signature: `AttributeError: 'BMFace' object has no attribute 'link_faces'`.

## 2. Rotation mode dispatch: unknown modes silently no-op

`_rotate_verts` mode set is exactly: `x+90 y-90 flip z+90 z-90 z180` (no `x-90`,
no `y+90`). An if/elif chain without `else` means calling a nonexistent mode is a
silent no-op — verification scripts that "compose a mode with its inverse" pass
vacuously if the inverse mode doesn't exist. Test scripts must only use
documented modes; prefer "4× 90° = full circle" round-trips.

## 3. Testing bpy-dependent modules

- Modules that `import bpy` at top level can ONLY be tested inside Blender:
  `blender.exe --background --factory-startup --python test.py`.
- Pure-math functions (foot_score, rotation math) can run in system Python with a
  MockObj exposing the mesh API surface the code touches:
  `vertices.foreach_get/foreach_set/__len__/__iter__` (yielding
  `SimpleNamespace(co=SimpleNamespace(x,y,z))`), `data.update()`,
  `matrix_world.to_euler()`. Add methods lazily as the code demands them
  (`__iter__` became necessary only when `get_bbox` was exercised).
- Synthetic humanoid anatomy matters for foot_score tests: torso depth (y-radius)
  must vary along height (buttocks bulge low, chest bulge high, waist pinch mid)
  — a flat-back column spanning full height degrades foot_score.
- Logic tests green ≠ pipeline safe: this session all mock tests passed, then the
  real run crashed on the BMFace bug. Real-model end-to-end run is mandatory.
- Delete temp verification scripts from %TEMP% after use.

## 4. Render-verification loop for orientation changes

Any rotation/orientation change must be confirmed by rendering, never by bbox
numbers alone. Workflow: `render_screenshot.py` renders front/side/three_quarter
with Workbench engine + `to_track_quat('-Z','Y')` cameras → move PNGs to
`screenshots/` with a dated prefix (e.g. `rerun_0805_front.png`) → vision_analyze
each with explicit yes/no questions (standing? facing camera? T-pose? complete
parts?). Note: in a true side view the raised T-pose arms can occlude the face
region — vision may read "arms forward"; that's a projection artifact, cross-check
against the front view before suspecting the model.

## 5. Re-run discipline for pipeline stages

When re-running a stage from the original input (e.g. after rewriting a stage
script post-merge-rollback):
1. Back up the existing output blend first (`cp x.blend x.blend.bak_<date>`) —
   and add `*.blend.bak*` to `.gitignore` BEFORE any `git add -A`, otherwise a
   79MB backup gets staged and the push hangs ("remote end hung up").
2. Run with explicit `-- <input.glb> <output.blend>` args, tee the log.
3. Expected-good numbers from the last verified run are the regression baseline
   (01 stage: 1.17M→965K verts after weld, watertight, non_manifold<10,
   boundary<10, QR-READY; ~2 min total incl. adhesion).
4. Render + vision_analyze before declaring done.
