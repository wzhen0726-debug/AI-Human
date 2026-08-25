# Rig Delivery: Pose Purity, BONE-Parent Math, Marker-Based Joints (2026-08-25)

## Symptom pair with ONE root cause: "opens with a weird pose" + "eye iris pointing down"

Both came from **verification tests run directly on the delivery file**: a bend-elbow (90°) and
nod-head (28.6°) test were posed, then the file was saved with the pose residue intact.
The Head bone's 28.6° forward tilt dragged the Head-parented eyeballs down — iris pointed down.
Static skeleton structure was correct; the pose contamination was the whole problem.

**Diagnosis**: loop `arm.pose.bones`, flag any with non-identity `rotation_euler` /
`rotation_quaternion` / `location`. (On the broken file: Head 28.6°, RightForeArm 90°.)

**Fix + rule**:
- Before saving ANY delivery blend, run a pose-purity check and zero out residue.
- Verification tests (bend elbow, nod head, eyeball follow) run on a **temporary copy only**.
  Never write test poses back to delivery files. Delivery files are rest pose, always.

## Eyeball (or any child) parented with parent_type=BONE — transform math (verified)

For `parent_type='BONE'`, the parent matrix origin is the bone's **TAIL, oriented along the
bone's rest axes** — not the head. Using the wrong matrix shifts the child by bone-length plus
orientation error (measured: z off by 0.238m).

- WRONG: `arm.matrix_world @ pose_bone.matrix` — pose matrix, drifts with any pose.
- WRONG: `arm.matrix_world @ bone.matrix_local` — origin at head, wrong origin and offset.
- CORRECT (round-trip verified to restore placement position exactly):

```python
import mathutils
head_b = arm.data.bones['Head']
tail_mat = mathutils.Matrix.Translation((0, head_b.length, 0))
parent_mat = arm.matrix_world @ head_b.matrix_local @ tail_mat
eye.location = parent_mat.inverted() @ world_pos   # set AFTER assigning parent/bone
```

After saving, read back the eye's world position (depsgraph-evaluated) and compare against the
placement value — do not trust the formula alone.

## Marker-based rigging (01A pattern applied to body joints)

Flow: `measure_joints.py` geometric measurement (height-band scans, arm-thickness profile,
leg-width profile) → `joints_measured.json` → markers placed AT measured positions → user
fine-tunes in GUI → mirror R→L → generate skeleton.

- **CRITICAL difference from 01A eyelid markers: body joints are INSIDE limbs — do NOT add
  Shrinkwrap constraints** (they pull joint markers onto the skin surface, e.g. belly/back,
  making markers scatter). Eyelid markers are surface features → Shrinkwrap correct there.
- Initial positions from measurement, never guessed constants (earlier version wrote Crotch
  z=0.90 vs measured 0.71, wrist ±0.59 vs measured ±0.69 — visibly wrong).
- Naming: `LM_01_中文_英文` (01A convention), color-coded groups, `show_in_front=True`.
- Shoulder point reference: **humeral head** — 1-2cm below the acromion, deep to deltoid.
  NOT deltoid midpoint, NOT clavicle end. Render a PIL-annotated reference image for the user
  (`bpy_extras.object_utils.world_to_camera_view` → PIL circles; 3D spheres get occluded).
- Folder split: `A_半自动打点/` (markers + measurement, user stage) vs `B_骨骼绑定/`
  (rig generation, delivery) — keep the two stages' files separate.

## Bone direction & structure fixes (verified this session)

- **UpLeg sign**: hip head must be on the SAME x-side as the knee tail. Sign flipped once
  produced head +0.08 → tail −0.133: thigh crossing through the body.
- **Foot/toe orientation**: toes point −Y (model forward), NOT ±X sideways. Four-segment foot:
  Foot(ankle→heel, +y/−z), ToeBase(heel→ball, −y), Toe(ball→tip).
- **Shoulder bone (Mixamo convention)**: draw from near spine
  (`shoulder_mid + (sh−shoulder_mid)*0.2`) TO the shoulder joint — not shoulder→elbow
  (that overlaps the Arm bone and looks "missing").
- **Hands**: 5 fingers × 3 segments × 2 hands = 30 bones; fan around Z (thumb +25° … pinky −10°,
  mirror sign per side), thumb tilted up; fingers extend along `hand_dir` from the knuckle row.
- Total: 22 body + 30 finger + 2 extra foot = 54 bones.

## Verification checklist (temporary copy!)

1. Bend RightForeArm 90° → count verts moving >1cm (11,051 moved) → weights effective.
2. Nod Head → eyeball world position moves (7.9cm) → eyes follow head.
3. On the delivery file: 0 pose bones with residue; opens in rest pose.
4. Eye world position matches placement after save.

## ARP status note

Auto-Rig Pro 3.74.60 is installed with complete AI model files (front/side/top/fingers .pth +
inference exes under `Documents/AutoRigPro/AI/inference/`). The hand-written Mixamo rig above is
the active approach; ARP Smart remains a viable alternative (GUI-driven workflow; headless
run requires the monkey-patches in `auto-rig-pro-background-mode.md`). If the user wants
animation-grade finger/foot deformation, evaluate ARP before extending the hand rig further.
