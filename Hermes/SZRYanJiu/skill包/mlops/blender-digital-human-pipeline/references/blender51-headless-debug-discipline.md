# Blender 5.1 Headless Run & Debug Discipline (2026-08-27)

Durable lessons from many headless `blender -b --python` runs this project.

## Log handling
- **Never use `2>nul`** — it discards the real traceback. Redirect everything to a
  log file (`> log.txt 2>&1`) and grep it. One session re-ran the same crashing
  command 40+ times because stderr was discarded.
- **Blender exits 0 even when the `--python` script throws.** Always check the log
  for `Traceback` / your DONE marker; never trust the exit code alone.
- Addon registration noise (ARP/better_fbx/rigify) floods stdout. Grep with
  exclusion filters: `grep -avE "bpy_types|better_fbx|callback|load_pre|arp_debug"`.
- Print markers like `STEP_DONE` + write results to a file inside the script
  (stdout can be swallowed); check the file after the run.

## Blender 5.x API changes hit this session
- `ShrinkwrapConstraint.wrap_method` → `shrinkwrap_type`; enum
  `NEAREST_SURFACEPOINT` → `NEAREST_SURFACE` (valid: NEAREST_SURFACE / PROJECT /
  NEAREST_VERTEX / TARGET_PROJECT).
- `bpy.data.meshes.get(name)` may return a mesh whose `bm.to_mesh(me)` needs a
  freshly `bpy.data.meshes.new()`-ed mesh — never pass None.
- `bpy.data.objects` collections do not support slicing (`verts[::50]`) — use
  `range(0, n, step)` indexing.
- After addon ops in headless mode, `bpy.ops.object.select_all` can fail with
  "context is incorrect" — deselect via a `select_set(False)` loop instead.
- `bpy.ops.object.add(type='ARMATURE')` creates the armature **at the 3D cursor**
  — reset `scene.cursor.location = (0,0,0)` first or the whole skeleton is offset
  (cost one full rebuild: Hips off by 17.5cm).
- Drivers: `obj.driver_add("location", i)` returns an FCurve; set `.driver.type='SCRIPTED'`,
  variables with `TRANSFORMS` type + `transform_space='WORLD_SPACE'`.
- Empty marker objects: use `EMPTY` type with `empty_display_type='SPHERE'`,
  `empty_display_size=0.012`, `show_in_front=True` — the user-validated hand-made
  marker style. Mesh balls with materials render gray/invisible in Workbench and
  the user rejected them repeatedly. Object `.color` works on Empty wireframes.

## Verification before delivery
Bone positions must be checked against the user's marker coordinates numerically
(head/tail vs point, flag >5cm) before handing any rig file to the user — multiple
deliveries were rejected because this step was skipped.
