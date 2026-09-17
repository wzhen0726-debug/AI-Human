## Walk-retarget QA: the "cat-walk" judge must measure VISIBLE geometry

After rest normalization to Mixamo (legs vertical), a retarget design that
"keeps our own stance ⊕ reference motion" loses the original asset's 8° leg
splay that used to keep the gait wide. With a narrow marked pelvis
(UpLeg|x| 77.8 vs the walk actor's 91.2) the landing ankle drops to 18 mm from
the midline and an ankle-threshold check (ref-min × pelvis-ratio × 0.75)
false-fails a walk that renders completely natural (8-frame strip: no crossing,
half a foot-width minimum gap, natural gait).

Lessons for judging locomotive QA:

- Judge on VISIBLE geometry, not bone x. Working criterion (two parts):
  (a) hard: min 3D vertex distance between the two feet ≥ ~5 mm (contact /
crossing = the catastrophic regression form); (b) proportional: tightest landing-
ankle / pelvis-half-width ≥ reference's own same ratio (tightest side) × 0.6 —
all derived from the reference FBX measured in-run; no hard-coded mm, and one
rational tolerance factor, documented.
- Dead ends (do not repeat): x-projection gap between foot bounds is negative
even for the reference (−6.2 mm) — the passing swing foot always overlaps in x;
min-3D foot distance alone is dominated by that same normal pass-by; flipping
the hips' lateral-carry sign is WORSE (the original sign is correct).
- When a numeric gate fails a visually-fine animation, render the animation
before touching the rig: the frame strip decided this case, and the fix was the
criterion, not the walk.

---

# Rest-Pose Normalization: limbs-only (no shoulders, no torso)

## Final policy (2026-09-17, user-verified after rejecting full alignment)

Align the 47 limb bones (Arm/ForeArm/Hand + fingers, UpLeg/Leg/Foot/Toe); do NOT
touch the 8 torso-side bones. User verdict on the previous full-alignment: “除了腿跟手臂
有正优化，其他的肩膀 躯干 脖子 都是负优化” — top view showed a squeezed groove between
the shoulder blades, front read as severe chest-thrust, and the face warped after the
neck was aligned.

- **Shoulders are NOT limbs.** Clavicles sit 21° off the reference; aligning them
  rotates the clavicle/scapula flesh → the back groove + chest-out look. Excluding
  shoulders (arms only) fixes chest-out — the earlier “limbs-only still chest-out”
  attribution was really the shoulder rotation.
- **Measure the reference bones before copying any angle convention.** mixamorig:Neck
  is DEAD VERTICAL (+180.00° side angle), Neck→Head relative rotation = 0.00° — the
  reference's forward-leaning neck lives in the **Head bone's origin offset**, not the
  neck angle: Head head-to-Neck-tail offset = (0, −31.4, −4.7) mm (31.4 mm forward).
  Our asset expresses the same forward lean as a 21°-tilted Neck bone. Aligning our
  neck to vertical drags the head+face flesh ~30 mm backward → face warp (user
  screenshot). Same convention mismatch applies to spine/head.
- General rule: the “mesh follows the bone re-bake” (LBS) step assumes the asset's
  bone↔flesh relationship matches the reference's. True for limbs; FALSE for torso
  and neck (two different ways to encode the same visual posture).
- NO_ALIGN = {Hips, Spine, Spine1, Spine2, Neck, Head, LeftShoulder, RightShoulder}.
  Once decided, DELETE the per-bone blend-factor machinery — a mechanism kept “just in
  case” only re-adds a rotating failure surface.

## Verify with region-rigidity numbers, not bone checks alone

- Face verts (Head weight > 0.5): delta vs pre-normalization must be a PURE global
  translation (the feet-glue lift, e.g. (0,0,+17.4) mm) with relative spread ≈ 0.000 mm
  (measured) = perfectly rigid face.
- Top-view render torso crop and eye-height-aligned face closeup: 0 px diff vs
  pre-normalization.
- Beware framing artifacts: the global feet-glue lift shifts the whole render — align
  cameras to a per-file feature (bbox center, eye height) before pixel-diffing, or the
  entire frame reads as “changed”.

## Eye/head consistency after rest moves (the user's acceptance criterion)

Eye objects are separate meshes skinned to Head (parent=None, scale=1); they
are re-baked by the LBS loop over ALL skinned meshes — assert both eye objects
are in that loop's input list ("largest mesh only" was a real historical bug).

**The failure mode a first-pass check misses: the eye-region FLESH carries the
defect, not the eyes.** Auto-weighting gives the eyelid/socket skin ≈ Head 0.91
+ Neck 0.09 while the eyeballs are pure Head. Whenever head and neck move
relative to each other — the rest normalization AND every later head-turn
animation — the lids lag ~3.9 mm against the stationary eyes and the user sees
the eyeball "bulging out of the socket". The eye centers' head-local positions
can be perfect (0.0001 mm) while this is happening: the eyes are innocent, the
flesh drifts.

Fix inside the normalization step, before the LBS re-bake: unify the eye-region
weights to Head. Radius derived from the measured eyeball objects (mean vertex
distance to their center = R_eye; no hard-coded mm): core within 1.5×R_eye →
pure Head, smooth falloff to 2.5×R_eye, other vertex groups scaled down
proportionally. Verify region-wide: every vertex in the region (not only
pure-weight ones) must match the Head bone's rigid delta (+dz), reported as
core max vs outer-transition-ring max (core ≈ 0 required; the ring keeps a few
mm by design). Keep also: (a) eye center in the Head frame before vs after —
identical; (b) never demand "head/eyes must not move" once torso matching is
intentional — compare displacement against the Head delta instead.

**Check-design rule: never audit only pure-dominant (>0.9999) vertices.** A
blended region (0.91/0.09) is invisible to dominant-bone checks — the rig
passes every "pure vertex" assert while the blended flesh drifts. Filter by
REGION (distance to the feature), then test rigid-follow over everything in it.
The user's visual report outranks center/rigid checks: when they report a
feature moved or bulged after a bone change, audit the surrounding region's
skin weights first.

Ortho A/B renders (identical camera, ortho — perspective closeups exaggerate
eye bulge) are acceptance material for the user, not evidence: absolute vision
readings of eye closeups contradict themselves (one read called a real 3.9 mm
lid drift "no difference", another called pre-existing geometry "bulging").
Numbers decide; the render confirms with the user.

## Cost that remains

Straightening the asset's stance pulls knees/ankles ~5-6 cm inward per side
(user accepted as-is). Torso/neck/head introduce NO extra head move now (they are
untouched; only the global feet-glue lift applies). Report consequences as
consequences, not defects. Downstream stages (walk retarget, exports) must be
regenerated after any normalization change.

**Stage-05 deliveries = THREE blends** (user requirement): bound-unstandardized /
standardized / action-tested. The unstandardized file is a first-class product
(comparison baseline + fallback), not an intermediate.
## The effect

Aligning ALL bones to a Mixamo T-pose reference AND re-baking the mesh via LBS
(the 03B rest-normalization step) is correct for retargeting (D=I, avoids the
内八/猫步 compensation bugs) but it ROTATES the visible body. A wide-stance AI
asset (measured: femur abducted +8.7° vs the Mixamo reference's +0.35°) gets
straightened to vertical, pulling knees ~50 mm and ankles ~60 mm inward per
side; the thigh flesh must now bridge from the wide pelvis to the pinned-down
knee — the user reads this as X-shaped / knock-kneed legs in the static T-pose.
The reference value is NOT "too aggressive" — the distortion is inherent to
mesh-following normalization on a stanced asset.

## Diagnose numerically, never by eye or vision

- Bone level: per-bone frontal angle + head/tail x for femur / shin / foot in
  the pre- and post-normalization blends (expect: pre femur +8.7° outward-down,
  post +0.3° vertical; hip JOINT head x unchanged — the joint is the rotation
  pivot).
- Mesh level (what the user's eyes see): x-median of vertices in z-slices at
  hip / knee / ankle heights, per side. Compare pre vs post.
- Vision on such renders is unreliable: it called an X-stance render "legs
  basically straight, no obvious X or O". Numbers + the user's eyes decide.

## Reassure with evidence, not claims

Render one frame of the retargeted walk from the same project: the X stance is
a STATIC T-POSE artefact only. With D=I absolute orientation matching, the legs
in every animated pose follow the animation, so the stance disappears in
motion. (Verified: walk frame-1 render shows a normal stance.)

## Options to present (user decides — do not apply unilaterally)

1. Keep as-is — only the static bind pose is affected; animation is correct.
2. Partial alignment (leave a few degrees of abduction) — reduces the look but
   reintroduces a rest-difference compensation, i.e. the path that previously
   produced 内八/猫步; only with a fresh fix for that risk.
3. Mesh-level local compensation after normalization (geometry work; needs
   explicit user approval — respect any standing "don't sculpt" instruction).
