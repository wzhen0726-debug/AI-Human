# Repair Pipeline v7 — High-Poly Geometry Repair WITHOUT Voxel Remesh (2026-07-23)

**CRITICAL CORRECTION of v6**: Voxel Remesh (even at voxel_size=0.003) destroys
facial detail — the 34K-54K proxy model loses 80-90% of facial features (lips,
nose, eyes). The user explicitly corrected: "网格修复后的面数好少啊，面部细节
都快没了" and "34k模型的意义是什么？反正我自己思考下，最后给我的整个的
高模修复结果就是一个做了网格修复跟黏连修复的高面数模型吧？"

## Correct Approach: No Voxel Remesh, Preserve High Face Count

**Input**: Raw AI GLB (Tripo: 1.13M verts / 1.93M faces, 516K non-manifold edges)
**Output**: Cleaned high-poly (964K verts / 1.93M faces, 27 non-manifold, 24 boundary)
**Key difference from v6**: NO Voxel Remesh. Only geometry cleanup.

The output goes directly to Quad Remesher — QR handles the face-count reduction.
The repair stage's job is to fix topology (non-manifold, holes, orientation),
NOT to reduce faces.

## Pipeline Steps (10 stages + 1 final weld)

1. **Orientation**: Detect `dim_y > dim_x * 1.8` → rotate 90° CW around Z.
2. **Center & ground**: X=0, Y=0, Z=0 (feet at origin).
3. **Remove doubles**: `remove_doubles(threshold=0.0001)`. Tripo: 1.13M→964K verts.
4. **Dissolve degenerate**: `bmesh.ops.dissolve_faces()` for zero-area faces.
5. **Fill holes**: `fill_holes(sides=0)` — close all boundary edge loops.
6. **Fix non-manifold edges**: Find edges with >2 link_faces, remove extra faces.
7. **Laplacian smooth**: 2 iterations, factor=0.3 (gentle, preserve detail).
8. **Final fill + remove doubles**: Close residual holes, merge coincident verts.
9. **Re-ground**: Smoothing shifts Z ~2mm; subtract `min(Z)`.
10. **Quality verification**: 11 checks (see below).
11. **Final weld for QR** (v17, 2026-07-31): `remove_doubles(dist=0.0001)` + `edgeloop_fill` — ensures closed manifold before saving blend. **Critical**: without this, QR (xremesh) stalls at ~21% due to fragmented input mesh (172K unwelded verts + 517K boundary edges). See `qr-input-mesh-welding.md`.

## Adhesion Detection + Repair (merged into same stage)

Runs AFTER mesh repair on the same high-poly model:

1. **KDTree** on all face centers (193万 faces, builds in ~0.5s).
2. **Query pairs** within `2 * threshold` radius.
3. **Filter**: non-adjacent (no shared verts) + normal direction check
   (`n_i · dir > 0.5` AND `n_j · -dir > 0.5` — strict, filters clothing-on-body).
4. **Fix**: Push affected verts along normals (0.3mm step), then smooth
   affected region (3 iterations, factor=0.15).
5. **Verify**: Re-scan to confirm pair reduction.

**Note**: On high-poly (193万面), expect 5000+ pairs at 5mm threshold.
Most are legitimate close surfaces (clothing on body), not true adhesion.
The strict `dot > 0.5` filter reduces false positives. Remaining pairs after
fix indicate areas needing manual inspection.

## ⚠️ `normals_make_consistent` — 2026-07-24 结论修正(原"NEVER call"结论被推翻)

**原结论(错误)**: "NEVER call `normals_make_consistent` — it flips correct faces on 193万面."
**修正后(同日后续实验)**: 删除该调用并没有解决问题。

**实验证据**:
- 删掉 `repair.py` 中两处 `normals_make_consistent` 后,重跑管线生成新 `01_repair.blend`
- 与"正确的" `01_repair_no_normal_fix.blend` 做 5000 个面对比:**法线方向完全一致**
- 但用户仍报告"胯部面朝向不对,着色模式下出现空洞,背景透出"
- 用户对**同一文件**手动 Shift+N(即 `normals_make_consistent`)能修好 — 说明 GUI 版本和 background 版本行为不同

**真正的根因(2026-07-24 第二次修正 — 仍未完全定位, 但排除了两个假根因)**:
- ❌ 假根因#1: `normals_make_consistent` — 删掉后问题没解决
- ❌ 假根因#2: `fill_holes` 在胯部凹陷区补错 — 用 `repair_final.py` 完整复刻(不做任何法线操作)后, 新文件和"用户认为正确的文件"在胯部 413,612 面上做 5000 采样法线对比, **方向完全一致**, 背面剔除渲染 0 个洞. 两个文件几何上是一样的
- ✅ 高度怀疑: 用户在 Blender GUI 里打开的可能是 `.blend1` 旧备份(时间戳 18:26, 含 normals_make_consistent 的旧版), 不是 18:34 的新 `01_repair.blend`. 用户再次确认后表示"之前是去 tripoTpose 文件夹去看了" — 即看的不是最新主输出
- ⚠️ BVH 外表面检测在凹陷区域(裆部/腋下/衣物褶皱)确实不可靠 — 500 采样显示 0 翻转但视觉可能有问题, 射线从外部进不到裆部深处. 需要用其他方式验证凹陷区(如同一模型新旧两版几何 diff)

**给未来 agent 的实战流程 (2026-07-24 验证有效)**:
1. 用户说"法线不对"时, **先确认 ta 看的是哪个文件** — 列出目录按 mtime 排序, 问 ta 打开的是不是最新那份. `.blend1` 是 Blender 自动备份, 是上一版的旧状态
2. 如果文件路径正确, **再做法线 diff** — 把"正确的"和"错误的"文件加载进同一 Blender session, 按面心最近邻配对, 比较法线方向 (采样 5000). 若全部一致, 差异不在模型本身
3. 若两文件几何一致但用户坚称视觉不同, 检查 GUI 显示设置(face orientation overlay / backface culling / 材质模式) — 不是 mesh 数据问题
4. **绝对不要在没做 step 1-3 前改 repair.py** — 本次 session 浪费了一轮"删 normals_make_consistent → 重跑 → 没用 → 才发现看错文件"

**不要做的事**:
- ❌ 不要在 background 模式下迭代跑 `normals_make_consistent` — 实验证实背面从 235K 增到 307K(+26%),反而更糟
- ❌ 不要仅凭 BVH 外表面检测判断凹陷区域(裆部/腋下/衣物褶皱)法线对错 — 它会给出"all clear"的假阴性
- ❌ 不要在没真正复刻"参考正确文件"流程前就下结论 — 用户明确说"参考那两个正确模型处理方案",应该先做 step-by-step diff 再动手

**当前可用方案**:
- 让用户在 Blender GUI 手动 Shift+N(已知能修好),或
- 用 `repair_final.py`(已验证可产生正确法线的脚本)作为基线重跑

**操作手册版本留痕 (2026-07-24)**: 该阶段最终操作手册存于
`方案md记录/v3_QuadRemesher/01高模修复与黏连检测/高模修复操作手册_v16.md`(md格式)。
v7-v15 docx 旧版已全部删除。后续每个阶段的手册按 milestone 子文件夹归档
(`01高模修复与黏连检测/`, `02QuadRemesher拓扑/`, `03自动UV/`, ...),不动 docx。

**Verification (axis-balance ratio)**: After repair, sample face normals and
check axis-pair balance. For a correct human mesh, no axis pair should be
skewed more than ~1.5:1. The bad state had back+Y/front−Y = 24.3/16.9 = 1.44.
After fix, y-ratio = 1.04, z-ratio = 1.08, x-ratio = 1.02.

```python
import bpy
obj = [o for o in bpy.data.objects if o.type=='MESH'][0]
up=down=front=back=xp=xm=0
for p in obj.data.polygons:
    n = p.normal
    if n.z > 0.7: up += 1
    elif n.z < -0.7: down += 1
    if n.y < -0.7: front += 1
    elif n.y > 0.7: back += 1
    if n.x > 0.7: xp += 1
    elif n.x < -0.7: xm += 1
t = len(obj.data.polygons)
def ratio(a, b):
    hi, lo = max(a, b), max(min(a, b), 1e-9)
    return hi / lo
assert ratio(up/t, down/t) < 1.5, f"Z-axis normals skewed: {ratio(up/t,down/t):.2f}"
assert ratio(front/t, back/t) < 1.5, f"Y-axis normals skewed: {ratio(front/t,back/t):.2f}"
assert ratio(xp/t, xm/t) < 1.5, f"X-axis normals skewed: {ratio(xp/t,xm/t):.2f}"
```

## Quality Check Script (`repair_qa.py`)

11 checks — for high-poly (no Voxel Remesh), non_manifold and boundary
tolerances are relaxed (≤50 instead of 0, QR can handle):

| Check | Condition | v7 Measured |
|-------|-----------|-------------|
| non_manifold_edges | ≤ 50 | 27 |
| boundary_edges | ≤ 50 | 24 |
| loose_verts | == 0 | 0 |
| degenerate_faces | == 0 | 0 |
| oriented_arms_along_x | dim_x > dim_y * 1.5 | True |
| centered_x | |cx| < 0.01 | -0.006 |
| centered_y | |cy| < 0.05 | -0.034 |
| grounded_z | |min_z| < 0.005 | True |
| face_count_min | ≥ 100,000 | 1,929,579 |
| height_range | 0.8m ≤ dim_z ≤ 2.5m | 0.976m |

Run: `blender --background 01_repair.blend --factory-startup --python repair_qa.py`

## Why No Voxel Remesh?

Voxel Remesh converts the mesh to a uniform voxel grid, then reconstructs.
At any voxel size that produces a reasonable proxy (34K-96K faces), it
**destroys all facial detail** — lips lose their edges, nose becomes a blob,
eye sockets flatten. Vision analysis confirmed 80-90% detail loss at
voxel_size=0.004 (54K faces) and 0.005 (34K faces).

The original Tripo high-poly (193万面) has excellent facial detail. The
repair stage should preserve it. Quad Remesher (next stage) does the
face-count reduction with curvature-adaptive retopology that respects
facial features.

## Verified Results (2026-07-23)

- Input: 1,137,322 verts / 1,930,148 faces / 516,960 non-manifold edges
- Output: 964,761 verts / 1,929,579 faces / 27 non-manifold / 24 boundary
- Facial detail: **fully preserved** (vision-verified)
- All 11 QA checks: PASS
- Adhesion: 5018 pairs detected, 243 verts pushed, 5017 remaining
  (high-poly has many legitimate close-surface pairs)

## File Locations

- `test03_SimplifiedPipeline/scripts/repair.py` — mesh repair (no Voxel Remesh)
- `test03_SimplifiedPipeline/scripts/adhesion.py` — adhesion detect + fix
- `test03_SimplifiedPipeline/scripts/run_repair.py` — one-click launcher (both)
- `test03_SimplifiedPipeline/scripts/repair_qa.py` — quality check
- `test03_SimplifiedPipeline/v6_run/01_repair.blend` — output model

Config: `smooth_iterations=2`, `smooth_factor=0.3` (no voxel_size param)
