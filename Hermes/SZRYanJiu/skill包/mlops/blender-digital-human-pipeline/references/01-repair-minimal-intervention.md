# 01 Repair Minimal Intervention Principle (2026-08-03)

## The Critical Lesson

This session the agent attempted **five progressively more aggressive automated fixes** on the chest area:

1. Normal flipping (49K faces based on face-center-to-model-center dot product)
2. Tiny face removal via `bmesh.ops.holes_fill` (crashed/hung)
3. Tiny face removal via `bmesh.ops.remove_doubles` (merged legit detail)
4. Sculpt smooth (Laplacian, 5 iters, strength=0.3)
5. Bump pushing (ring-based reference, 100% push to reference)

**Result**: Every fix either did nothing visible or **damaged other regions**:
- Neck root (z=1.38): 16.7mm deviation from original — normal flipping destroyed the natural concave anatomy (clavicle fossa normals are legitimately inward-facing)
- Belly (z=1.00): 44mm deviation — cumulative damage from multiple operations

**The user's response**: "不知道你改动了啥，胸口错误没变化，肚子上还出现了新错误"

## The Correct Approach

**When the user says "I can fix this with sculpt brush in Blender GUI"** — STOP. Do not attempt automated fixes. The user's manual fix is the correct path. The agent's job is:

1. **Rotation correction** (stand up + face -Y) — always needed
2. **Remove doubles** (adaptive threshold ~0.0001 for 193K faces) — QR prerequisite
3. **Non-manifold edge fix** — QR prerequisite
4. **Nothing else** — leave geometry details to the user

Verification against the raw model (after this minimal repair) showed **0.2mm max deviation** — only remove_doubles welding displacement, no geometry damage.

## Root Causes of Failed Fixes

### Normal flipping (most destructive)
- **Logic**: `face_normal.dot(face_center - model_center) < 0 → flip`
- **Problem**: Concave anatomical regions (neck root, clavicle fossa, armpit, crotch) have naturally inward-facing normals. The dot product test is WRONG for these areas.
- **Consequence**: 16.7mm visual deformation in neck root area
- **Fix**: Remove this logic entirely. Do not attempt automated normal correction.

### Sculpt smooth / bump pushing
- **Logic**: Laplacian smooth restricted to chest z-range, then push bump vertices toward ring-averaged reference
- **Problem**: Reference surface includes the bump itself (self-contamination), and the smooth propagates errors to surrounding areas
- **Consequence**: Cumulative vertex displacement spread to belly area (44mm)
- **Fix**: Let the user handle local bumps with Blender's sculpt brush in GUI mode

### Verification trap
- **Problem**: Comparing fixed model vs raw model without applying the SAME rotation first gives false 50mm+ deviations (coordinate mismatch)
- **Fix**: Always rotate the raw model (`rotate_to_standard()` + `transform_apply()`) before KDTree comparison
- **Also**: When loading the repair blend, select the mesh with MAX vertex count, not `[0]` — the file may contain a default Cube (8 verts) from factory settings

## When to Use This

Trigger: User reports a localized surface issue (bump, dent, hole) on a high-poly AI model and says "I can fix this in Blender GUI with sculpt brush."

Response:
1. Do NOT attempt automated fixes
2. Ensure the 01 repair pipeline only does: rotation + welding + non-manifold fix
3. Deliver the model with the original geometry intact
4. Let the user apply their sculpt brush fix in GUI

## Related References

- `repair-pipeline-v7.md` — the full pipeline description
- `sculpt-smooth-bmesh-regional.md` — previous attempt at regional sculpt smooth (may contain useful algorithms but the lesson is: DON'T use them without user confirmation)
- `chest-region-three-step-fix.md` — previous chest fix attempt