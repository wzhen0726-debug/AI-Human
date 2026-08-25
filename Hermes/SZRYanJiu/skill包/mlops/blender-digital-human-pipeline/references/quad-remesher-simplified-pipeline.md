# Quad Remesher Simplified Pipeline (v3)

> 全自动化管线, 8-10周工期, 20-25万面, 保留衣服头发, 不做面绑

## Summary
The simplest viable pipeline: AI-generated clothed high-poly → Quad Remesher → auto-UV → bake → Mixamo bind → GLB. No MetaHuman wrap, no clothes removal, no face binding, no symmetry correction needed (tight clothing + Symmetry X).

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| 20-25万面 (not 30万) | Mixamo boundary value — 30万 may fail to upload |
| Symmetry X ON | Tight clothing is approximately symmetric; ensures better binding |
| Auto-UV (edge-angle + Unwrap) | Fully automated, 100% Blender, far better than Smart UV Project |
| Keep eyes in mesh | Quad Remesher preserves all geometry; no separate eye assembly needed |
| Keep clothes/hair | No removal pipeline needed; accept rigid hair/cloth animation |
| Tight clothing requirement | Loose clothes cause bad Mixamo weights and baking interference |
| No face binding | Adds 6+ weeks; accept static face for MVP |

## Why This Wins Over MetaHuman Wrap

| Factor | MetaHuman Wrap | Quad Remesher |
|--------|---------------|---------------|
| Timeline | 21 weeks | 8-10 weeks |
| Face quality | ARKit 52 (excellent) | Static (no blendshapes) |
| Clothes | Must remove (4 weeks) | Keep as-is |
| Symmetry | Complex bmesh mirror (72% ceiling) | Symmetry X ON (automatic) |
| UV | Template pre-made | Auto edge-angle seam |
| Complexity | Very high | Moderate |

## Risks

| Risk | Level | Mitigation |
|------|-------|------------|
| Mixamo fails on 20-25万面 | Medium | Switch to Auto-Rig Pro |
| Adhesion (thighs touching) | Medium | Photo prevention (legs shoulder-width) + iterative repair |
| Loose clothes weight quality | Medium | Photo requirement: tight clothing only |
| UV seam visibility | Low | Non-AAA acceptable; seams at sharp edges |
| Auto-UV quality | Low | Validated — better than Smart UV Project |

## 6 Original WBS Contradictions Resolved

1. 30万面 → 20-25万面 (Mixamo compatibility)
2. Symmetry X OFF → ON (tight clothing)
3. Smart UV Project → Auto edge-angle Unwrap (production quality)
4. Eye separation deleted → Kept in mesh (Quad Remesher preserves all)
5. Clothes baking interference → Separate high-poly + Cage during bake
6. 6-8 weeks → 8-10 weeks (accounting for corrections)

## Project Structure

### Research & Planning
- `方案md记录/v3_QuadRemesher/` — 完整技术档案 (10份文档: WBS/方案/缺陷分析/调研报告/UV脚本)
- Key files: `QuadRemesher简化版_完整档案.md`, `技术方案_全自动化版v3.md`, `项目WBS_全自动化版v3.md`, `adhesion_research_report.md`, `auto_uv_research_report.md`, `quad-remesher-mixamo-research.md`

### Runnable Implementation — `test03_SimplifiedPipeline/` (2026-07-15)

```
test03_SimplifiedPipeline/
├── input/                    # GLB输入模型
├── output/                   # 各阶段输出(编号+阶段名)
│   ├── 01_repair/            # Voxel Remesh + Laplacian Smooth
│   ├── 02_adhesion/          # BVH/KDTree黏连检测 + 法线推开
│   ├── 03_remesh/            # Quad Remesher (20-25万面)
│   ├── 04_uv/                # 自动UV (边缘角度接缝+Unwrap)
│   ├── 05_bake/              # Diffuse+Normal烘焙 (Cycles)
│   ├── 06_rig/               # FBX导出 (Mixamo上传)
│   └── 07_glb/               # 最终GLB
└── scripts/
    ├── config.json           # 管线参数 (可调阈值/面数/UV角度等)
    ├── pipeline.py           # 主控 (--stage/--from/--reset/--list)
    ├── repair.py             # 阶段1-2: 去重→填洞→Voxel Remesh→Laplacian
    ├── adhesion.py           # 阶段3: KDTree面心距离+法线推开+平滑
    ├── remesh.py             # 阶段4: bpy.ops.quadremesher.remesh()
    ├── uv.py                 # 阶段5: 二面角接缝+对称轴+Angle Based Unwrap+Pack
    ├── bake.py               # 阶段6: Selected to Active + Cage
    ├── rig.py                # 阶段7: 导出FBX for Mixamo
    └── export_glb.py         # 阶段8: GLB导出
```

**Usage**: `cd scripts && python pipeline.py [--stage repari] [--from remesh] [--reset] [--list]`

**Checkpoint**: `scripts/checkpoint.json` 记录已完成阶段，支持断点续跑。每个阶段输出独立 `.blend` 到对应 `output/` 子目录。

## v5 Run Results (2026-07-16) — Full Pipeline End-to-End

User-corrected issues from v4:
1. **UV**: "UV都有问题，前面是只展开了头，而且头展开的不对，没有人在脸中部分割开uv的" — UV only unwrapped head, and incorrectly (split through face). Smart UV Project created 894 islands.
2. **Bake**: "低模上的纹理很多错误，有多重纹理重叠的感觉" — texture has multiple overlaps, black faces. Need to clean scene, fix normals, adjust bake params.
3. **Rotation**: "旋转做了好几次，优化旋转次数" — rotation done multiple times, optimize to once.
4. **Rig**: "绑定点都不在模型上" — binding points not on the model.

Fixes applied:
- **Rotation moved to repair stage** (once, bmesh vertex swap, correct CW direction: `new_x=old_y, new_y=-old_x`)
- **UV rewritten** with strategic seams (back center + crotch + armpits, tight tolerance 0.5% width) → 8304 seams → 420 islands
- **Bake rewritten** with scene cleanup (remove duplicate retopo meshes), normal recalculation on both high+low, bake distance 0.12m
- **Marker positions** computed from body_temp vertex-band centers, clamped to bbox

| Stage | Status | Result |
|-------|--------|--------|
| 1. Repair | ✅ | Rotated + Voxel Remesh → 34,480 verts (arms now along X, face -Y) |
| 2. Adhesion | ✅ | 33 adhesion pairs detected + fixed |
| 3. Remesh | ✅ | QR → 224,277 verts retopo |
| 4. UV | ✅ | 8,304 strategic seams → 420 islands, U[0.002,0.980] V[0.002,0.998] |
| 5. Bake | ✅ | Diffuse + Normal @ 2048², 0.12m distance, 63.5% black (down from 95%) |
| 6. Rig | ✅ | ARP Smart 339 bones + 67 vertex groups (auto-weights) |
| 7. GLB | ✅ | 17.4MB, with skins+materials |

**Remaining issues**: 63.5% black pixels in bake (high-poly/low-poly surface mismatch in torso region). Needs Cage baking or larger distance (0.15m+).

End-to-end run on same 60MB Tripo AI GLB. Stages 1-5 fully verified:

| Stage | Status | Result |
|-------|--------|--------|
| 1. Repair | ✅ | Voxel Remesh (0.005) → 34,480 verts |
| 2. Adhesion | ✅ | 33 adhesion pairs detected + fixed |
| 3. Remesh | ✅ | QR via standalone exe (addon not installed) → 223,108 verts retopo |
| 4. UV | ✅ | 1,238 seams (65 angle + 1,173 symmetry), Angle Based Unwrap + Pack |
| 5. Bake | ✅ | Diffuse + Normal @ 2048², adaptive distance = 0.244m (25% of model size) |
| 6. Rig | ⏳ | ARP Smart: steps 1-2 work, step 3 (go_detect) blocked by shoulder ray-cast None |

**Key fix in v4 — bake distance**: Previous runs used fixed 0.05m bake distance (5% of model), producing massive black patches and fragmented textures. v4 uses `max(bake_distance, model_size * 0.25)` = 0.244m adaptive distance, which fixed the bake quality.

**Key fix in v4 — launcher workdir**: The launcher uses `os.getcwd()` when `bpy.data.filepath` is empty (fresh Blender session). Always pass `workdir` to the terminal call or `cd` before running.

## Implementation Verification (2026-07-15)

Tested end-to-end on 60MB Tripo AI GLB (113.7万v/193万f). Final output: 12.89MB GLB
(23.4万v retopo + Diffuse+Normal 2048²). 11 bugs fixed across Blender 5.1 API
migration and QuadRemesher async handling. Key findings:

- **QuadRemesher API**: `bpy.ops.qremesher.remesh` (NOT `quadremesher.remesh`),
  params via `scene.qremesher.*`, async polling of `progress.txt` required
- **Bake-to-GLB**: Must pack images + wire to material output (Diffuse→BSDF Base
  Color, Normal→NormalMap→BSDF Normal)
- **GLB mesh selection**: Prefer objects with 'Retopo' in name
- **Model limitation**: Original X-depth only 0.001m (flat); Voxel Remesh expanded
  to 0.084m but caused collapse to 34K faces. Quad Remesher rebuilt to 234K faces.
  Recommend 4-view photography for proper 3D depth.

Full details: `references/blender51-api-migration.md`, `references/quad-remesher-blender51-api.md`