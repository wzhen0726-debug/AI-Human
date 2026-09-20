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

## 验证（独立反向判据）

- `select_overlap` 复测 = 0。
- 用“相机射线→低模面→UV→读 texel 值”检查：修复前 texel 值(如58)应变为正常皮肤(如145)。
- 同机位渲染三联（旧问题态|新未调整|新已调整）视觉复核：皮肤污痕消失，残余深色若=衣物边缘线则为检测器误报（自然边界）。
