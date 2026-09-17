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
- **Headless log noise that is harmless** (seen every run, do not chase): better_fbx
  `ModuleNotFoundError: bpy_types` at addon register; ARP `cleanup_line_fx` /
  `arp_debug_mode AttributeError` load_pre handler errors; `No reference neck bone
  selected: pinky3_ref.l`; driver `Invalid driver - custom_shape_scale` warnings. The run
  is fine if `Error during detection? False` and bone counts print.

### 2.5) Marker QA loop (user-enforced 2026-08-31): first-pass user markers are often wrong
Do NOT treat user-placed/AI-placed markers as final after one pass. Loop until the user
confirms in the GUI:
1. Run a numeric self-check script (`check_markers.py` pattern) on the current markers
   blend BEFORE go_detect: left/right symmetry (|x|, z within 1cm), expected-z table with
   ±5cm tolerance, T-pose arm z-linearity (shoulder/elbow/wrist/tip within 3cm), chain
   ordering (arm x increasing, leg z decreasing), midline points x≈0, proportions
   (shoulder width > hip width; upper-arm/forearm ratio 0.7-1.4; thigh/shank 0.75-1.3),
   root vs thigh equal height (±2cm). Print every violation as a human-checkable hint,
   never auto-move the user's markers.
2. User adjusts in GUI, saves, re-check, repeat. In the 2026-08-31 session it took 3
   user passes (root height, shoulder position, elbow position) — this is normal.
3. Deliverables of the loop: `点位指南.md` (placement guide, summary table FIRST,
   detailed per-point landmark text AFTER) + `check_markers.py` — both are reusable
   product artifacts, not session scratch.
- **Guide format lesson (user correction)**: summary table must come first ("让人第一眼
  就能看到大概要打的点"), detailed per-point text after; guide must state explicitly
  that markers are 3D points needing BOTH front (x/z) and side-ortho (y) checks.
- **Elbow ROOT CAUSE (source, auto_rig_smart.py:2333-2348)**: the user's `elbow_loc`
  sets `arm_ref.tail` (upper-arm END), but `forearm_ref.head` (the actual elbow JOINT)
  is computed by ARP's own elbow-direction correction — it takes midpoint of (arm head,
  forearm tail), checks `forearm_ref.head[1] < midpoint[1]`, and if so ROTATES the elbow
  around the arm axis. So the marker drives the upper-arm tail but NOT the elbow joint.
  Fix at extraction: set both `LeftArm.tail` AND `LeftForeArm.head` to the elbow marker
  (keeps chain connected, zero gap). Confirmed 2026-09-01 walk still passes.
- **User markers ARE symmetric (corrected 2026-09-01)**: the `_sym` markers mirror the main markers via a COPY_LOCATION constraint, so they are strictly symmetric **when read correctly**. The 09-01 asymmetry (elbow L/R x+1.5cm y-4.5cm) was a READING bug: `o.location` returns the pre-constraint local value; use `o.evaluated_get(dg).matrix_world.translation` (see "镜像标记点读取" below). No symmetrization needed when reading correctly.
- **Leg bones must NEVER be "verticalized"** (rejected 09-01): forcing UpLeg/Leg tails
  straight down to match Mixamo's vertical rest direction breaks the chain — thigh tail
  stays at thigh x but knee is offset in x -> 4-6cm gaps, use_connect drops off. Real
  legs splay; Mixamo rest legs are also not perfectly vertical. Keep ARP ref leg
  positions as-is.
- **Marker-priority override pitfall (hit 2026-09-01)**: when overriding joint positions
  with user markers, NEVER point two different bones at the same marker — user
  `shoulder_loc` (三角肌中点 skin landmark) and ARP `arm_ref` (shoulder joint) happened
  to coincide at x=0.215, so mapping both Shoulder-head and Arm-head to the marker
  collapsed the Shoulder (clavicle) bone to zero length → "肩膀骨骼没了". Mixamo anatomy
  has TWO distinct points (Shoulder head ≈x0.061 near spine, Arm head ≈x0.188 at the
  joint); the user's shoulder marker matches neither exactly. Rule: marker override
  applies ONLY to joints the user actually marked (elbow/wrist/hip/knee/ankle +
  midline root/neck); clavicle (Shoulder) keeps the ARP ref position.
- **Marker-priority override — refined rule (2026-09-01)**: FULL marker-priority extraction (every joint from markers) was rejected (breaks REST-frame alignment → odd walk). The validated route is **pure ARP ref-skeleton + align_roll as the BASE**, with **targeted marker corrections only**: (a) elbow joint ← `elbow_loc` (ARP rotates it off-course, see elbow root cause above); (b) leg bones ← re-centered to leg-mesh geometric center (see 腿骨中心化 below). Markers serve as QA for everything else. Do NOT point two bones at one marker (clavicle/shoulder collapse) and NEVER verticalize legs.
- **Do NOT scale `mixamo_rest_spec.json` positions onto the model (rejected plan,
  2026-09-01)**: spec `head` is in METERS but `length` is in CENTIMETERS (mixed units
  in the same file); more fundamentally the spec is a different-proportioned reference
  model, so `head*scale` lands joints 18-21cm off the real mesh (shoulder z 1.26 vs
  real 1.465) and walk-PASS becomes meaningless (rig outside body). The spec's only
  valid use is roll/z-axis orientation (`align_roll`), never absolute positions.
  Verified numerically: Mixamo reference IS T-pose (LeftArm Y axis = (1,0,0) pure
  horizontal, shoulder/elbow/wrist all z≈1.436) — do not re-litigate this.
- **`bpy.data.libraries.load` objects have uninitialized matrix_world (all-zero)**: when
  reading marker objects from another .blend via libraries.load without linking them to
  the scene, `o.matrix_world.translation` returns (0,0,0) — for top-level objects use
  `o.location` directly. Always `assert any(v.length > 0.1 ...)` after loading markers;
  a zeroed skeleton still produces a fake walk PASS (mesh collapses onto origin-bound
  rig → huge vertex deltas), so numeric walk validation alone does NOT prove the rig is
  inside the body — sanity-check absolute joint coordinates too.

### 2.6) Productization requirement (user-stated 2026-08-31)
The end product is a packaged, programmatic pipeline — not a chat-driven session. Every
step must end as an independently callable script (one .py per step, `--python` headless,
logs to `logs/stepN_log.txt`), with exactly ONE human gate: GUI confirmation of marker
positions (backed by the guide + self-check script). Keep this shape when writing new
steps; do not leave workflow knowledge only in chat.

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

## Supervised re-run discipline (user-enforced 2026-08-31)
When the user asks to redo the ARP test from an upstream stage (e.g. `04_bake.blend`)
"from 0" with supervision:
- Backup existing deliverables (dated folder), then create a NEW dated test folder
  (`ARP新版测试_YYYYMMDD/`) holding step scripts + step blends + `logs/` — never delete or
  overwrite old test data; the user explicitly wants prior runs preserved.
- Run ONE step per script, save `NN_步骤名.blend`, STOP, and wait for user confirmation
  before the next step. Full-chain one-shot reruns are only for already-accepted flows.

## 双脚腾空 / 脚不贴地 (2026-09-01 攻克, 核心新坑)

**症状**: Mixamo 行走动画套上后, 用户报告"走路两只脚都不贴地""脚底浮空上下波动"。
数值实测: 帧4-14 + 帧22-32 大段双脚同时离地 3-8cm。

**根因 = Hips 垂直起伏被误删(不是腿长差)**:
- 行走动画的 Hips location 含重心垂直起伏(2-5cm), 迈步时身体下压让支撑脚踩地。
- 全删 Hips location(原地走) 把这个起伏也删了 → 身体不压 → 脚够不着地 → 双脚腾空。
- 恢复 Hips 垂直起伏后, 脚自然贴地, 0腾空帧。**不是腿长差**(腿长差11%只影响步幅, 不影响贴地)。

**正确修法 = 恢复 Hips 垂直起伏(源头, 可程序化)**:
1. 删 Hips location 的**水平轴**保留垂直起伏。但我们骨架与参考骨架的 Hips 局部坐标系不同:
   - 我们骨架(scale=1): **Hips 局部 y 轴 = 世界垂直**(实测: pose_bone.location.y+0.1→世界z+0.1), 局部 x/z=水平
   - 参考骨架(FBX scale=0.01): 局部 y=垂直(cm)
2. 逐帧读参考骨架 Hips 世界z, 算起伏增量 `(ref_z - ref_rest_z) * 腿长比`, 用
   `hips_pb.location.y = delta` + `keyframe_insert('location', index=1, frame=f)` 写入
   我们 Hips 局部 y。**用 pose_bone.location + keyframe_insert 让 Blender 处理局部系,
   绝不手改 fcurve 原始值**。
3. 验证: 全帧扫支撑脚最低点, 腾空帧(>2cm)应=0。

**邪修勿用**: 逐帧测支撑脚间隙再反算 Hips 下沉补偿(数据驱动贴地)——用户明确反对, 会导致
身体晃动且无法程序化(每个新模型都要AI补偿)。贴地要从动画数据源头(恢复Hips起伏)解决。

**配套坑**:
- "行走验证PASS"不等于贴地——旧验证只看摆臂+右脚z<0.4(太宽松)。验证必须含全帧支撑脚贴地检测。
- 调Hips fcurve不生效时, 先实测轴向: `pose_bone.location[idx]=0.1` 后读世界z变化, 找哪个局部轴=世界垂直, 别猜。

## 镜像标记点读取 (2026-09-01, 反复栽坑)
ARP打点模板的 `_sym` 点靠 **COPY_LOCATION 约束(invert_x)** 镜像跟随主点, 严格对称。
- **读标记点必须用 `obj.evaluated_get(dg).matrix_world.translation`**(含约束求值结果)。
- **`o.location` 只读约束前的局部原始值**(错误的/不对称的)——用它读会误判点不对称, 进而
  多做对称化取平均(牺牲精度)。先用 `bpy.context.view_layer.update()` 触发约束求值再读。
- 自检: 读完断言左右对称(|a.x+b.x|<2mm), 不对称=读取方法错。

## 腿骨中心化 (2026-09-01, 治膝盖朝外/划圆)
ARP参考骨的小腿骨距腿mesh表面仅0.1cm(贴皮,偏后外), 不在小腿几何中心 → 行走膝盖朝外/划圆。
修法: 用 BVHTree 算胯/膝/踝各自高度处的腿mesh顶点几何中心(x,y), 把腿骨移过去:
- z(高度)保持标记点不变, 只调x,y
- UpLeg.tail 和 Leg.head 都对齐到膝中心(同一点) → 链条不断开
- 左右腿分别采样后**镜像对称化**(x取|均值|,y取均值) → 避免mesh本身左右不对称导致骨骼不对称
- 脚head跟随踝中心
验证: 对称/连贯全过, 贴地0腾空, Hips起伏正常。

## Marker placement guide + verification pitfalls (2026-08-31)
- Users supervising AI-placed markers need a **text placement guide** to check against —
  produce a `点位指南.md` alongside the markers blend: each of the 10 main points anchored
  to ONE unambiguous body landmark (chin=下巴最下尖, neck=颈后大椎高度正中线,
  shoulder=三角肌中点/肩缝, elbow=肘外侧骨点与肩同高, hand=腕横纹中点,
  hand_tip=中指指尖, root=大转子高度的骨盆几何中心, thigh=股骨大转子,
  knee=髌骨外侧缘高度, foot=外踝骨突), each with a "不是" anti-ambiguity line, plus a
  numeric self-check table (expected z per landmark for the current model).
- Markers are 3D points: front view verifies x/z only; **side view (Numpad-3 ortho) is
  required for depth (y)** — chin/neck/root/knee/foot are the depth-sensitive ones.
- **Never trust vision_analyze for fine relative-height judgments** (e.g. "is root higher
  or lower than thigh"): in this session vision gave opposite answers to the same question
  twice. Read marker coordinates from the .blend (`-b --python-expr` printing
  `matrix_world.translation.z`) and compare numerically — one 4-second headless call
  settles it. Here the numeric check showed root z=0.927 vs thigh z=0.882, i.e. root
  needed to move DOWN 4.5cm — opposite of the vision-based advice. Matches the standing
  rule: quantitative geometric judgments = world-bbox/coordinate math, never vision.
