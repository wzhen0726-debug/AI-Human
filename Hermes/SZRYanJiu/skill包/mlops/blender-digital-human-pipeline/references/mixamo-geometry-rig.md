# Mixamo-Standard Rig from Mesh Geometry (2026-07-17)

## Motivation
ARP's Smart auto-rigging template is designed for ~1.95m humans. Models at different scales (0.976m, or fat/female body types) produce fundamentally wrong bone proportions — uniform scaling can't fix template-specific bone lengths. The user's feedback: "成了长颈鹿骨骼" (giraffe skeleton — all limb bones compressed into lower body, spine/neck stretched to fill upper body).

## Solution: Geometry-Based Joint Detection
`rig_mixamo.py` uses **X-axis density analysis** to find joints, with zero hardcoded percentages. Works for any body type (slim, fat, male, female) because it reads the mesh's actual vertex distribution.

### Algorithm

**1. X-Width Profile**: Scan Z from 10%→85% height, compute X-spread (max_x - min_x) at each Z band.

**2. Arm Separation Z**: Z where max(X) peaks in the upper body (Z > 65%×H). This correctly finds the fully-extended arm height (Z≈0.78 for this model), NOT where spread first exceeds a threshold. Using threshold (0.5×W) can trigger too early at Z=0.74 where arms are just starting to spread.

**3. Hip Z**: Widest X-spread in Z range [0.25, 0.55]×H. This finds the hip joint regardless of body type — works for slim (narrow hips) and fat (wide hips).

**4. Shoulder X**: Density peak in Z band at arm_sep_z, within X range [0.02, max_x×0.35]. The density peak correctly identifies the shoulder joint even for muscular vs slim builds.

**5. Elbow X**: Midpoint from shoulder to max_x×0.85.

**6. Wrist X**: Density valley in Z band at arm_sep_z, within X range [max_x×0.7, max_x×0.95]. The valley correctly finds the wrist constriction even for thick/fat arms.

**7. Hip joint X**: Density peak at hip Z in X range [0.02, max_x×0.30].

**8. Knee Z**: Fixed at 22%×H (consistent across body types).

**9. Foot/Toe Z**: Fixed at 5% and 1%×H.

### Mixamo Standard Bone Names
```
Hips → Spine → Spine1 → Spine2 → Neck → Head
├── RightShoulder → RightArm → RightForeArm → RightHand
├── LeftShoulder  → LeftArm  → LeftForeArm  → LeftHand
├── RightUpLeg → RightLeg → RightFoot → RightToe
└── LeftUpLeg  → LeftLeg  → LeftFoot  → LeftToe
```
20 bones total.

### Pitfalls Encountered

**Bug 1: Foot spread misdetected as hip**. Initial scan from Z=5% found ankle spread > threshold → hips placed at ankle level. **Fix**: Scan from Z=10% minimum, use width-profile widest-point instead of threshold change-point.

**Bug 2: Hand bones extending outside mesh**. Shoulder at body-side (X≈0.09), elbow midpoint, wrist at density valley — but hand tail must extend to mesh boundary (max_x), not arbitrarily 0.02m past wrist.

**Bug 3: All arm joints at same Z — must verify mesh arm is at that Z**. Arm joints placed at arm_sep_z (the Z where X-width first exceeds 50% of total width). Must verify this Z has enough arm vertices on both sides.

**Bug 4: Arm separation Z detection via threshold (0.5×W) triggers too early (2026-07-20)**. At Z=0.742, X-width barely exceeds 0.5×W, but the arm doesn't fully extend until Z=0.781 (max_X=0.483). Using threshold detection places arm joints at Z=0.742 — 0.04m too low. **Fix**: Scan for the Z where **max(X)** reaches its peak in the upper body (Z > 65%×H), not where X-width first exceeds a threshold. This correctly finds the fully-extended arm height.

**Bug 5: Arm bones reversed — shoulder head must be at body side (2026-07-20)**. The `band_extreme_x()` function finds the widest X (arm tip) and assigns it as the shoulder joint. This makes shoulder head at X=0.484 (arm tip) → tail at X=0.104 (body side) — the bone is reversed (points inward instead of outward). **Fix**: Shoulder joint uses `density_peak_x()` (body-side, X≈0.10), elbow is midpoint, wrist uses `density_valley_x()` (arm constriction), hand tail extends to max_x (fingertip). Verify bone direction: head must be proximal (toward body center), tail must be distal (toward extremity).

**Bug 6: Wrist X via density_valley outside mesh bounds (2026-07-20)**. `density_valley_x()` searches X∈[max_x×0.7, max_x×0.95] but at the wrong Z, max_x at that Z may be smaller than expected. On the test model, at Z=0.722 the max X was only 0.108 (arm not present at that Z). **Fix**: Compute all arm joints at the same Z (arm_sep_z) where the arm is fully extended, not at progressively lower Z values. The arm in T-pose is roughly horizontal, so shoulder/elbow/wrist are all at the same Z height.

### Verification Checklist
Before handing off, verify:
1. `Hips` Z matches mesh hip region (verify via vertex band center)
2. `RightShoulder` X is at density peak (not arbitrary hardcoded 0.08)
3. `RightForeArm` X is at density valley (wrist constriction)
4. `RightHand` tail extends to max_x*0.98 (fingertip, not hanging mid-air)
5. All 20 bones have vertex groups with actual weights (>0)
6. Export GLB: `export_apply=False`, delete non-deform bones, verify re-import has 1 armature + 1 mesh + 0 empties
7. Re-import GLB and verify: no empties, mesh has vertex groups with weights, parent=armature
8. **Check bone positions against mesh bbox**: root bone within mesh, head bone at top, hand bones within X bounds

### Self-Check Routine (must run before handoff)
```python
# After rig, verify:
arm = [o for o in bpy.data.objects if o.type=='ARMATURE'][0]
mesh = [o for o in bpy.data.objects if o.type=='MESH'][0]
xs = [v.co.x for v in mesh.data.vertices]
zs = [v.co.z for v in mesh.data.vertices]
min_x,max_x = min(xs),max(xs); min_z,max_z = min(zs),max(zs)
# Check all bone heads are within mesh bbox
for b in arm.data.bones:
    h = arm.matrix_world @ b.head_local
    assert min_x-0.01 <= h.x <= max_x+0.01, f"{b.name} X={h.x:.3f} outside [{min_x:.3f},{max_x:.3f}]"
    assert min_z-0.01 <= h.z <= max_z+0.01, f"{b.name} Z={h.z:.3f} outside [{min_z:.3f},{max_z:.3f}]"
# Check vertex groups have weights
for vg in mesh.vertex_groups:
    w = sum(1 for v in mesh.data.vertices if any(g.group==vg.index and g.weight>0 for g in v.groups))
    assert w > 0, f"VG {vg.name} has 0 weighted vertices"
```
