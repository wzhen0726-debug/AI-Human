# ARP Smart on T-pose models: rescue via ref-skeleton extraction (validated 2026-08-28)

## Symptom / when to use
ARP Smart (`guess_markers` → `go_detect`) on a **T-pose** model produces a wrong deform
skeleton even though detection is correct:
- `*_ref` bones land exactly on the user markers (arms horizontal at marker Z).
- Final deform bones (`shoulder.l`, `arm_stretch.l`, `hand.l`...) drop ~20-30cm and shorten
  (A-pose template). Wrist was off by 29cm in the validated case.
- Reproducible with the FULL official one-shot flow (guess_markers→go_detect without any
  interruption) → the fault is intrinsic to `go_detect`, not script sequencing.
- ARP presets are only DEFAULT/UE4/UE5 (all A-pose); there is **no T-pose/Mixamo preset**.
- `arp_smart_depth` only affects marker Y depth; it does NOT fix pose.

Do NOT try to re-pose or move the generated deform bones manually (constraints/finger
attachments break → bones disconnect). Extract from the correct ref skeleton instead.

**Status: this is now the standard ARP pipeline, not just a rescue.** The entire chain
(04-bake body → guess_markers → go_detect → ref extraction → align_roll → use_connect →
auto weights → walk verification) was consolidated into ONE script and re-validated from
scratch in a single pass: 55 bones / 55 weight groups / walk test 2793/3000 verts moved,
swing 8.2cm, foot grounded. Known-good script:
`05骨骼绑定/_工作区_过程文件/B_骨骼绑定/arp_full_rerun.py` (project repo, committed).
When re-running from an upstream stage output (e.g. `04_bake.blend`): delete all non-MESH
objects first (cameras/lights/eye objects live in baked files), keep only the body mesh,
then run `id.get_selected_objects` on it.

## Validated rescue pipeline

### 0) Official marker names (hard requirement)
`go_detect` only reads objects with fixed names:
`root_loc / chin_loc / neck_loc / shoulder_loc / elbow_loc / hand_loc / hand_tip_loc / thigh_loc / knee_loc / foot_loc` (+ `_sym` for left side).
Any custom naming scheme breaks the build. guess_markers produces all 17 (10 main + 7 sym).

### 1) guess_markers headless (AI marker placement)
Screenshot patch required for `-b` mode (replaces `_screenshot_char`):
- **Resolution MUST be 256x256** — `_set_markers_from_keypoints` maps pixels via
  `ratio = dim/256`; 512 input doubles every offset.
- Gray emissive material on `body_temp` (0.8 gray Emission shader) + dark world background;
  EEVEE render, JPEG. AI fails on textured/clothed renders.
- **Write back to self**: `self.larger_dim`, `self.larger_dimy`, `self.larger_dimtop`,
  `self.midx/midy/midz`, `self.margin` — without this all markers land at (0,0,0) and the
  arm-angle step crashes on a zero vector.
- **Never rename the user mesh to `body_temp` before ARP runs** — ARP creates its own
  `body_temp` copy; a name collision makes the screenshot patch grab the original mesh
  (with textures) → AI detection fails.
- Camera margin ~1.35 (1.05 clips fingertips → elbow/hand detection fails).
- Also patch `display_popup_message` to a print for headless.

### 2) go_detect settings
- `scn.arp_smart_depth = False`
- `scn.arp_smart_fingers_engine = 'LEGACY'` — 'AI' fingers need `thumb1_loc` etc. markers
  that don't exist in this flow → NoneType crash. LEGACY without `_bot_auto` objects skips
  the AI finger stage and still builds finger bones.
- Result: 348-bone controller rig + **correct `*_ref` skeleton** (66 bones incl. 30 finger
  refs). Keep this file as the intermediate.

### 3) Extract the `*_ref` skeleton into a new Mixamo-named armature
Create a fresh armature; head/tail come from ref bones via `arm.matrix_world @ head_local`.
Mapping (ARP ref → Mixamo bone):

| Mixamo | ARP ref source |
|---|---|
| Hips / Spine / Spine1 / Spine2 / Neck / Head (+HeadTop_End) | root_ref.x / spine_01..03_ref.x / neck_ref.x / head_ref.x |
| {Side}Shoulder | shoulder_ref.{l,r} — head stays at spine side (Mixamo convention; head≈(0.057,..), tail at shoulder joint) |
| {Side}Arm / ForeArm / Hand | arm_ref / forearm_ref / hand_ref |
| {Side}Hand tail | extend to **head of `middle1_ref`** (metacarpal region belongs to the Hand bone) |
| {Side}HandThumb1..3 | thumb1..3_ref (ARP thumb has NO base bone) |
| {Side}Hand{Index,Middle,Ring,Pinky}1 | **only `{f}1_ref`** — do NOT merge `{f}1_base_ref` (that is the metacarpal; merging it pulls the palm segment into Finger1 → "two bones in the palm, only two left in the finger") |
| Finger 2/3 | `{f}2_ref` / `{f}3_ref` |
| {Side}UpLeg / Leg / Foot / ToeBase (+Toe_End) | thigh_ref / leg_ref / foot_ref / toes_ref |

Delete the old controller rig, then `parent_set(type='ARMATURE_AUTO')` for weights
(vertex group count should equal bone count; validated 55/55).

### 4) Orientation: align_roll ONLY — never rewrite tails
Generate `mixamo_rest_spec.json` by dumping the Mixamo reference FBX bone local axes
(x/y/z + length + parent). Then per bone: `b.align_roll(spec_z_axis)`.
**Do NOT set `b.tail = head + spec_y * spec_length`** — the Mixamo reference model has
different proportions; tails drift off the child heads → every joint disconnects and
fingers scatter. Mixamo retargeting tolerates proportion differences; only the roll
(rotation frame) must match. Walk animation correctness comes entirely from roll.

### 5) Presentation + verification
- Set `use_connect` on children whose head == parent.tail (<2mm). Remaining gaps are
  anatomical offsets, identical in Mixamo's own skeleton (clavicle starts beside spine,
  fingers fan from metacarpals, thighs splay from hip sockets) — not errors.
- **Verify any user-reported "bone disconnected / finger intrudes palm" quantitatively
  before fixing.** Recipe (EDIT mode): for every bone with a parent, compute
  `gap = (b.head - b.parent.tail).length`; report all gaps >1mm. Classify:
  gaps <2mm = connected (chains intact); isolated gaps on limb chains (shoulder→elbow→wrist,
  hip→knee→ankle) = real break (almost always a script that rewrote `tail` or merged a
  segment); fan-out gaps on clavicle/finger-roots/hip = anatomical, not errors. In the
  validated session this single measurement both proved the tail-rewrite bug (15 breaks)
  and later confirmed the fix (0 chain breaks, only the 13 anatomical offsets). Do NOT
  hand-move bones to "fix" gaps — that re-breaks constraints; fix the generator instead.
- Mixamo walk verification harness (works for ANY Mixamo-named rig):
  import `Standard Walk.fbx` → copy action → locate the channelbag with fcurves
  (`action.layers[].strips[].channelbags`, a **property**, not a method) → remove
  `mixamorig:Hips` location curves → bind `animation_data.action_slot` to the slot whose
  `handle` matches that channelbag → depsgraph-evaluate frames 1 vs 18:
  count vertices moved >1cm (expect >500/3000 sampled), LeftHand z<1.8 with >2cm swing,
  RightFoot z<0.4 (grounded). Validated results: 2793/3000 moved, swing 8.2cm.

## Blender 5.1 API pitfalls hit repeatedly this session
- `ShrinkwrapConstraint.wrap_method` → `shrinkwrap_type`; enum value is `NEAREST_SURFACE`
  (not NEAREST_SURFACEPOINT).
- `bpy.data.objects` / `mesh.vertices` collections do NOT support slicing (`[::50]`) —
  iterate by index.
- `bpy.ops.object.add(type='ARMATURE')` creates at the **3D cursor** — set
  `scene.cursor.location=(0,0,0)` first or the whole rig is translated.
- Headless (`-b`): `bpy.ops.object.select_all` poll can fail after heavy ops (go_detect);
  use data-API selection (`o.select_set`) and `mode_set(mode='OBJECT')` before parenting.
- 5.x actions: no `action.fcurves`; use `layers[].strips[].channelbags` (property).
  `ActionSlot` has `identifier`/`handle`, no `name`.
- `scene.cursor_location` → `scene.cursor.location`; empty marker styling = `EMPTY` object
  with `empty_display_type='SPHERE'` + `show_in_front=True` (this is what the user-accepted
  manual marker template uses — not mesh balls).

## Delivery discipline (user-enforced)
One `.blend` per pipeline step in a clean linearly-numbered delivery folder (e.g.
`ARP版交付/01_打点模板.blend → 02_骨骼绑定.blend → 03_行走测试.blend`), each step verified
by the user before the next runs. Batching several unverified steps and delivering them at
once is rejected — errors compound invisibly.
**Backup before any full redo**: when the user asks to re-run the pipeline from an upstream
step, first snapshot the current deliverables + key intermediates into a dated folder
(`ARP版备份_20260828_第一版/`) — include the user's input point file, since the user's
manual work is irreplaceable. Then overwrite the live delivery folder with the fresh run.
