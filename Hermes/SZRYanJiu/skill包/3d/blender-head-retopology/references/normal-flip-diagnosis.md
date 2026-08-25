# 法线翻转诊断与修复 — BVH Fibonacci 射线法

**日期**: 2026-07-24  
**模型**: tripoTpose (193 万面)  
**问题**: 材质预览/渲染模式下胯部/裆部黑色碎裂或透明，实体模式正常

---

## 症状

| 模式 | 表现 |
|------|------|
| 实体模式 (Solid) | 正常，无异常 |
| 材质预览 (Material Preview) | 胯部黑色碎裂/透明 |
| 渲染模式 (Rendered) | 同上 |

用户描述："不是显示黑色，是透明了，黑色的是背景"

---

## 为什么 Shift+N (normals_make_consistent) 不稳定

`bpy.ops.mesh.normals_make_consistent(inside=False)` 基于面邻接传播算法。
在 AI 高模（多层网格：衣物外层+衣物内层+身体层）上传播断裂。

### 实测数据 (2026-07-24, tripoTpose, 193万面)

| Shift+N 次数 | 法线朝内面片数 | 效果 |
|-------------|--------------|------|
| 初始（v3修复后） | 0 | 正确 |
| 第 1 次 | 126,779 | 暴增！正确面被翻转 |
| 第 2 次 | 123,812 | 继续传播错误 |
| 第 3 次 | 8,826 | 部分恢复但不可预测 |

**结论**：Shift+N 在多层网格上每次结果不同，不可作为可靠方案。

### 用户经验佐证

用户报告："实际操作做了两遍才好，做了3遍它又错了"——与实测数据一致。
`normals_make_consistent` 在复杂拓扑上是非确定性的。

---

## BVH Fibonacci 球面射线法（推荐方案）

### 原理

从模型外部均匀发射射线，命中 BVH 树的第一个面就是"外表面"。
内层面片不会被射线命中，其法线朝内是正常的（衣物内侧应朝向身体）。
只翻转外表面中法线朝内的面。

### 为什么 Fibonacci 球面优于随机采样

| 采样方式 | 射线数 | 第1轮翻转 | 第2轮翻转 | 收敛 |
|---------|--------|----------|----------|------|
| 随机 | 50000 | 2602 | 2518 | ❌ 5轮不收敛 |
| **Fibonacci** | **50000** | **1416** | **0** | **✅ 2轮收敛** |

随机采样有方向重复，某些外表面从未被命中。Fibonacci 球面分布更均匀。

### 完整代码

```python
import bpy, bmesh, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def fix_normals_bvh(mesh_obj, max_rounds=5, n_rays=50000):
    """用 BVH Fibonacci 射线精确翻转外表面法线朝内的面"""
    mesh = mesh_obj.data
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    zs = [v.co.z for v in mesh.vertices]
    cx = (min(xs)+max(xs))/2
    cy = (min(ys)+max(ys))/2
    cz = (min(zs)+max(zs))/2
    dim = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    center = Vector((cx, cy, cz))

    total_flipped = 0
    golden = (1 + math.sqrt(5)) / 2

    for rnd in range(max_rounds):
        bm = bmesh.new(); bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        bvh = BVHTree.FromBMesh(bm)

        # Fibonacci 球面均匀采样
        hit_faces = set()
        for i in range(n_rays):
            theta = 2 * math.pi * i / golden
            phi = math.acos(1 - 2 * (i + 0.5) / n_rays)
            dx = math.sin(phi) * math.cos(theta)
            dy = math.sin(phi) * math.sin(theta)
            dz = math.cos(phi)
            origin = center + Vector((dx, dy, dz)) * dim
            direction = Vector((-dx, -dy, -dz))
            hit, normal, fi, _ = bvh.ray_cast(origin, direction, dim*3)
            if hit and fi is not None:
                hit_faces.add(fi)

        # 翻转外表面中法线朝内的 (dot < -0.3)
        to_flip = []
        for fi in hit_faces:
            f = bm.faces[fi]
            c = f.calc_center_median()
            outward = (c - center).normalized()
            if f.normal.dot(outward) < -0.3:
                to_flip.append(fi)

        for fi in to_flip:
            bm.faces.ensure_lookup_table()
            bm.faces[fi].normal_flip()

        bm.to_mesh(mesh); bm.free()
        mesh.update()

        print(f"round {rnd+1}: hit={len(hit_faces)}, flipped={len(to_flip)}")
        total_flipped += len(to_flip)
        if len(to_flip) == 0:
            print("converged!")
            break

    print(f"total flipped: {total_flipped}")
    return total_flipped
```

### 性能

- 193 万面模型：每轮 ~30 秒（BVH 构建 + 50000 射线）
- 2 轮收敛：总时间 ~60 秒
- 翻转面数精确：~1400（vs Shift+N 的 12.7万 vs 中心外向法的 70万）

---

## 失败方案记录

### 中心外向法（v2，灾难性）

翻转 701,355 面（36%），全身白色斑块。
**不适用于非凸区域**（腋下、裆部、指缝）。

### 保守 Y 方向翻转（v3，部分有效）

翻转 113,083 面，只处理前侧 Y 方向，后侧和腿部漏处理。

### 重叠面删除（v1，产生破洞）

删除 23 组重叠面导致短裤白色破洞，回退。

### 平滑侧面法线（失败）

平滑衣物-身体间隙侧面导致破洞，回退。

---

## 诊断流程

```
1. 用户报告"黑色/透明"
   ↓
2. 确认是颜色黑（法线翻转）还是透明（缺失/剔除）
   → 用户描述"透明，黑色是背景" → 剔除/缺失
   ↓
3. 检查边界边 = 0？→ 是 → 无破洞
   ↓
4. 检查重叠面法线夹角 >150°？→ 否 → 排除 z-fighting
   ↓
5. 检查问题区域法线方向 → n.y > 0 在前侧 → 确认翻转
   ↓
6. BVH Fibonacci 射线法翻转 → 验证 inward=0
```

---

## 关键教训

| 教训 | 说明 |
|------|------|
| **Shift+N 不可靠** | 多层网格上非确定性，每次结果不同 |
| **中心外向法不可用于非凸区域** | 腋下/裆部/指缝会错误翻转 |
| **BVH 射线法是唯一可靠方案** | 不依赖邻接传播，直接检测可见性 |
| **Fibonacci > 随机** | 均匀采样确保所有外表面被命中 |
| **只翻外表面** | 内层面片法线朝内是正常的 |
| **不要平滑间隙** | 衣物-身体间隙侧面是几何特征，平滑导致破洞 |

---

## 相关文档

- `glb-matrix-world-pitfall.md` — 混元模型 matrix_world 预旋转
- `fragment-provenance-diagnosis.md` — 碎片溯源诊断方法
- `brush-background-research.md` — background 模式 sculpt brush 限制