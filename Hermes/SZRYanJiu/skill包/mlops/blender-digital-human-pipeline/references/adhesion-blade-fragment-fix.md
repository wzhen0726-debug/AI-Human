# 黏连修复刀片碎片根因与修复（v9, 2026-07-23）

## 问题现象

用户在修复后高模左手旁发现"黑色刀片状物体"，质疑是否为修复流程引入。
经逐阶段 blade 计数回溯确认：

```
[0-initial] blade_faces=0
[1-REMOVE_DOUBLES] blade_faces=0
[2-dissolve_degen] blade_faces=0
[3-fill_holes] blade_faces=0
[4-fix_non_manifold] blade_faces=0
[5-laplacian] blade_faces=0
[6-final_fill] blade_faces=0
[8-ADHESION_FIX] blade_faces=160   ← 根因
```

碎片集中在左手（X≈-0.47, Z≈0.76-0.79），共 160 面、54 簇，
特征：X 厚 6-21mm，Y 展开 30-108mm，典型"刀片"几何。

## 根因机制

`fix_adhesion` 的原始实现有两个缺陷：

1. **用变形后法线计算推开方向**：顶点被多个黏连对共享时，
   法线随每次推移动态变化，方向逐渐失控
2. **无位移上限**：单点可被数十个黏连对叠加推动，
   在 AI 融合手区域（指缝间双层皮 <5mm）把过渡面拉成细长三角形

`remove_doubles(threshold=0.0001)` 也有贡献：0.1mm 阈值会把
近距双层皮的顶点合并，预先制造了可被拉成刀片的拓扑结构。

## 修复方案（三层）

### 1. 检测端 — 四肢末端排除区

AI 手部/足部几何不可靠（融合手、薄片脚），在这些区域做黏连推开
必然产生碎片。排除区：

```python
def _in_exclusion_zone(c):
    return abs(c.x) > 0.42 or c.z < 0.10  # 手腕以远 + 脚踝以下
```

**注意**：排除区阈值不能太宽。`|X|>0.35` 会排除手臂大部分面
（手臂占人体表面积~30%），导致 detect 前 5 万面 pairs=0、
120 秒时间上限触发。`|X|>0.42` 只排除手掌/手指，保留手臂。

### 2. 推开端 — 检测法线 + 位移 clamp + 渐进平滑

```python
# 用检测时的法线（未变形）
n_i = f_i.normal.normalized()
affected[v.index] += n_i * push_step

# clamp 单点最大位移
max_displacement = push_step * 3.0  # 1.5mm
if push_vec.length > max_displacement:
    push_vec = push_vec.normalized() * max_displacement

# 渐进平滑：0.35 → 0.10
for it in range(smooth_iter):
    f = 0.35 - 0.25 * (it / max(smooth_iter - 1, 1))
    bpy.ops.mesh.vertices_smooth(factor=f, repeat=1)
```

### 3. 预防端 — remove_doubles 阈值收紧

```python
# 0.05mm（原 0.1mm），避免合并近距双层皮
bpy.ops.mesh.remove_doubles(threshold=0.00005)
```

## 性能优化

193 万面 KDTree detect 的瓶颈不是排除区过滤，而是 find_range 循环本身。
v7 能 30 秒跑完是因为 max_pairs=5000 提前 break（前 5% 面即集满）。
排除区过滤后 pairs 增长慢，需要：

```python
# 扫描上限 + 时间上限
scan_limit = max(len(active_faces) // 3, 80000)
time_limit = 120.0

# 快速复检模式（二次 detect 用）
if max_pairs <= 1000:
    scan_limit = 100000
    time_limit = 30.0
```

二次 detect 只做快速抽检（100K 面/30s），不做全量扫描。

## 验证结果

| 指标 | v7（修复前） | v9（修复后） |
|------|------------|------------|
| blade_faces | 160 | **0** |
| 非流形边 | 27 | **1** |
| 水密 | False | **True** |
| 顶点数 | 964,761 | 965,018 |
| 面数 | 1,929,579 | 1,930,105 |
| clamped 顶点 | — | 222 |
| 总时间 | ~60s | ~60s |

## 相关文件

- 碎片溯源诊断流程：`blender-head-retopology/references/fragment-provenance-diagnosis.md`
- v7 修复管线：`references/repair-pipeline-v7.md`
- 生产脚本：`scripts/adhesion.py`, `scripts/repair.py`, `scripts/repair_qa.py`
