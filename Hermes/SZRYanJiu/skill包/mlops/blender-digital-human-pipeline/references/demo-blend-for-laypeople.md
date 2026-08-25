# Demo blend for laypeople — zero-install interactive handoff

When the user must hand an interactive 3D file to a NON-technical person (演示给不懂建模的人看/调),
the right deliverable is a **self-contained .blend** — NOT an addon (addon needs install + has
hardcoded absolute paths that break on another machine). The blend must open in a state where the
layperson can act immediately, with zero setup and zero script authorization prompts.

## The four things that must be set BEFORE saving the blend

Viewport/UI state lives in the blend's workspace, so it must be configured in a **windowed** Blender
run (NOT `-b` background — background has no window, and area-split / tool / shading settings made
headless are NOT persisted). Launch with UI, run the setup script, save, then quit in the same run:
```
blender --python make_demo.py --python-expr "import bpy; bpy.ops.wm.quit_blender()"
```

1. **Material preview shading** — laypeople think an untextured gray model is "broken". Set
   `space.shading.type = 'MATERIAL'` on every VIEW_3D area so it opens already textured.
2. **Move tool active + gizmo visible** — a layperson doesn't know to press G or switch tools.
   Set `bpy.ops.wm.tool_set_by_id(name="builtin.move")` in each area's context override so the
   XYZ axis gizmo shows on the selected object the moment the file opens.
3. **Target object(s) pre-selected + active** — `select_set(True)` + `view_layer.objects.active`.
4. **Dual viewport** (optional but requested): split one VIEW_3D into two — left = front view,
   right = side view. Use `bpy.ops.screen.area_split(direction='VERTICAL', factor=0.5)` ONCE
   (guard: only split if only one VIEW_3D exists, else re-runs keep splitting). Then set each
   area's `region_3d.view_rotation` (quaternion) + `view_perspective='ORTHO'` for the two views.

## Object sync WITHOUT scripts — native Copy Location constraint

Scripted depsgraph handlers require the user to click "Allow Execution" (a yellow security banner)
on first open — a layperson will miss it and the demo silently doesn't work. **Use a native
constraint instead: zero script, zero authorization, works on any machine.**

For mirrored pair sync (left eye drives, right eye mirrors):
```
con = eyeR.constraints.new(type='COPY_LOCATION')
con.target = eyeL
con.use_x=True; con.invert_x=True    # X mirrored (left/right symmetric about x=0)
con.use_y=True; con.invert_y=False   # Y (depth) same
con.use_z=True; con.invert_z=False   # Z (height) same
con.target_space='WORLD'; con.owner_space='WORLD'
```
Dragging the LEFT eye makes the RIGHT follow mirrored. The `invert_x` trick only works when the
pair is symmetric about x=0 — verify positions before relying on it.

## Verification

Confirm the constraint and selection actually persisted by re-opening the saved blend headless and
reading them back:
```
blender -b demo.blend --python-expr "import bpy; print(len(bpy.data.objects['Eye002_R'].constraints), bpy.context.view_layer.objects.active.name)"
```
Expect: constraint count ≥1 with correct target + invert flags, active object = the driver object.

## Camera/view orientation gotcha

The view_rotation quaternion depends on which way the model faces (this project: face toward -Y).
A wrong quaternion makes "front view" show the back of the head. Verify by rendering or reading the
quaternion back and reasoning about the facing axis before declaring done.
