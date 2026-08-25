---
name: blender-body-wrap
description: "Use when wrapping MetaHuman body onto AI high-poly. ❌ ABANDONED 2026-07-29 — 9 methods failed (clothing nesting + inverted normals). Head wrap v3.4 also unusable (numeric metrics OK but visual quality poor: ear/lip/eye distortion). Kept as failure archive + T-pose prep reference. v4 three-stage route: Stage 1 MVP brute-force (QR+Smart UV+Bake, verified working), Stage 2 3D segmentation+ARAP, Stage 3 SMPL-X."
version: 1.0.0
author: Hermes Agent
tags: [blender, wrap, metahuman, body, shrinkwrap, uv, clothes, triplo]
platforms: [windows]
---

# Blender Body Wrap Pipeline

Wrap MetaHuman Body low-poly (~56K vertices, **14 connected components**) onto AI-generated high-poly (Tripo ~193万面, 含衣服) to inherit MetaHuman's standard UV.

## Core Principle

**WRAP 是为了 UV 传递，不是完美贴合。** MetaHuman 自带标准 UV，QR 后的 Tripo UV 碎片化（1145-2000岛）。Wrap 让 MetaHuman 拓扑贴合 Tripo 形状，继承 UV。衣服区域无所谓——QR 后一样乱。

## Pipeline

### 1. MetaHuman T-Pose 准备
- 来源：Mixamo T-Pose FBX（用户已在 Mixamo 完成 A-pose→T-pose 动画）
- 导入后：armature scale×100 → frame_set(2) → modifier_apply("Armature") → 删除骨骼
- 顶点坐标变换：`x=x*0.01, y=-z*0.01, z=y*0.01`（FBX cm→Blender m + 坐标系转换）
- 验证：X span≈1.9m, Z span≈1.8m, 脸朝 -Y

### 2. 骨骼 Landmark 提取
从 Mixamo pose.bones 提取关节位置（**用 tail 而非 head**）：

```python
mapping = [
    ('shoulder_L','mixamorig:LeftShoulder', 'tail'),  # 肩关节
    ('elbow_L',   'mixamorig:LeftArm',     'tail'),    # 肘关节
    ('wrist_L',   'mixamorig:LeftForeArm', 'tail'),    # 腕关节
    ('head_top',  'mixamorig:Head',        'head'),
    ('chest',     'mixamorig:Spine2',      'head'),
    ('pelvis',    'mixamorig:Hips',        'head'),
]
pos = arm.matrix_world @ (pb.tail if end=='tail' else pb.head)
```

### 3. 纯缩放+平移对齐（唯一成功方法）

```python
sx = tripo_xspan / mh_xspan  # 通常 0.94
sy = tripo_yspan / mh_yspan  # 通常 0.89
sz = tripo_zspan / mh_zspan  # 通常 1.00
for v in obj.data.vertices:
    v.co.x = (v.co.x - mh_center.x) * sx + tripo_center.x
    v.co.y = (v.co.y - mh_center.y) * sy + tripo_center.y
    v.co.z = (v.co.z - mh_center.z) * sz + tripo_center.z
```

bbox 完全匹配，UV 完全保留，无扭曲。

## Failed Methods (Do NOT Use)

| 方法 | 结果 | 根因 |
|------|------|------|
| Shrinkwrap NEAREST | X span 压扁 54% | 14分量+衣服内表面→塌缩 |
| Shrinkwrap PROJECT | 保持bbox但不投影 | 7.5%顶点真正投影 |
| Surface Deform | 0.3%投影 | falloff无效 |
| RBF thin_plate_spline | 整体扭曲 | 15控制点太稀疏 |
| 仿射变换 | 混入旋转 | 最小二乘固有特性 |
| 分组件Shrinkwrap | 每个分量仍塌缩 | 衣服内表面未解决 |

## Critical Pitfalls

### 14连通分量
MetaHuman Body 有 14 个独立分量（躯干、左右手臂各3段、脚、脚趾等）。Shrinkwrap 独立投影每个分量，手臂找到躯干衣服表面→塌缩。

### 衣服内表面
Tripo 含衣服，内表面距人体 5-20mm。Shrinkwrap 找到衣服内表面而非人体→MetaHuman 被吸到夹层。

### FBX rotation_euler 污染
FBX 导入残留 `rotation_euler=(1.5708,0,0)`。改 `v.co` 不影响 `matrix_world`。**必须直接改 v.co 做坐标系转换**。

### UV 保留
bmesh 只改 `vert.co` 不动 UV（差异 0.0）。Shrinkwrap/Surface Deform 会破坏 UV。纯缩放+平移保持 UV。

## Debugging Checklist

1. 连通分量数：bmesh 遍历，14个=正常
2. 法线：`sum(1 for p in mesh.polygons if p.normal.z < 0)`，>40%=AI特征
3. 投影质量：BVHTree find_nearest，<5mm=成功，>100mm=失败
4. UV 差异：`foreach_get("vector")`，差异=0.0=保留
5. bbox：X span≈1.8m, Z span≈1.8m

## Final Verdict (2026-07-29): ❌ Body Wrap ABANDONED

User has **definitively abandoned** the body wrap approach after 9 failed attempts. Root causes are structural and unfixable with automatic methods:
1. **Clothing nesting** — Tripo has outer clothes + inner body; all nearest-point algorithms find clothes, not body
2. **53.1% inverted normals** — AI-generated mesh defect; normal repair doesn't fix nesting
3. **14 connected components** — Shrinkwrap projects each independently to wrong locations

**Do NOT suggest**: Deformation Transfer, NICP, per-component Shrinkwrap, or any other automatic wrap variant — user has moved on.

**What user wants instead**: QR + external expert consultation for UV. Wrap approach fully abandoned (head v3.4 also unusable — numeric metrics 0.402mm/96.2% but visual quality poor: ear/lip/eye distortion + 178 self-intersections).

**Forward path (v4, 2026-07-29)**: Three-stage evolution route established — Stage 1 MVP brute-force (QR + Smart UV 66° + island_margin=0.03 + bake margin=16px, accept ~2000 islands), Stage 2 3D semantic segmentation + ARAP graded wrap, Stage 3 SMPL-X parametric inverse fitting. See `references/v4-three-stage-roadmap.md` for details, audit corrections to the source research, and stage comparison table. MVP Stage 1 verified working: QR 86K faces → Smart UV → Bake (mean pixel 0.337, no black) → FBX export. See `test02/mvp_pipeline/scripts/` for working scripts. **Updated 2026-07-29**: Final MVP config is QR 125K (117,539 faces, 235K tris, 0 non-manifold, 100% quad) → Smart UV (66°, margin=0.002) → Bake 4K (cage=3mm, ray=5mm, margin=16px, mean=0.413) → FBX with embedded textures. Scripts at `test02/mvp_pipeline/scripts/02_qr_remesh.py` through `05_export_fbx.py`.

**Critical user correction**: 拓扑的目的是"保持高模的细节跟相似度的同时降低面数" — NOT BBox alignment, NOT UV transfer. The wrap must preserve detail+similarity. Pure scale+translate achieves BBox match but loses all surface detail → user rejected it.

**Critical user correction (2026-07-29)**: QR后细分无意义。User explicitly rejected "QR + local subdivision" approach: "QR的模型已经没多少细节了，你迭代100次细分他不也是没细节？" — Subdivision on QR output is interpolation, not detail reconstruction. To get head/hand detail, must increase QR target count or use different retopology tool (not post-QR subdivision).

**QR overlap problem (2026-07-29)**: QR on "clothing+body" double-layer geometry produces ~29/1000 face overlap at clothing seams (cuff, collar). QR cannot distinguish two surfaces that are too close together. Attempted fixes:
- adaptive_size 80% → WORSE (39/1000 overlap, 4 non-manifold edges)
- remove_doubles(threshold=0.0001) → no effect (overlap is face-level, not vertex-level)
- delete overlapping faces → 678 faces deleted but non-manifold edges exploded to 1148 (topology destroyed)
- Instant Meshes (pymeshlab isotropic_explicit_remeshing) → overlap reduced to 1/1000 BUT all triangles (0% quad), 68 non-manifold edges, hand detail lost (0.6% vs 9.0%)

**Verdict**: QR overlap is a STRUCTURAL problem with no automatic fix. Tested 15+ post-processing approaches, ALL failed:
- adaptive_size 20/30/50/80 → no effect (28-39/1000 overlap)
- remove_doubles(threshold=0.0001) → no effect (overlap is face-level)
- delete overlapping faces → 678 deleted, non-manifold edges exploded to 1148
- Laplacian smooth (10 iterations, all overlap verts) → 29→27/1000 (negligible)
- Local Laplacian (overlap verts only, 20 iters) → 27/1000 (negligible — shared neighbors move together)
- Layer-separated smooth (upper verts only, vertices_smooth ×15) → 26/1000 (negligible)
- Voxel Remesh (3mm) → 27/1000, still present
- 沿法线推开顶点0.5mm (all overlap verts) → 29→33/1000 (WORSE — creates new overlaps)
- Push upper-layer-only verts 1mm → 35/1000 (WORSE — boundary new overlaps)
- Sculpt mode SMOOTH brush → **CANNOT use**: `tool_settings.sculpt.brush` is read-only in background mode
- Instant Meshes (pymeshlab isotropic_explicit_remeshing) → 1/1000 overlap BUT 0% quad, 68 non-manifold, hand detail lost
- Decimate pre-processing (keep head/hand detail) → no effect on overlap ratio

**Why manual sculpting works but programmatic doesn't**: User can visually identify the exact boundary between clothing and body layers, apply smooth brush with controlled radius to ONE layer only. Programmatic approaches cannot distinguish which vertices belong to which layer (shared edges/neighbors), so all smoothing moves both layers together. See `references/qr-overlap-test-results.md` for full 15-experiment matrix.

**Root cause**: QR treats "clothing+body" double-layer geometry as a single surface. At clothing seams (cuff, collar), two layers are too close for QR to distinguish — it creates overlapping faces. This is NOT a parameter problem (adaptive_size, hard_edges tested) and NOT a post-processing problem (smooth, Voxel, delete, push all fail). The ONLY fix is pre-QR: separate clothing from body before QR.

User chose to continue with QR but demanded "不能重叠" — this requirement is currently UNRESOLVED programmatically. **User decided to accept the overlap and continue the pipeline (2026-07-29)**: "算了 你先继续吧，用这个拓扑完了的低模做UV那一步". The overlap (~29/1000 sampled faces) is at clothing seams and does not affect Smart UV or Bake output quality. MVP pipeline continued successfully: QR 125K → Smart UV (margin=0.002) → Bake 4K (cage=3mm, ray=5mm) → FBX export.

**User style correction (2026-07-29)**: When documenting results, do NOT present numeric metrics as "success" when visual quality is poor. User explicitly corrected: "怎么总是给人感觉这个方案跑通了一样" — numeric 0.402mm/96.2% does NOT mean the result is usable. Always state both numeric metrics AND visual quality assessment (e.g., "数值达标但视觉质量差，不可用"). This applies to ALL future documentation and reporting.

**User workflow preference (2026-07-29)**: 分步执行，每步完成后给用户检查。不要一口气跑完整个管线。例如QR完成后先给用户blend文件确认，再继续Smart UV。**每次产出结果文件后，必须提供文件路径给用户。**

**MVP完整管线脚本已保存到交付目录 (2026-07-29)**: 完整的可复现MVP管线脚本（高模导入→QR→UV→纹理修复→Bake→FBX）已保存到 `v3_QuadRemesher_交付/scripts/01_highpoly_import.py` 到 `04_bake.py`。输出文件按功能分目录存放（01高模修复/02QR拓扑/03自动UV/04纹理烘焙）。**注意**: QR步骤（02_qr_remesh.py）在当前环境因xremesh license问题无法复现，需从test02复用已有结果。其他步骤均可复现。

**QR后台执行完整流程 (2026-07-30)**:

1. **Blender operator不可用**: `bpy.ops.qremesher.remesh()` 使用modal模式，在`--background`下cancel（无window_manager）
2. **正确调用方式**: 用`conhost`包装xremesh.exe提供GUI环境：
   ```bash
   conhost "C:\...\EngineWin\xremesh.exe" -s "C:\...\RetopoSettings.txt"
   ```
3. **ZED必须杀掉**: `taskkill /F /T /IM Zed.exe` — ZED占GUI资源导致xremesh卡在21.8%进度不动
4. **Settings关键参数**: `ExactQuadCount=0`更稳定；`=1`可能导致崩溃或生成异常面数
5. **进度监控**: 轮询progress.txt（0~1.0浮点数），输出文件retopo.fbx生成即完成
6. **computer-use备选**: 当xremesh后台调用反复失败时，用户偏好使用computer-use桌面自动化工具操作Blender GUI

详细工作流见 `references/xremesh-workflow.md`。

## Key Files

- `方案md记录/v1_MetaHumanWrap/fit_v3.py` — 头部 wrap 参考（❌数值达标但视觉不可用）
- `方案md记录/v1_MetaHumanWrap/Body_Wrap方案失败记录.md` — 9轮失败完整记录
- `test02/output/wrap/wrapped_scale_repair_v1.blend` — BBox对齐结果（用户已否定）
- `references/qr-overlap-test-results.md` — 11种QR重叠消除方案测试结果（全部失败，结构性问题）
