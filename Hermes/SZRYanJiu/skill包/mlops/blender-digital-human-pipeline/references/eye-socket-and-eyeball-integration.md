# Eye Socket Carving & Eyeball Integration (QR pipeline)

> Related: `script-file-health-audit.md` — batch encoding/compile check for when a pipeline script errors out with no logic cause (e.g. BOM corruption).

Use when adding working eyeballs (rotation-capable) to a head model in the v3 QR pipeline (delivery step folder `01A眼窝与眼球`; search triggers: 眼窝 / 眼球摆入 / 01A / iris / eye socket / eyeball).
Design validated 2026-08-05 on 01_highpoly_repair.blend (~960k verts, 8K tex). Full doc: `方案md记录/v3_QuadRemesher/01A眼窝与眼球/眼窝与眼球集成设计方案.md` (renamed from 08眼窝与眼球集成 2026-08-06).

## Pipeline placement (key decision)
- Eye socket is made on the **high-poly, between 01 repair and 02 QR** (delivery step folder `01A眼窝与眼球`, scripts `run_eye_socket.py` + `run_eyeball.py`).
  - High-poly already has a shallow socket (~4mm deeper than orbital rim, measured) — deepen it, keep natural lid shape.
  - QR re-topologizes the hole rim into clean quads for free.
  - 04 baking bakes socket depth into the normal map for the low-poly.
- **Eyeball is a separate object — never goes through QR/UV/baking.** It brings its own topology + textures (MetaHuman eye: 802 verts / 1536 faces / 1024 PBR tex per eye, diameter ~29mm, local origin at sphere center). It joins only at 05 rigging / 06 export.
- Fallback if QR mishandles the hole: carve socket after 02 on the quad low-poly instead (delete faces + push in). Try main plan first, decide with measurement.

## Iris center auto-localization (texture dark-pixel method) — VALIDATED then PAUSED 2026-08-06 (accuracy ceiling)

> **Status update 2026-08-06**: after reaching the v3 algorithm (IPD 71.7mm, pupil error 9/3px, vision-approved), the user judged the whole texture-dark-pixel approach to have an inherent accuracy ceiling and PAUSED it in favor of 3DDFA-V3 semantic face parsing. Ceiling reasons: (1) reliability depends entirely on painted-texture quality — on AI textures the pupil blurs into lash/eyeliner/shadow so "darkest disk" ≠ pupil center; (2) mm-level residual error persists after endless threshold/cluster tuning and does NOT generalize (untextured / closed-eye / makeup models each need re-tuning); (3) no semantic understanding — it bets "darkest = pupil", fails on makeup/shadow/reflection; (4) slow debug loop. Lesson: dark-pixel is a fine quick PROTOTYPE, not production-grade. Archived in `方案md记录/.../眼球定位_贴图暗像素法_暂停存档.md`. v3 below kept as best-effort fallback if 3DDFA unavailable.

Works when the texture has painted eyes (typical Tripo output):
1. Select an "eye band" vertex mask by geometry: head-top region, front side (tune per model; e.g. z in [zmax-0.20, zmax-0.125], |x|<0.06, y<-0.08 on a ~1.8m standing model).
2. For band verts, average their loop UVs (vectorized, see script).
3. Sample texture at those UVs, threshold brightness (12th percentile), split dark verts by x sign (left/right).
4. Centroid of each dark cluster = iris center. Got 500+ dark verts/eye, stable. Measured: IPD 47mm; left (-0.0241,-0.1163,1.6517), right (0.0229,-0.1168,1.6507).
Reusable script: `scripts/iris_detect.py` (edit the blend path at top).

**Pitfall (2026-08-06): centroid MUST be noise-robust.** Plain `mean` of dark verts gets dragged off by dark texture blemishes (lower-lash shadow / 卧蚕 dark patches) — measured on right eye: dark-vert z range spanned 1.632–1.667 (35mm!) because low-z noise crept in, pulling the mean 2.8mm below the left eye → eyeball placed 2.8mm low on that side, GUI showed mismatched heights. Original high-poly eyes are level; the skew was 100% detection noise. **Fix: trim outliers before centroid** — sort dark verts by z, drop top+bottom 20%, then mean. Converged at 20% (further trimming eats real iris pixels). After trim L/R iris z agree to within the model's true ~2mm asymmetry. Never "fix" by symmetrizing L/R — that breaks models whose eyes genuinely differ; fix the estimator instead. (User: "不是一股脑对称化…那哪天真换了个眼球位置不相同高的，你也对称吗？你要去优化你的算法跟方案". Symmetry is an output to VERIFY against, never an input to enforce, unless the user explicitly asks for a symmetric stylization.)

**Pitfall #2 (2026-08-06, deeper): the band seed/window can miss the true pupil entirely.** Even with robust centroid, the old seed-point + 20mm-radius band was centered on the inner canthus, so the sampling window never reached the lateral true pupil; inner-canthus/lash dark verts then dragged the centroid toward the nose — measured pupil projection off by 79/68px inward, IPD underestimated 42% (46mm vs true 71.7mm). **Fix (v2 algorithm, physically grounded, no guessing)**: ① full-face eye band (z 1.60–1.70, y<-0.08, |x|<0.08), no seed point; ② split L/R at nose midline x=0; ③ per side take darkest 10%, K-means (k=2) on x-z plane → **outer cluster (larger |x|) = true pupil region**, inner cluster = inner-canthus/lash noise; ④ within outer cluster take darkest 30% (pupil darker than lid shadow), centroid = pupil. Validated vs vision-marked pupil pixels: L off by +9px, R by -3px (was 79/68). Height diff 0.1mm. Diagnostic path: vision-check the texture eye region (beware cropping the wrong UV island → false "eyes closed"), render the high-poly front face to confirm eyes are open, then forward-project 3D candidates to screen pixels to measure error.

## Measurement protocol before carving
- **Eye axis**: mean normal of verts within 20mm of iris center (e.g. left (-0.53,-0.83,0.20)). NOTE: this flares outward (see Eyeball placement pitfall) — use it for carving direction only, never for eyeball orientation.
- **Depth profile**: for inner verts (d<20mm) and rim ring (d 30–42mm), project (v-center) onto (-eye_axis); compare median → verdict "已有凹陷" if inner median > +1.5mm.
- **Eye fissure / IPD**: ring span along x (measured ~50mm wide band), IPD from the two iris centers.

## Socket construction
1. Opening: ellipse ~26-28mm wide × 11-13mm tall centered on iris center, in plane perpendicular to eye axis. Sized to the measured eye fissure (~31.5mm wide) so lid edges overlap the ball (opening slightly smaller than fissure = "eyelid wraps the eyeball" look). Make width/height script parameters.
2. Delete faces inside → boundary loop.
3. Push-in: verts within ~15mm of opening, displaced along eye axis with smooth falloff, max depth ~10mm below original surface → bowl.
4. **Seal the bowl (user correction 2026-08-06 — open hole is NOT acceptable)**: deleting faces + pushing in leaves a see-through hole into the head interior (backface red visible through the opening). Must close the bottom with a concave cup: bridge/fill the boundary ring into a closed bowl surface (grid-fill or edge-loop fill on the pushed-in ring), so the socket is a sealed cavity. User's words: "你只掏了洞，但是没补洞啊，现在后面都漏出来了".
5. Cleanup: merge boundary by distance; verify manifold everywhere except the two holes.
- The painted eye on the texture becomes hidden behind the eyeball — no inpainting needed. Socket inner-wall texture is invisible in use; leave it.

## Eyeball placement (corrected 2026-08-05: use global forward, NOT eye-socket normal)
**PITFALL — strabismus risk**: the eye-socket normal measured above flares OUTWARD (left (-0.53,...), right (+0.57,...)) because the detection region includes lateral orbital wall. If eyeballs are placed/oriented along the socket normal, both eyes splay outward. Socket normals are OK for carving direction; eyeball placement must use the GLOBAL FORWARD direction.
- Center = iris center + global_forward(-Y) × ~10mm (NOT eye axis). Cornea apex (radius 14.5mm) protrudes ~4.5mm beyond original surface through the opening — the standard "lids catch the ball" look.
- Orientation: pupil local axis is ASSET-DEPENDENT — do not trust the texture-centroid estimate. For this eye_01.glb the pupil is at local **−Y** (down), NOT +Z as the 08-05 texture estimate suggested (see "Pupil orientation" below). Rotate the measured pupil axis → global −Y; both eyes → parallel forward gaze = 平视. Verify in GUI; fine-tune around the eye axis.
- Cross-section render through ball center: lower half occluded by lid edge, 3–5mm protrusion, no skin penetration outside the opening.

## Calibrating a detector against ground truth via forward-projection (reusable, broke the 08-06 loop)
When a detector (iris, landmark, any 3D feature) keeps disagreeing with what the user sees, STOP tuning it blind. Calibrate in pixel space:
1. Render the high-poly front view with a KNOWN camera (record location/rotation/fov/resolution).
2. Have vision_analyze mark the target's pixel coords on that render (e.g. "left pupil at x=27%, y=11%").
3. Forward-project your detector's 3D output to screen with `bpy_extras.object_utils.world_to_camera_view(scene, cam, co)` → compare pixels directly. This gave the exact signed error (iris detector 79/68px too far toward the nose) and proved the bias was toward the midline — pointing at the inner-canthus contamination, which the v2 outer-cluster fix then removed.
- Back-projecting a marked pixel to 3D (camera-ray → BVH ray_cast) is error-prone (fov/aspect/matrix pitfalls shot the ray into the floor twice); prefer forward-projection of candidate 3D points for validation, and reserve back-projection for when you already trust the camera setup.
- Do NOT iterate the detector against vision's qualitative prose ("looks protruded", "looks off") — only against its pixel coordinates, and only after the render actually shows the feature (a gray un-textured ball / a cropped UV island makes vision hallucinate).

## Eyeball size: place at scale 1.0 first, decide by render
29mm MetaHuman eye vs measured fissure ~31.5mm (only 2.5mm margin); Tripo heads often have small features (this model: IPD 47mm vs adult avg 62-64mm, head width 160mm normal). The eye may look too big. Protocol: place at 1.0, render front + cross-section; if lids can't cover / too protruded / too much sclera visible, scale UNIFORMLY to 0.85-0.9 (~24.6-26mm). Never non-uniform scale (flattens the ball). Recheck hole fit after QR if QR changed the opening (>1-2mm drift → adjust inset/protrusion).

## Measurement pitfalls
- Head bbox on a T-pose model is contaminated by arms (got 1.7m "head width" = armspan). Restrict head region: |x| < 0.08 (and z > top of shoulders).
- Eye-fissure width: band of verts 8-20mm from iris center AND within ±8mm of iris z → x span (~31.5mm), NOT the full 50mm ring span (that includes orbital rim).
- Eyeball pupil direction from its own texture: UV-sample, darkest 2% pixels, centroid direction from origin; test both v-flips (dark cluster identical either way if pupil sits near texture middle row).

## Rigging & export
- Mixamo skeleton has NO eye bones: manually add `eye_L` / `eye_R` parented to head, positioned at ball centers.
- Each eyeball mesh: 100% weight to its own eye bone. Bone rotation drives the ball; GLB consumers animate via bone quaternions.
- GLB export contains skin mesh + 2 eyeballs + skeleton; eyeballs keep own materials/textures.

## 3DDFA-V3 verdict (researched 2026-08-05, PIVOTED TO PRIMARY 2026-08-06)
CVPR2024 repo (wang-zidu/3DDFA-V3): photo → BFM mesh (35,709 verts) + 68/106/134 landmarks + 8-part segmentation incl. eye masks. Heavy env (PyTorch + nvdiffrast/cython renderer + pretrained weights).
- 08-05 verdict: not needed when input is a textured 3D mesh (dark-pixel lighter). **08-06 reversal**: user judged dark-pixel at its accuracy ceiling and chose 3DDFA as the PRIMARY eye-localization route (semantic "where is the eye", robust to untextured/closed-eye/makeup, generalizes). Dark-pixel v3 kept only as best-effort fallback.
- Eye-region ground truth in `face_model.npy` `annotation` (8 parts, BFM vertex indices): **right_eye = 440 verts, idx 2087–6343, 791 tris; left_eye = 440 verts, idx 10075–14326, 787 tris**; eyebrows 380 each; nose 1282. Use these BFM indices to pull the eye submesh / landmarks, then map onto our high-poly via the known render camera (forward-project, see calibration section).
- Pipeline: render high-poly front (known camera) → 3DDFA-V3 infer (2D eye landmarks + seg mask) → back-project to mesh → eye region. Deploy log: `方案md记录/.../01A眼窝与眼球/3DDFA-V3部署调研.md`. **Full Windows deploy + 5 hard-won env pitfalls (PYTHONPATH pollution / numpy<2 / opencv==4.9 / mtcnn lazy-import / cpu-cython-renderer via VS2022 BuildTools) + eye-data extraction code: `references/3ddfa-v3-deployment-windows.md`.**
- **HuggingFace big-file download on this machine's proxy**: 50MB+ blobs die mid-transfer through 127.0.0.1:7897 (`SSL: UNEXPECTED_EOF_WHILE_READING` / CURLE_PARTIAL_FILE) while small files pass. Workaround (validated): use mirror **hf-mirror.com** (same paths), bypass proxy `curl --noproxy '*'`, resume `curl -C - --retry 5 --retry-delay 2`; re-run on partial until size matches; verify by loading the file (truncated .npy → UnpicklingError). Keep proxy for PyPI/GitHub/API, use direct-mirror only for the big weights.

## 3DDFA→mesh production path (VALIDATED end-to-end 2026-08-06)
Full working loop (scripts in 01A眼窝与眼球/scripts/): orthographic front render (`render_front_for_3ddfa.py` — ORTHO cam, record params to `cam_params.json`, aim z = bbox 88% height else eyes crop out of frame; wpp≈0.39mm/px at 1024²/0.40m) → 3DDFA `demo.py -i <img> -o results` (CPU works, ~30s; ldm68 eye pts = idx 36-41 R / 42-47 L; eye spacing from px × wpp cross-validates geometry: 177px→69mm vs dark-pixel 71.7mm ✓) → ortho back-projection (`backproject_3ddfa.py`: pixel→cam-plane point via right/up axes, ray along +Y, BVH ray_cast). Then `USE_3DDFA=True` in eye_socket_config feeds these centers into socket carving instead of dark-pixel.
- **Robust back-projection pitfall**: a single center-ray can hit the upper eyelid margin instead of cornea (normal pointing -Z/up instead of -Y/front). Fix: cast 9 rays (center + 8 neighbors at ±1.5px), pick the hit whose normal is most forward-facing (max -normal.y).

## Blender headless performance pitfall
- `img.pixels[:]` Python iteration on an 8K×8K texture timed out (>300s). Always use `img.pixels.foreach_get(buf)` into a preallocated numpy array.
- Same for vertices/normals/loops: `mesh.vertices.foreach_get("co", arr)`, `mesh.loops.foreach_get("vertex_index", arr)`, `uv_layer.data.foreach_get("uv", arr)` — never Python-loop over 1M-scale elements.

---

# Implementation-phase pitfalls (validated 2026-08-05, headless Blender 5.1)

These were hit while actually building the 01_1 socket + 01_2 eyeball scripts. The design above is the plan; these are the ground-truth corrections from running it.

## Blender 5.1 API changes (breaks older scripts)
- `bpy.ops.mesh.select_all(action='ALL')` raises `TypeError: enum "ALL" not found`. Valid actions are only `'TOGGLE' / 'SELECT' / 'DESELECT' / 'INVERT'`. Use `'SELECT'` to select all.
- `bpy.ops.mesh.normals_make_consistent(inside=False)` still works.
- OBJ import is `bpy.ops.wm.obj_import()`; FBX/GLTF use `bpy.ops.import_scene.fbx` / `.gltf` (no `import_scene.obj`).

## Face deletion: deletion criterion + post-delete index invalidation (both caused real bugs)
- **Criterion**: delete faces whose **face CENTER is inside the ellipse** (`f.calc_center_median()`), NOT faces with ANY vertex inside. The vertex-based test leaves dozens of broken "half-cut" faces along the rim (their center lies outside the ellipse but 1-2 verts inside) — these show up as residual surface inside the hole and fail the "center region has 0 in-face verts" check.
- **Post-delete re-indexing**: after `bmesh.ops.delete(...)`, vertex indices change (`nv` drops). Any mask computed BEFORE the delete (e.g. `in_ellipse`) is now misaligned with the vertex array — using it raises `ValueError: operands could not be broadcast (964731,) (965000,)`. RECOMPUTE all masks from the fresh `mesh.vertices.foreach_get("co", ...)` after deleting, before the push-in step.

## Opening ellipse half-height must cover the fissure (rz=6mm left 70+ residual faces)
- First attempt used rx=13mm, rz=6mm. Result: ~70 residual faces inside the hole, their centers at ellipse value `ell = 1.0–1.66` (just OUTSIDE the ellipse) but 3D distance only 7.7–8.5mm from iris center — i.e. the eye fissure is TALLER than 12mm. Fix: **rz ≥ 9mm (18mm total height)**. After rz=9mm, center-region in-face verts = 0 on both eyes (verified).
- Verify hole completion numerically, not just visually: for each eye, count verts within `d < 8mm` of iris center that still belong to any face — must be 0. (`verify_hole.py` pattern: build `in_face` bool array over all polygons, check center mask.)

## NEVER run global `normals_make_consistent` (Shift+N) on the repaired high-poly (user correction 2026-08-06)
The 01A socket script ended cleanup with `bpy.ops.mesh.select_all(SELECT)` + `bpy.ops.mesh.normals_make_consistent(inside=False)`. User then opened `01_1_eye_socket.blend` and found the ENTIRE lower body red in face-orientation view — while the input `01_highpoly_repair.blend` was verified 100% clean by the user in GUI. Root cause: Shift+N propagates from a seed face along adjacency; deleting ~700 eye faces cut adjacency and left open boundaries, so the propagation flipped huge distant regions (non-deterministic, same failure documented in 法线朝向修复方案.md: "Shift+N 不可靠，不收敛，每次结果不同").
Rules:
- The 01-repair output normals are ALREADY correct — downstream steps must NOT re-run global normal unification. Treat the input normals as ground truth.
- Any local edit (face delete / vertex push) only changes normals of the touched ring; fix locally via bmesh (`bmesh.ops.recalc_face_normals` on the affected faces only) or leave as-is.
- This is the second time this exact mistake was made after being documented — check for `normals_make_consistent` in any new mesh-editing script before running. Root-cause deep-dive (why Shift+N flips watertight-broken meshes + the 4 geometric causes + GUI rescue path): `references/shiftn-normals-make-consistent-pitfalls.md`.

## GLB eyeball asset traps (MetaHuman eye_01.glb)
- **Name/position inversion**: `NewMetaHumanCharacter_Eye_L` sits at x=+0.033 (RIGHT side), `Eye_R` at x=-0.033 (LEFT side). Do NOT assign left/right by object name — assign by sign of `obj.location.x`.
- **Local center offset**: the ball's local-space centroid is NOT at origin — bounds are symmetric (±14.5mm) but vertex mean ≈ (0, -2.1mm, 0). Compensate +2.1mm on the placement axis or the ball sits 2mm off target.
- **Gray-ball texture issue**: the GLB material mixes vertex color with the image via a Mix node (`Image Texture → Mix.A`, `Color Attribute → Mix.B`, Fac default 0.5) and renders gray in EEVEE. Setting Fac=1.0 picks the VERTEX COLOR (still gray). Correct fix: remove all links into Principled BSDF `Base Color` and connect `Image Texture.Color → Base Color` directly.

## Eyeball placement: RESOLVED 2026-08-06 via geometric anchor on the lid-edge rim (replaces blind scalar push-in)
The 08-05 "push iris center along global -Y by a guessed inset" approach failed every vision check. The 08-06 fix computes the ball center from MEASURED socket geometry; user confirmed normals + pupil correct in GUI. Working method:
1. **Anchor on the lip rim, not the iris center.** From the carved `01_1_eye_socket.blend`, collect the hole's open-boundary verts (edges with `len(e.link_faces)==1` whose midpoint sits in an annulus ~0.6–2.6× the ellipse radii around the iris center, |y − rim_y|<0.03). Their x/z mean = true opening center; their min y = front lip edge (`rim_y`). Measured: L center (−0.0270, 1.6681) rim_y −0.1182; R center (0.0193, 1.6629) rim_y −0.1216.
2. **Ball-center y formula + the ±Y SIGN PITFALL.** Model faces −Y, so "outward/toward viewer" = decreasing y, "into head" = increasing y. Require cornea apex (= ball_center_y − radius) to sit CORNEA_PROTRUDE beyond the lip: `ball_center_y = rim_y + radius − protrude` (+Y pushes INTO the head). First attempt used `rim_y − (radius − protrude)` (wrong sign) → ball burst 23.4mm out (exophthalmos). Correct sign → 2.4mm protrusion.
3. **Per-side anchors, NOT mirrored.** The two openings are NOT symmetric about x=0 (L x=−0.0270, R x=+0.0193 — centerline offset 3.7mm). Widening both by the same WIDEN keeps the asymmetry. Measure each side separately; don't assume symmetry.
4. **GUI-review fine-tune knobs** (all in eyeball_config.py; change one number, re-run): `EYE_PUSH_BACK` (extra +Y inset mm), `EYE_WIDEN` (per-side ±X), `CORNEA_PROTRUDE`, `EYE_SCALE`. Subjective protrusion/symmetry tweaks are unreliable via render+vision — get the target mm from the user's GUI read and set it directly.
- Quantitative verify (authoritative): world bbox of each eye, cornea apex = min(bbox y), protrusion = rim_y − apex_y, target 3–5mm. Replaces the old "cross-section render" advice.

## Pupil orientation: PUPIL_LOCAL_DIR must be the MEASURED pupil axis, and shortest-arc is fragile
- 08-05 measured pupil at local (0,−0.04,+0.997) ≈ +Z, rotated +Z→global−Y. 08-06 GUI review: pupil pointed DOWN. The −0.04 y-noise, fed through `rotation_difference` (shortest-arc), gave quaternion (0.721,0.693,0,0) that tilted the pupil off-axis.
- Ground truth for THIS asset: pupil sits at local **−Y** (down). Fix: `PUPIL_LOCAL_DIR=(0,-1.0,0.0)` (clean cardinal axis, not a noisy measurement) → rotate to global (0,-1,0). Verified pupil_world_y = −1.000 (exactly forward) on both eyes.
- Lesson: re-derive the pupil axis from the actual rendered orientation; prefer a clean cardinal axis over a noisy measured vector for `rotation_difference`.

## Socket-cup generation on an almond contour (2026-08-07 status: STILL UNRESOLVED — user rejected BOTH extremes)

> ⚠️ **Read this before trusting any recipe below.** On 2026-08-07 the user rejected the flat-bottom pit too: "眼窝形状不对啊…跟直接在y轴挤出了似的，边缘非常锐利，也没有眼窝的那种'碗'形状" and clarified explicitly: **"眼窝剖面要更像球面碗(底部圆、坡度连续), 不要直筒/平底"**. Neither the single-pole cone NOR the flat pit is accepted. The deliverable is a **smooth spherical bowl**: round bottom, continuous slope, soft rim. As of session end this is NOT achieved; an earlier draft of this doc called the flat pit "the correct deliverable" — that was WRONG (user overrode it).

The parametric lathe and single-pole fan BOTH produced **starburst / corrugation破面** once the opening became the 3DDFA almond contour. 6+ iterations failed. Root causes, in order of discovery:
1. **Single-pole triangle fan** (`vpole` + last-ring fan) collapses to a sharp star — every face shares one apex, straight-line rim→apex = zero curvature = corrugated flat triangles. Already rejected 08-06, but the multi-ring replacement had its own failure:
2. **Multi-ring inner-scaling self-intersects on an almond**: ring0 verts are non-uniformly distributed (sparse at the pointed canthi), so shrinking inner rings toward the centroid stretches those quads into thin self-crossing wedges. Measured: in-cup normal scatter mean 65.8°, 562/639 faces >40° off the mean normal = real self-intersection, NOT a render artifact. **Quantified root cause (2026-08-07)**: boundary-ring vertex spacing measured 0.70–2.91mm (mean 1.51, std 0.49, 29/68 gaps >1.5mm) — the 4× spacing spread is what stretches sparse-region quads into thin wedges during shrink. This is WHY uniform resampling (below) helps.
2b. **Push-in (压凹) is itself a starburst source (2026-08-07)**: the old push-in displaced verts within 15mm by xz-distance with cosine falloff — on an ALMOND opening the canthus verts are closest to center so get pushed deepest while neighbors move less → depth discontinuity → rim sawtooth spikes. Even "hole + push-in only, no cup" rendered rim starburst. Fix: REMOVED push-in entirely (凹陷由碗负责); boundary-ring verts now stay on the smooth face surface.
3. **ring0 y-spread breaks quad coplanarity**: if the boundary ring was pushed by the earlier push-in step, its verts span 11.6mm in y; bridging that to a flat bottom ring makes every side-wall quad non-planar → twisted starburst. Fix: either exclude ring verts from the push-in (push only the lid-transition zone, skip verts within ~2mm of the contour), or flatten ring0 to `rim_y = mean(ring0.y)` before bridging.
4. **Distance-threshold ring detection over-selects**: `dist_to_poly < 3mm` grabbed 70 verts including cup-interior verts, vs the TRUE open-boundary loop of 38. Bridging the wrong set = misaligned 之字形穿插. **Fix: topological closed-loop walk** — build vert→open-edge map, start at an open edge near the eye center, walk "next open edge ≠ the one you came from" until you return to the start vert. That yields the exact ordered boundary loop (no threshold, no angle sort — an angle `atan2` sort SCRAMBLES the topological order on an almond and causes穿插 by itself).

**Working recipe (SUPERSEDED 2026-08-07 — geometrically clean but user-REJECTED as "直筒挤出不像碗")**: topological closed-loop walk → ordered ring0 → flatten ring0 to rim_y → inset bottom ring at rim_y+CUP_DEPTH (~90% scale) → bridge quads → ngon cap. Result: 0 open edges, 0 non-manifold, depth ~15mm — BUT user verdict: "跟直接在y轴挤出了似的，边缘非常锐利，也没有眼窝的那种'碗'形状". The flat pit is geometrically valid and visually WRONG. Do not deliver it.

**User's actual requirement (2026-08-07 verbatim decision)**: 球面碗 — spherical bowl profile, bottom ROUND not flat, slope CONTINUOUS, rim SOFT not sharp. The earlier "内部是个坑就好，反正有眼珠挡着" was about floor DETAIL level, not license for a cylindrical pit.

**Validated partial ingredient — uniform-angle resampling kills bowl-center starburst (2026-08-07)**: a free-standing test bowl with 48 uniform-angle verts (θ=2πi/48) × spherical profile (scale=cos(t·π/2), depth=sin(t·π/2)) + ngon floor cap was vision-confirmed "碗心平滑无星爆、底部圆不尖、无放射折痕". Remaining gap: rim comb-teeth because the test bowl was NOT stitched to the face hole (free-floating grid). The unfinished integration problem at session end: uniform resampling changes vertex positions/count vs the real boundary ring → vert-sharing with ring0 breaks → needs `bridge_edge_loops(ring0 → resampled ring)` or snap resampled verts to nearest true boundary edges, then uniform inner rings. That stitch is unvalidated.

**Candidate next routes (unvalidated — pick deliberately, don't blind-iterate)**:
- (a) resample ring0 uniformly, snap each sample to the nearest point on the true boundary loop (preserves seam), then spherical inner rings + ngon floor;
- (b) bmesh `grid_fill` on the true ring (clean quads on uneven loops; may need even count + span/offset tuning), then shape the fill into a bowl;
- (c) user hand-finishes the bowl in GUI; agent delivers clean almond opening + depth markers.
The dead-end record is long — STOP and ask the user before another blind round.
- Verify with a bounded-depth probe, not a raw max: cup-interior verts are `point_in_polygon(x,z) AND rim_y-5mm < y < rim_y+30mm`; cup depth = max(y)−rim_y of those. An UNBOUNDED `max(y)` inside the polygon catches the back of the skull (~+0.10) and falsely reports 200mm depth.
- CUP_DEPTH ~15mm is enough; 20mm risks poking the floor into the skull cavity.
- **Patch-loop pitfall (2026-08-07)**: repeatedly patching the same function across turns produced a DUPLICATED code block (the topological ring-walk appeared twice) that still lint-passed. After any patch to a heavily-edited function, READ the whole function back and check for duplicate blocks / stale variable refs (e.g. a print still referencing a deleted `pole`/`N` var → NameError at runtime).

## Vision misreads ngon triangulation as "starburst" — trust the manifold metrics, not the shaded render (2026-08-07)
Repeated this session: a WORKBENCH/clay render of a correct flat-bottom pit was judged by vision_analyze as "放射星爆碎面/破面" across 4 consecutive iterations — because the ngon floor triangulates into a fan at render time and a flat fan READS as a starburst to the model. The mesh was actually clean (0 open edges, 0 non-manifold). Same class as the 08-06 "gray ball reads as protruded" lesson, new manifestation. Rules:
- For "is this mesh broken / does it have holes / is it a星爆" questions, the vision model CANNOT tell render-time ngon triangulation from real self-intersection. Do NOT iterate mesh code against vision's prose on shaded renders.
- Authoritative checks (quantitative, run in Blender): open-edge count, non-manifold-edge count (`len(e.link_faces)!=2`), and in-region normal scatter (mean angle of each face normal to the region mean; >40° on many faces = real穿插). All three are cheap bmesh/numpy probes.
- If you DO ask vision about topology, render a WIREFRAME (`show_xray_wireframe=True`), not a shaded clay — and even then treat "looks like a starburst" as unproven until the metrics say so.
- This cost ~6 wasted iterations. When metrics say clean but vision says broken ≥2 rounds, STOP, show the user the metrics, and move on.

## Bowl-seal history (SUPERSEDED 2026-08-07 — see "Socket-cup generation on an almond contour" above for the current method)
> ⚠️ The half-ellipsoid lathe described below worked on the old symmetric-ELLIPSE opening but FAILED (starburst/穿插) on the 3DDFA ALMOND contour. Do not use it for the almond opening. Kept for the failure analysis only.
The first bowl-seal (`seal_socket_bottom`) fanned all triangles to ONE bottom point → a **sharp cone with flat corrugated facets**, which the user rejected outright: "效果极差，还有很多瓦楞感平直的表面，我想要的是个半椭圆类似，而且是有一定的平滑度的". Root causes of the cone's badness: ① all faces share one apex = cone not bowl; ② straight-line rim→apex = zero curvature = corrugated flat triangles; ③ it amplifies the jagged deleted-face ring. **Replacement (`make_eye_cup`)** — anatomical smooth half-ellipsoid lathe:
1. **Ring 0 = the actual open-boundary ring (SHARED verts, not new).** Collect open edges (`len(e.link_faces)==1`) in an annulus (0.5–2.8 × ellipse radii) around the iris center, sort by `atan2(z−cz, x−cx)`. Sharing these verts makes the cup seamless with the face opening — do NOT place ring 0 at a fixed y (first attempt put it at iris-center y, leaving a 13.8mm floating gap to the real lip at −0.1264).
2. `rim_y = mean(ring0 y)` (the ring's real depth, NOT the iris-center y).
3. Inner rings j=1..N−1: keep each vert's angle θ from ring0, but RECOMPUTE x/z from the ellipse `x=cx+rx·scale·cosθ, z=cz+rz·scale·sinθ` with `scale=cos(t·π/2)`, and depth `y=rim_y+max_depth·sin(t·π/2)`. cos-scale gives a quarter-ellipse profile (smooth bowl, continuous at the pole); recomputing x/z (instead of scaling the jagged ring) removes the corrugation.
4. Pole = single vert `(cx, rim_y+max_depth, cz)` (hemisphere south pole, curvature-continuous, not a spike).
5. Faces: ring-to-ring quads `faces.new((a,d,c,b))` wound so inner wall faces the eyeball (−Y); last ring → pole as a triangle fan `faces.new((last[i], vpole, last[i2]))`.
Got L=104-ring→832 faces, R=96-ring→768 faces, 12mm deep. Vision confirmed: smooth bowl, seamless lip, continuous transition, no cone/corrugation. Params in config: `CUP_RINGS`(=8), `CUP_DEPTH`(=0.012), `CUP_SEGMENTS`. Verify seamlessness by counting open edges with midpoint inside the ellipse (r²<0.8): must be 0.
(Legacy `seal_socket_bottom` kept below for reference only — do not call it.)

The "seal the bowl" requirement had no method until 08-06. Working impl: find open-boundary edges near the iris center (same annulus test as the rim anchor), collect their verts, **sort by `atan2(z−cz, x−cx)` around the opening center** to order the ring, add one bottom vert at `(cx, rim_y + SOCKET_DEPTH*CUP_DEPTH_RATIO, cz)` (CUP_DEPTH_RATIO=1.5 → 15mm deep), then `bm.faces.new((ring[i], ring[(i+1)%n], bottom))` triangle fan. Got L=87 / R=81 fan faces, hole sealed. Call AFTER make_eye_socket, per eye. (NOTE: single bottom point = flat floor. If QR/visual review shows the flat floor, subdivide the fan or grid-fill instead; not yet flagged by user.)
- Verification-script pitfall: an "open edges near eyes" counter FALSE-POSITIVES on the two eyeball meshes (a separate ball has an open boundary by nature). Scope the open-edge check to the skin mesh, or exclude eyeball objects.

## Vision model vs quantitative geometry — trust geometry when they conflict
08-06: bbox math said 2.4mm protrusion (in-spec), vision_analyze said "ball bursting out / half the cap exposed." They contradict because the eyeball rendered GRAY (texture link not rendering in EEVEE) → a gray matte ball reads as "sphere pasted on face" to the vision model regardless of true depth. User GUI check settled it (normals fine, pupil forward). Rules:
- For numeric placement questions (protrusion, symmetry in mm), compute from world bbox — do NOT ask the vision model.
- vision_analyze is only for qualitative presence/absence (is a pupil visible, is the hole see-through), and only AFTER the material/texture actually renders.
- When vision and measurement disagree, show the user the measurement and defer to their GUI read — don't iterate the parameter against the vision model's opinion.

## The exophthalmos debugging spiral (biggest lesson of 2026-08-06)
After 3DDFA placement, vision kept judging the eyeball "整球凸出/蛙眼" across 7+ parameter iterations (3DDFA cornea point → rim-back-projection → lid-apex → lid-line → fitted-sphere ± push-back). Each fix moved the ball 5-20mm; the vision verdict never changed. Root cause found LATE: **the Tripo high-poly's eyes are PAINTED bumps — there is no eyelid geometry wrapping anything.** Carving the socket deletes that painted skin, so the inserted ball has NO lid geometry around it; the front view then ALWAYS reads "bare sphere pasted on face" at any plausible depth. Quantitative ground truth that finally settled placement: ① sphere-fit the original painted bump (`debug_eye_spherefit.py`, 2-round least-squares on verts <16mm xz-radius: fitted center y≈-0.1202, r=16.6mm, resid 1.4mm — the "virtual original eyeball" the lids were sculpted against); ② brow-nose silhouette line y at eye height (interpolate brow apex y / nose apex y to eye z; here -0.1358) — cornea apex must sit at/inside this line. Ball center = fitted center (x/z from 3DDFA, y from fit) + small push-back. Verification: temporary ad-hoc script asserting `|actual_pos - expected_pos| < 3mm` per eye — caught a config/product desync (blend generated with stale PUSH_BACK value).

Rules for this failure class:
- When vision and quantitative bbox math disagree REPEATEDLY (≥3 rounds), STOP iterating the parameter. The disagreement usually means the MODEL lacks the geometry the vision model expects (here: lids), not that the number is wrong. State the geometry-gap hypothesis to the user and let them pick the route (proceed / push deeper / rethink with MetaHuman lid topology) instead of silently burning more loops.
- `sphere-protrude = skin_front_y - sphere_front_y`: spell the sign convention out in the script comment or you WILL read it backwards mid-spiral (negative = sphere in front of skin on a -Y-facing model).
- Rim/lip measurement on a SEAMLESSLY-SEALED cup cannot use open-boundary edges (make_eye_cup shares ring0 verts → no open edges at the lip; only ~49 stray open edges elsewhere in the whole mesh). Deterministic alternative: pole_y = max y of verts within ellipse r²<0.6 and within a 20mm depth band behind the eye → rim_y = pole_y − CUP_DEPTH. Blind `min(y)` over a rim band catches protruding lid skin; unbounded `max(y)` catches the back of the skull — both wrong, bound the band.
- Socket delete criterion on painted-bump eyes: a y-window `abs(fc.y-cy)<0.020` misses the most-protruding lid skin (apex 20mm+ in front of the 3DDFA cornea point). Delete ellipse-interior faces with `fc.y < cy + 5mm` instead.
- Cup depth must contain the ball's back pole: 12mm cup vs 29mm ball guaranteed ~440 bowl-wall verts inside the ball (max 11.5mm penetration). 20mm cup is the minimum for a 14.5mm-radius ball seated near the rim.
- Config↔product sync: after any config change, RE-RUN the placement before verifying; verify expected position from the SAME config constants the run used.

## Headless run + vision verify pattern that worked
- Run: `cd <scripts_dir> && "<blender.exe>" --background --factory-startup --python run_xxx.py > out.txt 2>&1; grep -a "keyword" out.txt` (the `cd` matters for `sys.path.insert(0, os.path.dirname(__file__))` module imports).
- Vision model repeatedly misread gray WorkBench/EEVEE renders as "pure gray ball with no pupil" when the texture wasn't connected — always fix the material link FIRST, then re-render, then vision-verify. Also vision_analyze on these renders timed out often (Gemini free tier); retry after 45-60s rather than concluding failure.

## 2026-08-13: back-of-head penetration (Y-constraint) + opening-too-small margin (user GUI corrections)

### A. "后脑勺又穿透了" — any 2D-region normal-flip sweep MUST constrain Y (depth)
`fix_socket_normals` flipped every face whose center was inside the 3DDFA eyelid polygon AND `normal.y > 0`. The bug: `point_in_polygon(fc.x, fc.z, poly)` tests only the **X,Z projection**, and the eyelid contour's XZ box passes straight through the head — the back of the skull has faces at the SAME X,Z that legitimately point `+Y` (outward/backward). Those 395 back-of-head faces got flipped to `-Y`, and from the back view the head looked see-through ("穿透"). Fix: add `fc.y < 0` to the flip condition (socket + bowl all live on the front face `Y<0`; back of skull is `Y > +0.05`). Verified: 391 back faces all `+Y` after.
- **General rule**: any "flip/recolor/delete faces inside region R" where R is defined by a 2D projection (XZ polygon, XY mask, UV rect) implicitly selects a COLUMN through the whole mesh, not a surface patch. Always add a depth bound (Y window, or dot(face_center, region_normal) sign) unless the region truly spans the full thickness. This is the same class as the earlier "unbounded max(y) catches back of skull" lesson — projection regions pierce the head.

### B. Opening too small — 3DDFA almond contour alone carves only the eyeball area, user wants the FULL eyelid opening
The 26.8×9.7mm almond contour (6 pts back-projected) deletes faces strictly inside the fissure rim — the user's GUI annotation showed the red (carved) outline sat on the INNER eyeball region while the blue (desired) outline followed the full upper/lower lid margins. Fix: in `load_eyelid_contour(side, n_points=24, margin_mm=2.0)`:
1. **Densify 6→24 points** by arc-length resampling along the closed contour (kills the 6-segment polygon's sharp corners; a 6-gon reads "差一丢丢" off the smooth lid curve).
2. **Radial margin** outward from the contour centroid. 0.5mm was NOT enough (still read as "red"); **2.0mm** brought the opening to ~30.0×13.3mm (L) / 29.8×13.1mm (R), matching the full lid margin. Result: deleted-face count rose L 455→592, R 432→605 (~+30%).
3. **Outer-canthus non-uniform extension** (2026-08-13 v21→v22): user GUI still showed the outer corner (temple side) too short, and a third round of annotation showed the inner corner also needed extension. After uniform radial expansion, identify the outer-canthus point (max |x|) and inner-canthus point (min |x|), then push each + its ±2 neighbors in the correct direction:

   - **v21**: outer_extra_mm=1.0 only. L outer: −0.0509→−0.0519, R outer: 0.0474→0.0484. Total width: 31.0/30.8mm. User still said "外眼角少了点".
   - **v22** (2026-08-13): after **quantitative analysis of user's red/blue annotation image** (see section E below), outer_extra_mm=1.0→**4.0**, inner_extra_mm=0→**1.5**. L outer: −0.0519→−0.0549, L inner: −0.0209→−0.0194. Total width: 31.0→**35.5mm** (L) / 30.8→**35.3mm** (R). Deleted faces: L 608→660, R 618→661. Direction: outer_dir = sign(x) (away from nose), inner_dir = −sign(x) (toward nose). Falloff [0.33,0.66,1.0,0.66,0.33] smooths the transition.
- Note the margin is a per-model knob: it must cover the lid margins without eating the brow/nose. Verify by the deleted-face count and by rim span, not by eyeballing the render.

### B2. The UNIFORM radial margin was the UV-tearing root cause — use DIRECTIONAL margin (2026-08-13 v23)
The 2mm radial margin above expands the contour equally in X **and Z**. On this model the contour center z≈1.671 and the brow sits at z≥1.68, so a +2mm Z expansion pushed the contour's top edge to z≈1.684 — INTO the lower brow. `make_eye_socket`'s flood-fill then deleted ~300 brow faces (total brow-zone deletion 390), tearing the brow UV into the "纹理错乱 / 异常面" the user flagged. The user's instruction was explicit: **don't fix the torn UV after the fact — prevent the deletion at the source** ("不要先去想着修改这个错乱UV，而是从源头，让这个错乱不发生").

Fix: replace uniform radial margin with **directional (elliptical) margin** — the X and Z expansion are independent:
```
x' = x + (dx/dist)*mx      # horizontal points (canthi) expand mx
z' = z + (dz/dist)*mz      # vertical points (lids) expand mz
```
with `margin_x_mm=2.0` (width, satisfies the user's "外眼角再大") and `margin_z_mm=1.0` (height, keeps top edge at z≈1.677 < 1.68). Result: width unchanged at 35.5/35.3mm, height dropped 13.3→11.4/11.1mm, top edge z=1.6774, **brow-zone deleted faces 390→0** while the socket opening (z1.64–1.68) still carves 1523 faces normally.

- **General rule**: any "outward margin/offset" applied radially to a 2D region will also grow the region along the axis you DON'T intend. When only one dimension needs to grow (here: width for the canthi), use axis-separated margins, not a single radial scalar. This is the same class as the earlier projection-pierces-the-head lesson — a radial expansion on an XZ polygon is effectively a 2D dilation, and dilation grows both axes.
- Diagnosing "which faces did my edit delete": diff face-center multisets between input and output blend (`Counter((round(x,3),round(y,3),round(z,3)))`), bucket by z, and the deleted-face z-histogram points straight at the offending step (brow bucket = contour too tall; tiny-area bucket = sliver dissolve). This pinpoints the SOURCE in one probe instead of guessing which of several steps ate the region.

### C. Sliver-dissolve XZ radius must NOT reach the eyebrow (2026-08-13 v20, refined v23)
The `make_eye_socket` and `make_eye_cup` sliver-dissolve steps used `(fc-center).xz.length < 0.020` (20mm radius). The eye center z≈1.671 and the eyebrow is at z≈1.69–1.72. 20mm radius = 1.671±0.020 = 1.651–1.691, so the lower eyebrow (z=1.69 < 1.691) falls inside the dissolve zone. Tiny faces (<0.5mm²) there got dissolved → UV tearing → "纹理错乱" on the brow. Fix: reduce radius to **0.015 (15mm)**, which reaches z=1.671+0.015=1.686 < 1.69 (the brow). After fix: sliver dissolve count dropped L 684→348, R 579→253 (no brow faces touched). Also applied to `make_eye_cup`'s flipped-sliver dissolve (same 20→15mm).

**Refinement (2026-08-13 v23): 15mm is STILL not enough — add an explicit z ceiling.** After the directional-margin fix killed the flood-fill's brow deletion, the z-histogram still showed 93 faces deleted at z≈1.68–1.69, all tiny (area 0.18–0.50µm² = slivers). Cause: even at 15mm XZ radius, the dissolve reached z=1.671+0.015=1.686, and the brow's lower slivers sit at z≈1.68–1.686. Fix: add `and fc.calc_center_median().z < 1.678` to BOTH sliver-dissolve filters (matching the contour top edge from B2). After: brow-zone deletion 93→0. The XZ radius alone is insufficient because it's a circle — a z ceiling is the only thing that provably excludes the brow.

- **General rule**: any radius-based cleanup on the eye region should stop at 15mm from the eye center to avoid the eyebrow. The eye opening itself is ~15mm wide, so 15mm is sufficient.
- **When a radius bound sits just barely past a feature boundary (15mm→z1.686 vs brow z1.68), do NOT rely on the radius alone** — add an explicit per-axis ceiling on the same coordinate the feature is bounded by. Radius bounds are round; the feature boundary is flat.

### E. Quantitative annotation-image diagnosis (2026-08-13 — extract user's red/blue contours via PIL to size parameters)

When the user draws annotation contours on a screenshot (red = current, blue = desired), vision_analyze is not needed — the red/blue lines are pure color, and PIL can extract them directly:
```python
red_mask = (R > 150) & (G < 100) & (B < 100) & ((R-G) > 80) & ((R-B) > 80)
blue_mask = (B > 150) & (R < 120) & ((B-R) > 60)
```
Then compute the bounding box of each mask's pixel coordinates, and sample the contour profile (top/bottom edge per column) to get width, height, and per-corner extensions. This gave the 1.296× width ratio and the 60px outer-canthus / 23px inner-canthus extension that drove the v22 outer_extra_mm=4.0 / inner_extra_mm=1.5 values. The single diagnostic run replaced 3+ rounds of blind "lil bigger" parameter tweaking.

- This technique generalizes: any time the user marks a target shape on a screenshot with a distinct color, extract the pixels and measure the relative dimensions against the current output. The pixel-to-mm conversion is approximate (hand-drawn annotation, perspective), but the **ratio** between red and blue is robust — use it to scale the relevant parameter proportionally.

### F. ngon cleanup after dissolve_faces (2026-08-13 v24 — prevent visual tearing / 破面)

`bmesh.ops.dissolve_faces` on a triangular mesh merges adjacent faces into multi-sided polygons (ngons). Even a single 42-sided ngon, rendered with real-time triangulation, produces inconsistent face normals that read as dark streaks / \"破面\" on the eyelid margin. After ANY dissolve_faces on the high-poly, immediately triangulate residual ngons:
```python
bm.faces.ensure_lookup_table()
ngons = [f for f in bm.faces if len(f.verts) > 4]
if ngons:
    bmesh.ops.triangulate(bm, faces=ngons)
    bmesh.update_edit_mesh(mesh)
```
This must run after BOTH the `make_eye_socket` sliver dissolve and the `make_eye_cup` flipped-sliver dissolve. After the fix: ngon count 36→0, 破面 eliminated. The user explicitly called this \"布线乱掉了，出现了很多多变面\" — those ngons are the dissolve artifact, and triangulating them restores the all-triangle topology.

### G. Bowl transition ring for smooth rim (2026-08-13 v24→v25 — BUG FIX: direction was reversed)

The spherical bowl (8-ring cos/sin profile) meets the skin surface at ring0 with a tangent discontinuity — the skin surface is nearly flat while the bowl's first ring drops ~20% of the total depth over only ~2% of the radial span. The user flagged the rim fold as \"太锐利\". Fix: after bowl creation, push the skin vertices adjacent to ring0 inward with a cosine falloff.

**v24 BUG (2026-08-13): the cosine falloff direction was REVERSED.** The v24 formula was:
```python
push = (1.0 - math.cos(t * math.pi / 2)) * 0.001  # t=0→push=0, t=1→push=1mm — WRONG
```
This pushes vertices FARTHEST from ring0 the MOST, and ring0-adjacent vertices ZERO — the opposite of the intended smoothing. The user reported \"没变化\" after v24 because the ring0 area (where the crease is) received zero push.

**v25 CORRECTED formula (2026-08-13):**
```python
t = min(min_dist / 0.004, 1.0)  # 0 at ring0, 1 at 4mm
push = math.cos(t * math.pi / 2) * 0.002  # t=0→push=2mm, t=1→push=0
sv.co.y += push  # +Y = into head
```
This pushes ring0-adjacent vertices the MOST (2mm) and decays to zero at 4mm distance. The depth was also increased from 1mm to 2mm for visible effect. The BFS finds 1-3 skin-vertex layers outward (expanded from 2 layers). The push-in affects only the y coordinate (depth), not x/z, so the opening shape stays the same.

- **Pitfall: the `cos` vs `1-cos` confusion.** When t=0 (at ring0), `cos(0)=1` → push=max; when t=1 (far), `cos(π/2)=0` → push=0. If you write `1-cos` instead, the falloff is inverted and ring0 gets zero push — the rim stays sharp.
- The `fix_socket_normals` pass will flip any skin faces whose normals turn inward from the push — this is expected and harmless (L 36→178 flipped, R 11→97).
- If the push-in depth is too aggressive, the skin vertices will visibly \"dent\" the face around the eye. 2mm is subtle; increase only if the user still sees a sharp rim.

### H. Bowl face UV assignment — new vertices created by bm.verts.new() have UV=(0,0) (2026-08-13 v26)

The spherical bowl's inner rings and pole vertex are created by `bm.verts.new()` — these new vertices have NO UV coordinates. The default UV=(0,0) samples the texture's bottom-left corner, which may be a color completely different from the surrounding skin. On the user's 8K texture, (0,0) = RGB(0.88,0.68,0.56) (bright skin tone), while the eyelid skin is RGB(0.69,0.50,0.38) (darker). The visual mismatch reads as \"破面\" / dark streaks at the bowl-skin boundary.

**Fix (v26):** assign UV to bowl vertices radially from ring0. The bowl's inner-ring vertices are generated per-ring by radial correspondence to ring0 vertices — so each inner-ring vertex `vgrid[j][i]` should inherit the UV of `ring0[i]`. The pole vertex gets the average UV of all ring0 vertices.

```python
uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.verify()
# Collect ring0 vertex UVs
ring0_uv = {}
for v in ring0:
    for loop in v.link_loops:
        ring0_uv[v.index] = loop[uv_layer].uv.copy()
        break
avg_uv = sum(ring0_uv.values(), Vector((0,0))) / len(ring0_uv)

# After creating all faces, assign UV per loop:
v2uv = {}
for i in range(M):
    v2uv[vgrid[0][i].index] = ring0_uv[ring0[i].index]
    for j in range(1, NR):
        v2uv[vgrid[j][i].index] = ring0_uv[ring0[i].index]
v2uv[pole.index] = avg_uv

for f in new_faces:
    for loop in f.loops:
        if loop.vert.index in v2uv:
            loop[uv_layer].uv = v2uv[loop.vert.index]
```

After the fix: bowl UV=(0,0) count dropped from 512/533 (L) and 607/621 (R) to **0/533 and 0/621**. The bowl internal color now matches the eyelid skin tone, and the visual boundary artifact is eliminated.

- **General rule**: any geometry created by `bm.verts.new()` in a mesh with a UV layer will have UV=(0,0). Always assign UVs to new vertices — either by radial inheritance from existing boundary vertices (as above), or by projecting from a known camera/plane.
- The UV assignment must happen BEFORE the sliver dissolve and normal correction, because those steps need the mesh to be in a consistent state. In `make_eye_cup`, place the UV assignment immediately after face creation, before `bmesh.update_edit_mesh(mesh)`.

### I. Pole triangle fan normal reversal + mode_set(OBJECT) normal recalc pitfall (2026-08-13 v27)

**The "面朝向反了" root cause**: the user first reported "破面" (broken surface), then corrected to "面朝向反了" (faces facing wrong way — black from the outside). Diagnosis found the pole triangle fan faces (the last ring of the bowl) had normals pointing INTO the head (+Y) instead of outward (−Y). Two independent bugs:

**Bug 1: Triangle fan winding order.** The fan was created as `bm.faces.new((last[i], last[(i+1)%M], pole))` — the vertex order `last[i] → last[i+1] → pole` generates a face with clockwise winding from the outside, whose normal points inward. **Fix: reverse the order to `(last[(i+1)%M], last[i], pole)`**, which produces counter-clockwise winding from the outside → outward normal.

**Bug 2: `normal_flip()` is undone by exit from EDIT mode.** The original normal correction ran `for f in new_faces: if f.normal.y > 0: f.normal_flip()` while still in EDIT mode, then called `bmesh.update_edit_mesh(mesh)` and `bpy.ops.object.mode_set(mode='OBJECT')`. Both operations **recalculate mesh normals** from the face winding order, which overwrites the manual `normal_flip()` on the triangle fan (the fan's winding is still inward → recalc restores the inward normal). Fix: run the normal-flip pass **AFTER** `mode_set(OBJECT)`, by re-entering EDIT mode:
```python
bmesh.update_edit_mesh(mesh)
bpy.ops.object.mode_set(mode='OBJECT')
# Normals were recalculated by mode_set — re-enter EDIT to fix them
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(mesh)
flipped = 0
for f in bm.faces:
    if (f.calc_center_median() - center).xz.length < 0.014 and f.normal.y > 0:
        f.normal_flip()
        flipped += 1
bmesh.update_edit_mesh(mesh)
bpy.ops.object.mode_set(mode='OBJECT')
```
After the fix: L pole inward faces 216/427 → 0/397, R 240/327 → 0/329.

- **General rule**: `bmesh.update_edit_mesh()` and `bpy.ops.object.mode_set(mode='OBJECT')` both recalculate face normals from the winding order. Any manual `normal_flip()` or `normal_set()` done before these calls will be overwritten. If you need to manually set normals, do it AFTER the mode_set, in a fresh EDIT-mode session.
- When diagnosing "面朝向反了", first check the pole triangle fan faces (the last ring of the bowl) — these are the most likely to have wrong winding because the fan's winding convention is the opposite of the ring quads.
- The winding order for a `bm.faces.new()` that should face outward (toward −Y): `(last[i+1], last[i], pole)` — the reversed order compared to the intuitive `(last[i], last[i+1], pole)`.

### J. Bowl ring count + profile upgrade: NR 8→24, smoothstep profile (2026-08-13 v27)

The user explicitly rejected the smooth-shading approach to hide the rim crease: "我看你是用了类似平滑着色的方式，我完全不满意，而且这是个高模，我需要你增加面数去做圆润的变化".

**Two changes in v27:**

1. **Ring count NR 8→24.** The bowl now has 24 concentric rings instead of 8, giving 3× more quad faces. The user's high-poly has ~1.9M faces; adding ~1500 bowl quad faces is negligible. Result: bowl quad count L 720→2160, R 712→2136.

2. **Profile from `sin(ang)` to `smoothstep(t) = t²(3-2t)`.** The old profile used `ang = t·π/2, depth_frac = sin(ang), scale = cos(ang)`. The `sin` function has a non-zero slope at t=0 (near the rim), which means the bowl immediately drops at the rim — contributing to the "太锐利" look. The smoothstep profile has:
   - `s = t²(3-2t)` — derivative `s' = 6t(1-t)`, which is 0 at t=0 (rim) and t=1 (pole)
   - `scale = 1.0 - s` (radius contraction, starts at 1.0 at rim, ends at 0 at pole)
   - `depth_frac = s` (depth, starts at 0 at rim, ends at 1 at pole)
   
   The zero derivative at t=0 means the bowl rim is tangent-continuous with the skin surface — the bowl starts flat, then smoothly curves inward. This is the correct mathematical profile for a smooth transition. The cos/sin profile is a better fit for a hemisphere (constant curvature), not for a bowl that needs to blend into a flat surface.

```python
for j in range(1, NR):
    t = j / NR
    s = t * t * (3 - 2 * t)       # smoothstep
    scale = 1.0 - s                # radius contraction
    depth_frac = s                 # depth
    for i in range(M):
        x = center.x + (ring0[i].co.x - center.x) * scale
        z = center.z + (ring0[i].co.z - center.z) * scale
        y = ring0[i].co.y + (rim_y + max_depth - ring0[i].co.y) * depth_frac
        vgrid.append(bm.verts.new((x, y, z)))
```

- **Pitfall**: the `y` formula uses `ring0[i].co.y` as the base, not `rim_y` (the mean). This preserves the ring0's Y variation across the opening, which is important for matching the face's natural curvature. If you use `rim_y` as the base for all vertices, the bowl rim will be artificially flat.
- **When to use smoothstep vs sin/cos**: smoothstep for a bowl that needs a flat tangent at the rim (blending into a flat skin surface); sin/cos for a hemisphere that needs constant curvature.

### D. Verification script standard (hermes-verify- prefix, epsilon-based classification)
End-to-end verification scripts should be prefixed `hermes-verify-` (written to `%TEMP%`, run via Blender headless, deleted after pass). They must:
- Call the pipeline's `main()` directly (not read a cached blend) to cover the latest code.
- Use quantitative assertions (counts, distances, normal directions) — never rely on vision_analyze for geometry verification (vision reads ngon triangulation as starburst, gray models as protruded, etc.).
- Use epsilon-based normal classification: `> 0.001` / `< −0.001` with a neutral band `|ny| ≤ 0.001` for degenerate-slivability faces. The `else`-branch pattern (`normal.y >= 0`) false-counts rim slivers with `normal.y == 0.000000` as "flipped".
- Clean up the temp script after the run.

## 2026-08-07 user-driven corrections (almond opening + socket normals + ball too far out)

After the spiral above, the user gave three concrete corrections from the GUI. Each maps to a script fix now in the pipeline (`run_eye_socket.py` / `socket_ops.py` / `run_eyeball.py`).

### 1. Socket opening shape: symmetric ellipse is WRONG — use the 3DDFA eyelid contour (almond)
The ellipse (rx=13, rz=9, aspect 1.44) carved a round "ball-like" hole. User: "眼窝是个跟眼球类似的球，这根本不合理…眼窝的外边应该是跟着眼睑做一个两头较尖的椭圆形". The 3DDFA-V3 ldm68 output already has the real fissure outline (6 pts/eye: outer canthus, 2 upper-lid, inner canthus, 2 lower-lid = idx 36-41 R / 42-47 L). Back-project those 6 pts (`backproject_eyelid.py` → `eyelid_contour.json`), then delete faces by **point-in-polygon (ray-cast) against the (x,z) contour**, not the ellipse equation. Measured real shape: **26.8 × 9.7 mm, aspect 2.75** (two-pointed almond). Result opening verified 25.7×10.2 aspect 2.5 (vs ellipse 1.44). Keep the `fc.y < cy+5mm` front-cut (painted-bump lid skin sits 20mm+ in front of the cornea point). Socket interior shape is uncritical ("内部是个坑就好，反正有眼珠挡着") — the parametric cup is fine.

### 2. Socket-interior normals flipped inward after push-in — fix ALL faces in the polygon, not just the cup's new faces
`make_eye_cup`'s built-in normal fix (`normal_flipped=0`) only touched the ~304 faces IT created; it never touched the surrounding original faces that the push-in step folded inward. Quantitative check (mesh.polygons inside the eyelid polygon) showed L 325 / R 419 faces with normal.y>0 (pointing INTO the head) — the "面朝向又反了" the user saw. Fix: a separate `fix_socket_normals(obj, side)` pass AFTER both socket+cup, flipping every face whose center is inside the eyelid polygon AND `normal.y > 0` (flipped L345/R434 → 0 inward). Still LOCAL (bmesh per-face normal_flip), never global Shift+N. Note the cup's ring0 winding from `atan2` sort is non-deterministic CW/CCW, so don't rely on generation-time winding — always run the explicit inward-flip sweep.

### 3. Eyeball was drifting FORWARD across iterations — anchor to the painted-bump apex and push BACK
Across the spiral the ball center crept forward (-0.1202 → -0.1142) chasing vision's "凸出" verdicts. User GUI read: "眼球太靠外了（-y太多）". Quantitative ground truth: the original painted eye-bump's most-protruding skin (apex) is at y≈-0.1149 (L) / -0.1160 (R) — the cornea apex must sit AT/just behind that, so `ball_center_y ≈ apex_y + radius ≈ -0.1004`. From the fitted virtual-eyeball center (y=-0.1202) that means `EYE_PUSH_BACK = +0.020` (positive = into head). Setting it put front_pole at -0.1147, and the side-view vision check FINALLY passed ("略凹进/前1/3球冠/位置合理"). Lesson reaffirmed: on painted-bump eyes the ONLY trustworthy y-anchor is the original bump apex / brow-nose silhouette line, measured — not any value derived from the (already carved-away) rim.
- Ad-hoc verification caught a real desync here: the blend had been generated with a STALE PUSH_BACK while the config moved on. After any knob change, RE-RUN placement, then verify position from the SAME constants (`|actual-expected| < 3mm`). Temporary verify scripts are deleted after the run.

## 2026-08-13: v28–v29 corrections (bowl normal misdiagnosis + bevel failure + push-in removal)

### K. \"Bowl face normal toward bowl axis\" is a misdiagnosis — do NOT reverse faces based on radial dot product (v28 回退)

The v27 normal correction used `normal.y > 0` correctly. v28 tried to \"improve\" it by checking `f.normal.dot(radial) > 0` (radial = from face center toward bowl axis), interpreting \"toward bowl axis\" as \"inward → needs reversal\". This was WRONG: a concave bowl surface's faces naturally point toward the bowl axis (the bowl's interior). The correct criterion for a face that should be flipped is ONLY `normal.y > 0` (pointing into the head, i.e., away from the eyeball). The radial-dot-product check falsely flagged 2431/2756 faces as \"inward\" when they were geometrically correct for a concave surface. v29 reverted to the simple `normal.y > 0.001` check.

**Rule**: For a concave surface (bowl, socket, cavity), normals pointing toward the surface's axis of symmetry are CORRECT — they point toward the cavity interior. Do not use radial dot product as a \"wrong-facing\" check. The only reliable check is `normal.y > 0` (into the head on a −Y-facing model).

### L. Bevel on triangle mesh fails — use skin-edge subdivision for corner feathering (v29)

The user wanted \"拐角处增加面数做羽化\" (add faces at the corner for feathering). `bmesh.ops.bevel` on the ring0 edges (boundary between skin triangles and bowl quads, segments=2, offset=1.5mm) was attempted twice:

- **Placed before sliver dissolve**: 33 open edges (bevel faces eaten by subsequent dissolve).
- **Placed after sliver dissolve**: 96 open edges, 56 non-manifold edges, 266 ngons — bevel on triangle-skin mesh intrinsically produces topology defects.

**Working alternative (v29): subdivide skin edges adjacent to ring0.** For each ring0 vertex, find skin triangle faces connected to it, collect their edges (excluding ring0 edges themselves), and apply `bmesh.ops.subdivide_edges(edges=skin_edges, cuts=1)`. This increases face count around the rim (one cut → ~2× density) without breaking topology. After subdivision, immediately triangulate any ngons produced. Result: 0 open edges, 1 non-manifold edge (inherited from input), 0 ngons; >90° normal-angle vertices at ring0 reduced from 32/17 to 17/13.

```python
ring0_set = set(v.index for v in ring0)
skin_edges = set()
for v in ring0:
    for f in v.link_faces:
        if len(f.verts) == 3:  # skin tri
            for e in f.edges:
                if not (e.verts[0].index in ring0_set and e.verts[1].index in ring0_set):
                    skin_edges.add(e)
bmesh.ops.subdivide_edges(bm, edges=list(skin_edges), cuts=1, use_grid_fill=False)
# triangulate ngons produced by subdivision
ngons = [f for f in bm.faces if len(f.verts) > 4]
if ngons: bmesh.ops.triangulate(bm, faces=ngons)
```

- **Pitfall**: `bmesh.ops.bevel` on a mixed triangle/quad mesh reliably produces open edges and non-manifold edges. The fundamental issue is that bevel expects a quad-only edge loop; the skin side is all triangles. Do not use bevel on the ring0 boundary.
- **When to use subdivision vs bevel**: subdivision for triangle meshes (increases face count, smooths normals); bevel for quad meshes (inserts proper transition rings). The skin mesh is triangulated → subdivision is the correct tool.

### M. Transition-ring push-in (v25) was removed — user wants \"增加面数\" not \"移动顶点\" (v29)

The v25 transition-ring push-in (cosine-falloff push of skin vertices toward the head) moved existing vertices but did not add any new faces. The user explicitly rejected this: \"增加面数，是在拐角处增加，类似给这个边加个羽化\" — add faces, like feathering an edge. The push-in was removed entirely in v29 because it was (a) the wrong approach (vertex movement, not face addition), and (b) caused a `ReferenceError: BMesh data removed` when placed after bevel (the ring0 vertices were already invalidated). The skin-edge subdivision in section L replaced it as the correct \"add faces for feathering\" mechanism.
## 2026-08-13: v30 — absorbing an external expert review (2 of 3 recommendations landed, 1 reverted)

The user handed over an external expert's review document and instructed: "仔细研究 → 检查合理性 → 吸收 → 开始修改" (study carefully → check reasonableness → absorb → then modify). The review's core diagnosis was CORRECT: the pipeline over-relied on hardcoded absolute-coordinate judgments (`fc.y < 0`, `normal.y > 0`) and topology-breaking edits (bevel on triangles). The pass is the template for handling external advice: absorb what the topology actually supports, revert what it doesn't, record both.

### N. recalc_face_normals with reference faces (专家方案3 — LANDED, replaces manual reverse_faces/normal_flip)

The manual `reverse_faces` on `normal.y > 0` was fragile. `bmesh.ops.recalc_face_normals(bm, faces=bowl_zone + reference_faces)` propagates correct orientation from the (provably correct) skin triangles along topology into the bowl. Two critical refinements the expert doc omitted:

1. **bowl_zone MUST filter `y < 0`.** The naive `(fc - center).xz.length < 0.014` bowl-zone selection includes BACK-OF-HEAD faces (same XZ, but y>0), and recalc flipped them all — 67,551 back-of-head faces got flipped to −Y in one run. Add `and f.calc_center_median().y < 0`.
2. **Dedupe before the call.** `bowl_zone` and `ref_faces` overlap at the rim; passing the same BMFace twice raises `RuntimeError: faces: found the same (BMFace) used multiple times`. Use `ref_unique = [f for f in ref_faces if f not in bowl_zone]`.

Result: bowl face 朝+Y = 0, open edges 0, non-manifold ≤1, back-of-head mis-flip delta = 0.

### O. Local-depth back-of-head lock (专家方案1 — LANDED, replaces global fc.y < 0)

Global `fc.y < 0` is fragile against origin offset and back-of-head concavities crossing y=0. Replace with a depth test relative to the eye center: `if abs(fc.y - center.y) > 0.05: continue` (only faces within 50mm of the eye center). On this model the skull back sits y≈+0.09 vs eye center cy≈−0.106, a 196mm gap — far outside the 50mm band, so back-of-head faces are excluded by construction, independent of model origin. Verified: back-of-head mis-flip delta input→output = 0.

### P. Extrude Buffer Ring (专家方案2 — REVERTED, fails on triangle mesh)

The expert proposed extruding ring0 inward ~0.5mm into a "buffer ring" (ring1), building the bowl from ring1, leaving a quad buffer strip between skin and bowl to smooth the seam. It produced open + non-manifold edges every time, regardless of construction method:
- Manual quad winding `(ring0[i], ring1[i], ring1[i2], ring0[i2])`: 19 open edges + 75 non-manifold.
- `bmesh.ops.bridge_loops`: 49 open edges + 52 non-manifold.
- `smooth_vert` on ring0/ring1 (the expert's smoothing suggestion): invalidated ring0 refs (`ReferenceError: BMesh data of type BMVert has been removed`) and, applied to shared skin verts, tore the skin.

Root cause: the buffer quads share the ring0 boundary edge with the skin triangles, and the new quads' winding disagrees with the existing skin tris' winding, so bmesh creates NEW edges instead of sharing — leaving the original boundary edges open. Same class as the bevel failure (section L): any face-injection onto a triangle-skin boundary is unreliable. Reverted; skin-edge subdivision (section L) remains the only topology-safe "add faces at the corner" method on this mesh.

**General rule from the v30 pass**: when handed external expert advice, the parts that are pure math/normal-propagation (recalc_face_normals, relative-depth bounds) usually land; the parts that inject NEW topology onto a triangle boundary (buffer ring, bevel) usually fail on a triangulated high-poly. Check the mesh's face type before trusting a topology-injection recipe.

## Machine-resource etiquette (user-reported 2026-08-06: whole PC stutters while agent runs heavy Blender)
The user works interactively on the same machine (Blender GUI open, HDD-based project disk). Each headless Blender load/render of the ~1.6GB high-poly blend causes a seconds-long CPU+disk spike that stutters the user's mouse. Rules:
- Run background Blender at reduced priority: Windows `start /BELOWNORMAL /B blender.exe ...` or via Python `subprocess.Popen(...)` then `psutil.Process(pid).nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)`.
- ONE heavy Blender task at a time — never parallel headless instances.
- Quick verification shots: use `BLENDER_WORKBENCH` (no shader compile spike), not EEVEE/Cycles, unless the check specifically needs materials/lighting.
- When the user reports "卡顿" (stutter), first check for leftover processes: `tasklist /FI "IMAGENAME eq blender.exe"` + psutil cmdline inspection — distinguish the user's own GUI session (don't touch) from agent-spawned leftovers (kill).

## Doc placement for research conclusions (user preference 2026-08-06, refined 08-06 part 2)
Research verdicts (e.g. the 3DDFA-V3 assessment) fold into the relevant pipeline step's README as an appendix, with a pointer to the full design doc. BUT when the user asks to SEE the detailed research ("把详细调研结果单独拉出来做成md，我需要仔细看看"), write a full standalone 调研报告 under 方案md记录 (specs, dependencies, cost/benefit table, verdict, fallback trigger) — e.g. `01A眼窝与眼球/3DDFA-V3调研报告.md`. Default = fold into README; explicit request = standalone report.

## Delivery ↔ 方案md记录 sync rule (user requirement 2026-08-06, keep current)
The user treats `方案md记录/` as the COMPLETE thinking log — every correct AND wrong attempt, analysis, and decision — and expects it updated promptly alongside the delivery folder. After any delivery-folder change:
- Mirror it in `方案md记录/v3_QuadRemesher/<same-step-name>/` — problem analysis / design docs / research verdicts go there, NOT in the delivery folder (delivery keeps only README + scripts + binary products).
- Keep the two folder structures aligned by step name (a `01A眼窝与眼球` in delivery ↔ `01A眼窝与眼球` in 方案md记录).
- Clean up stale/renamed/empty doc folders (the `08眼窝与眼球集成` → `01A眼窝与眼球` move is the example: rename BOTH sides, delete the empty leftover).
- Commit + push BOTH sides together (git tracks renames; sed the path references inside moved docs too — check the file-header comment lines of .py configs, not just path literals).

## Step-folder naming for Explorer sort order (user correction 2026-08-06)
Windows Explorer sorts `01_1眼窝制作` ABOVE `01高模修复与黏连检测` (underscore `_` U+005F < CJK), which the user found jarring ("看着不舒服"). Inserted sub-steps between `NN` and `NN+1` should use an ASCII continuation token that sorts after the parent's CJK text:
- GOOD: `01A眼窝与眼球` — `A` (U+0041) < CJK, and the folder is one merged unit.
- BAD: `01_1…` / `01_2…` — sorts above `01高模修复`; also two folders for one logical step.
- Also: merge tightly-coupled sub-steps into ONE folder (eye socket + eyeball = `01A眼窝与眼球`), minimize new folders. When renaming/merging, sweep every `os.path.join(DELIVERY, "<old>", ...)` in the scripts AND the docstring header lines (a stale `01_1眼窝制作` survived in a `"""..."""` comment and failed a path-assertion check).
