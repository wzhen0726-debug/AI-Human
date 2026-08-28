# Walk Animation Slot Binding & Deformation Verification (Blender 5.x)

> Root-caused 2026-08-26 after user reported "动作只有参考模型上有" (animation only on reference model) and "骨骼都有问题" (bones all wrong — actually frozen pose, bones were fine).

## Symptom

Mixamo walk action is assigned to the user's armature (`animation_data.action` set, name matches, 517 fcurves present), but playing the timeline produces ZERO mesh deformation and all pose bones read rotation (0,0,0). Meanwhile a Mixamo reference model (Alpha_Joints/Alpha_Surface + 65-bone "Armature") in the same file animates fine.

## Root Cause 1: action_slot points to the EMPTY slot

Blender 5.x Slotted Action: one Action can hold multiple slots; fcurves live in `action.layers[].strips[].channelbags`, and each channelbag belongs to a slot via `slot_handle`. If `animation_data.action_slot` references a slot whose channelbag is EMPTY while all fcurves sit under a different slot's channelbag, the action silently evaluates to nothing.

Diagnostic (this exact case):
```
绑定的slot: id=OBwalk_rig_slot, handle=929201143   ← EMPTY
action里的全部slots: [('OBSlot', 929201142), ('OBwalk_rig_slot', 929201143)]
layer[0] strip[0] channelbag: slot_handle=929201142, fcurves=517   ← ALL DATA HERE
```

Fix: find the slot whose channelbags contain fcurves, then `ad.action_slot = that_slot`.

```python
data_slot = None
for slot in act.slots:
    n = sum(len(bag.fcurves)
            for layer in act.layers for strip in layer.strips
            for bag in strip.channelbags
            if bag.slot_handle == slot.handle)
    if n > 0:
        data_slot = slot
ad.action_slot = data_slot
```

## Root Cause 2: Mixamo reference model contamination

Importing a Mixamo FBX to harvest the walk animation brings the whole reference rig into the scene (Alpha_Joints, Alpha_Surface, "Armature" with 65 bones). The user sees animation driving THAT model and concludes it wasn't applied to theirs. After binding the action to our rig, DELETE the reference objects:

```python
for name in ("Alpha_Joints", "Alpha_Surface", "Armature"):
    o = bpy.data.objects.get(name)
    if o: bpy.data.objects.remove(o, do_unlink=True)
```

## Root Cause 3 (verification bug, not animation bug): reading the raw mesh

`body.data.vertices` is the ORIGINAL mesh — no modifier stack result. An armature-deformed mesh reads as "0 deformation" even while animating perfectly. This caused a false "animation still broken" diagnosis after the slot fix.

**Correct deformation verification:**
```python
dg = bpy.context.evaluated_depsgraph_get()
scn.frame_set(1); bpy.context.view_layer.update()
base = [v.co.copy() for v in body.data.vertices[:N]]
scn.frame_set(18); bpy.context.view_layer.update()
body_ev = body.evaluated_get(dg)
moved = sum(1 for i, v in enumerate(body_ev.data.vertices[:N])
            if (v.co - base[i]).length > 0.01)
```
Result after fix: 1952/2000 verts moving (97.6%) — walk animation truly driving the model.

Also note: `pose_bone.rotation_euler` can read (0,0,0) while the animation uses quaternion — check `rotation_quaternion` too before concluding a bone isn't animated.

## Blender 5.x animation API cheat sheet (all verified 2026-08-26)

- `action.fcurves` — **does not exist**. Use `action.layers[].strips[].channelbags`.
- `strip.channelbags` — property WITH trailing 's', **NOT callable** (`channelbags()` → TypeError 'bpy_prop_collection' object is not callable; `channelbag` without s → 'bpy_func' object is not iterable).
- `ActionSlot` has `.identifier` and `.handle`, **NOT `.name`**.
- `slots.new(id_type, name)` takes 2 args. Reusing another object's slot on a copied action fails — create a fresh slot for the copy.
- Deleting objects invalidates existing Python references — re-fetch via `bpy.data.objects.get(name)` after any `open_mainfile` or object removal; printing `o.name` from a stale list raises `ReferenceError: StructRNA has been removed` (collect names BEFORE deleting).

## Deliverable structure for walk-test files

Save the walk test as a separate step file (e.g. `手写版交付/04_行走动画测试.blend`) — never leave test pose/action state inside the clean rig deliverable (see `rig-pose-purity-and-bone-parenting.md`). Walk test flow: import Mixamo walk FBX → delete Hips location fcurves (root motion is global coords, model flies 4m away) → bind action + correct slot to user's rig → delete reference model → verify deformation via evaluated mesh.
