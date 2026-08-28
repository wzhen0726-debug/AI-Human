# 标记点坐标：原始 location vs 约束求值后位置 (2026-08-26 根因，必读)

## 事故链
用户调好了会阴点（视图里显示在 x=0.000 中线），脚本重建绑定后 Hips 骨骼却落在 **x=-0.078**，两条腿不对称（左-0.158/右+0.002）。用户困惑："我没看出来偏啊，哪个方向偏了？"——他看到的没错，是脚本读错了坐标。

## 根因
`rig_from_markers.py` 用 `pos = m.location.copy()` 读标记点位置——这是**原始坐标**。
但三个中线点身上有 `SHRINKWRAP + LIMIT_LOCATION` 约束，用户在视口看到的是**约束求值后**的位置（`matrix_world.translation`），两者脱节：

| 点 | 原始 location（脚本读的） | 求值后 matrix_world（用户看到的） |
|---|---|---|
| 头顶 | x=+0.004 | x=0.000 |
| 颈根 | x=−0.004 | x=0.000 |
| 会阴 | **x=−0.078** ← 骨骼用了这个 | **x=0.000** ← 用户调好的 |
| 10个关节点（无约束） | 两者一致 | |

## 规则
**读取任何可能被约束驱动的对象位置，一律用 `matrix_world.translation`（所见即所得），禁止用 `.location`。**
适用于：绑定生成、动画参考、截图/渲染标注、任何"用户在视口看到什么就用什么"的场景。

## 诊断方法（骨骼位置和标记点对不上时）
写一个对照脚本，逐点打印 `location` 和 `matrix_world.translation`，标出"不一致"的行（诊断脚本：`verify_raw_vs_evaluated.py`，05骨骼绑定/C_诊断工具）：
```python
raw = o.location
eva = o.matrix_world.translation
same = (abs(raw.x-eva.x)+abs(raw.y-eva.y)+abs(raw.z-eva.z)) < 0.001
```
凡是带约束（constraints 非空）且两者不一致的点，就是嫌疑对象。

## 连带坑：约束在 -b 模式下的求值时机
`matrix_world` 要取约束求值后的值，脚本里先 `scn.frame_set(1); scn.update_tag(); bpy.context.view_layer.update()`，确保依赖图已计算再读。

## 修复记录
`rig_from_markers.py` 第66行 `m.location.copy()` → `m.matrix_world.translation.copy()`；重建后 Hips=(0.000,−0.091,0.836)、左右腿完全镜像（±0.080），行走动画测试通过。
