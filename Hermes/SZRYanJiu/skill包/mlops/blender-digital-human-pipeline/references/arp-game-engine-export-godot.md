# ARP Official Game-Engine Export (auto_rig_ge.py) — Godot Path (2026-08-27)

User tested ARP's AI rig in the GUI and reported: "绑定后是个控制器，导出后骨骼很乱，
跟mixamo完全不一样". Source inspection of `auto_rig_ge.py` shows these are all
expected consequences of NOT using ARP's own export panel — not ARP defects:

## Key findings
1. **ARP's game-engine exporter natively supports Godot.**
   `Scene.arp_engine_type` enum: `UNITY / UNREAL / GODOT / OTHERS`.
   Godot-specific options: `arp_rename_for_godot` (default True) and
   `arp_godot_root_axes` (root bone axes → Z forward, Y up for Godot root motion).
2. **Controllers are baked away on export.** The exporter builds a baked
   deformation armature (`rig_humanoid` for humanoid, `rig_mped` for universal)
   via `_bake_all` + `_bake_pose`, parents the meshes to it, and exports that —
   controllers never reach the file. Exporting via Blender's native FBX/GLB
   instead (what the user did) is why controllers and helper bones appeared.
3. **`arp_export_rig_type`**: `HUMANOID` ("简单骨骼层次结构,以确保动画重定向") or
   `UNIVERSAL`. Use HUMANOID for the digital human.
4. **Godot rename map (from `rename_for_godot()`)** — NOT Mixamo naming:
   thigh_stretch→UpperLeg, leg_stretch→LowerLeg, foot→Foot, toes_01→Toes,
   shoulder→Shoulder, arm_stretch→UpperArm, arm_twist→UpperArm_twist_01, etc.,
   with `.l/.r` → Left/Right prefix. Bones with bend/custom markers or
   `arp_ge_helper` key are skipped.
5. **Mixamo alignment = one extra rename step** after ARP export: the Godot
   humanoid names map 1:1 onto Mixamo names (UpperArm→LeftArm, LowerLeg→LeftLeg…),
   so "跟mixamo完全不一样" is a naming-layer difference, fixable by script.

## Recommended ARP→Godot flow
1. ARP Smart build (markers → controllers+weights).
2. ARP export panel path (scripted: engine=GODOT, rig_type=HUMANOID,
   rename_for_godot=True, godot_root_axes=True) → clean deformation-only rig.
3. Post-rename Godot names → `mixamorig:` Mixamo names for animation retargeting
   against the hand-written version (which already uses Mixamo names/axes).

## Status note
The scripted invocation of the ARP exporter itself was NOT exercised yet in the
2026-08-27 session (findings above are source-verified, runtime-pending). The
`go_detect` marker→bone alignment gap (bones up to 33cm off markers on T-pose
model) is the open blocker before export matters — see
`references/arp-smart-headless-guess-markers.md`.
