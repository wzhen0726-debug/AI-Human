# UV 折叠（岛内自重叠）检测与修复

## 症状/判据盲区

- **渲染症状**：皮肤上出现突兀的深色短线/污痕（不在 UV 缝/棱线上），烘焙后出现、纹理修复难根除。
- **旧判据盲**：面积均匀度(CV)/岛数/浪费比 全都查不出——它们只看“总面积分布”，不看“面与面是否压叠”。
- **硬判据**：`bpy.ops.uv.select_overlap`（编辑模式，全选→extend=False）→ 统计选中面数 = 重叠面数。必须作为硬门槛（目标=0）。

## 机制

1. 投影式 `uv.smart_project` 对**环状/长条区域**（手臂绕一圈、肩带、长边缘）必然产生岛内自折叠（一个岛展开后自己压自己）。
2. 实测：同一低模，角度 25°~89° 各档折叠面 37~1709，**没有任何角度能天然清零**；换打包器（CONVEX/AABB/各 margin_method）无效（非岛间重叠，是岛内✗）。
3. 折叠 texel 被多个不相邻表面（如“上臂皮肤”与“背心后肩”）共享 → **烘焙时只写得赢的那一面颜色**，另一半表面渲染时显示错色。用“相机射线→面→UV→texel 归属面清单”可铁证。

## 修复配方（生产可用）

```python
# 每轮: 取全部重叠面 + 2环邻域 作为一个选区(各连通分量独立求解)
bpy.ops.object.mode_set(mode='EDIT')
_select_region(mesh, sorted(fold_face_ids), ring=2)   # bmesh 逐面+边+点 select
bpy.ops.uv.unwrap(method='MINIMUM_STRETCH', margin=MARGIN)  # 失败则退 ANGLE_BASED
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.average_islands_scale()   # ★必须: 修复区密度与全布局归一, 否则 CV 爆表(实测5815)
bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method='SCALED',
                        margin=MARGIN, shape_method='CONCAVE', pin=False, merge_overlap=False)
bpy.ops.object.mode_set(mode='OBJECT')
# 重复至 select_overlap=0 (实测一~两轮即清零: 437→0); 顽固小残留用 ring=3 再试一轮
```

- 等价语义 = “在每条折痕处切缝再展平，不动其余布局”。
- **不要** 全网格 `uv.unwrap`：无接缝时整体崩塌（实测 U=0%、全网格报重叠✗）。
- 修复只在**最终选定版**上做一次，不要放进搜索循环（每候选做一遍太慢）。

### 修复失败模式（实测踩坑）

**坑1 — 修复后密度爆表但自查仍报PASS（自证陷阱）**：折叠修复跑完后，`average_islands_scale`+`pack_islands` 作用在**全部岛**上（不是只修复区），若修复区展开面积异常，重新打包后整体密度彻底失衡。实测一次：修复前密度比0.91(✓)→修复后密度比48122(✗✗✗)，但自查因折叠≠0走WARN分支，密度比爆表被掩盖，管线照常输出。**修复后必须独立复测密度比，且密度比必须有自己的阻断门槛，不能依附折叠判定分支。**

**坑2 — 修复迭代震荡不清零**：某些网格上每轮选区25/29面来回震荡（修复→又折叠→再修复），8轮预算用尽仍残留5-7面。此时**绝不能**用"warn不阻断"放行——折叠面在烘焙时会真实产生脏线。正确动作：WARN升级为FAIL，要求用户人工复核该次UV产物，或重跑03（多数情况下一次正常重跑折叠数会落回低位）。

**坑3 — 日志与产物不符时以产物实测为准**：若日志显示折叠修复异常但当前blend实测折叠=0/密度健康，说明日志记录的是另一次未落盘的运行（blend修改时间晚于日志时间）。**判定交付质量时，永远直接读当前blend实测UV数据，不依赖历史日志。** 对照 `ls -l --time-style=full-iso` 的 blend mtime 和 log mtime 可快速证伪。

**坑4 — 修复机制本身破坏布局（2026-09-20）**：`repair_local_folds` 的设计缺陷：每轮把折叠面+2环邻域作为选区重展后，调用 `average_islands_scale`+`pack_islands` 时**作用于全部514个岛**（`bpy.ops.mesh.select_all(action='SELECT')`），不是只修复区。修复区被压缩/放大后，重新打包会扰动所有岛的位置和缩放，导致整体布局劣化（利用率38.6%→63.6%是异常升高，因为岛被压扁了）。**根因：pack_islands 没有 "只调整选中岛" 的模式，一旦全选就是全局重排。** 若必须修复折叠，应：① 修复后仅对修复区做局部缩放归一（不动其余岛）；② 或干脆接受少量折叠残留，用烘焙margin覆盖（margin≥16px可包住大多数折叠texel）。

## 验证（独立反向判据）

- `select_overlap` 复测 = 0。
- 用“相机射线→低模面→UV→读 texel 值”检查：修复前 texel 值(如58)应变为正常皮肤(如145)。
- 同机位渲染三联（旧问题态|新未调整|新已调整）视觉复核：皮肤污痕消失，残余深色若=衣物边缘线则为检测器误报（自然边界）。
