# Manual Rig from Mesh Geometry — Mixamo Standard

When the user requires Mixamo-standard bones and the model size differs from ARP's template (~0.976m vs 1.8m), abandon ARP entirely. Use manual rig creation from mesh vertex band analysis.

## Mixamo 15-Bone Hierarchy

```
Hips (root)
├── Spine
│   └── Chest
│       ├── Neck
│       │   └── Head
│       ├── LeftShoulder
│       │   ├── LeftUpperArm
│       │   │   └── LeftLowerArm
│       │   │       └── LeftHand
│       └── RightShoulder
│           ├── RightUpperArm
│           │   └── RightLowerArm
│           │       └── RightHand
├── LeftUpLeg
│   ├── LeftLeg
│   │   └── LeftFoot
└── RightUpLeg
    ├── RightLeg
    │   └── RightFoot
```

## Joint Position Computation

Verified on 178K-face Quad Remesher output (0.976m tall, arms along X, face -Y):

1. Compute mesh bbox: `min/max_x/y/z`
2. `H = max_z - min_z`, `mid_x = (min_x + max_x) / 2`
3. **Root/Hips**: `Z = min_z + H*0.45` — crotch bifurcation point (X-density shows legs separate at 45%)
4. **Spine**: `Z = min_z + H*0.55`
5. **Chest**: `Z = min_z + H*0.68`
6. **Neck**: `Z = min_z + H*0.83`
7. **Head**: `Z = min_z + H*0.90`
8. **HeadTop**: `Z = min_z + H*0.97`
9. **Shoulder** (CRITICAL): NOT at arm tip. Use X-density peak at shoulder height:
   - Iterate X from 0.05 to 0.15 in 0.005 steps
   - Count vertices within ±0.01m at Z=shoulder_height
   - Pick X with highest count (typically ~0.10)
10. **Elbow**: `(shoulder_x + max_x*0.85) / 2` at shoulder height
11. **Hand/Wrist** (CRITICAL): NOT at max_x*0.9. Use density valley in [0.35, 0.48] at shoulder height — pick X with LOWEST count (>50). Hand bone tail extends to `max_x` (fingertips)
12. **Hips**: `Z = min_z + H*0.45`, X offset from center by density analysis
13. **Knee**: `Z = min_z + H*0.22`
14. **Foot**: `Z = min_z + H*0.05`

## Verification Checklist

- [ ] All bone heads inside mesh bbox
- [ ] Shoulder head at body side (X≈0.10), NOT arm tip
- [ ] Hand tail reaches mesh max_x
- [ ] Root Z matches crotch bifurcation
- [ ] `parent_set(type='ARMATURE_AUTO')` produces >0 weighted vertices per VG
- [ ] `arm.data.pose_position = 'REST'` before saving

## Pitfalls

- **Do NOT hardcode X=0.08 for shoulder**: Exact position varies per model. Hardcoding produces 长颈鹿骨骼 (giraffe skeleton).
- **Do NOT scale ARP rig for non-standard sizes**: ARP template proportions are fixed. Uniform scale compresses legs and stretches spine.
- **Do NOT use max_x*0.9 for hand**: This places the wrist too far from the actual arm narrowing point.

## 3 Refinement Iterations Discovered

1. Pelvis: 42% → 45% (crotch bifurcation from X-density)
2. Shoulder: arm-tip (X=0.48) → body-side (X=0.10) via density peak
3. Hand: max_x*0.9 (X=0.435) → density valley (X=0.445) with tail to max_x