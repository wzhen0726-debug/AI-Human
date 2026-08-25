# BVH 射线投票法修复法线 — 完整实现与教训

**日期**: 2026-07-24  
**来源**: tripoTpose 法线修复实战  
**关键教训**: BVH 缓存法线导致重复翻转，必须检测与修改解耦

---

## 一、致命 Bug：BVH 缓存法线

### 错误实现（已废弃）

```python
# ❌ 射线循环中直接翻转 —— 误伤！
for i in range(n_rays):
    hit, normal, fi, _ = bvh.ray_cast(origin, ray_dir, dim*4)
    if hit and fi is not None and normal.dot(ray_dir) > 0:
        bm.faces[fi].normal_flip()  # BVH 缓存旧法线，同一条面被翻转多次
```

**问题**：BVH 树在循环外构建，缓存了翻转前的法线。第 N 条射线翻转面 fi 后，第 N+K 条射线再次命中 fi 时，BVH 返回的还是旧法线 → 再次满足翻转条件 → 又翻转回去。

**结果**：同一条面被翻转 2/4/6 次（看似没变）或 1/3/5 次（错误），导致"修了几遍反而错"。

---

## 二、正确实现：投票制（检测与修改解耦）

### 核心代码

```python
import bmesh, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def fix_normals_voting(mesh, n_rays=50000):
    # 包围盒
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    zs = [v.co.z for v in mesh.vertices]
    center = Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    dim = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bvh = BVHTree.FromBMesh(bm)
    
    # 1. 收集投票（不修改）
    face_votes = {f.index: [0, 0] for f in bm.faces}
    golden = (1 + math.sqrt(5)) / 2
    
    for i in range(n_rays):
        # Fibonacci 球面均匀采样
        theta = 2 * math.pi * i / golden
        phi = math.acos(1 - 2 * (i + 0.5) / n_rays)
        dx = math.sin(phi) * math.cos(theta)
        dy = math.sin(phi) * math.sin(theta)
        dz = math.cos(phi)
        
        ray_dir = Vector((-dx, -dy, -dz))  # 外→内
        origin = center + Vector((dx, dy, dz)) * (dim * 1.5)
        
        hit, normal, fi, _ = bvh.ray_cast(origin, ray_dir, dim * 4)
        if hit and fi is not None:
            if normal.dot(ray_dir) > 0:
                face_votes[fi][0] += 1  # 朝内（错误）
            else:
                face_votes[fi][1] += 1  # 朝外（正确）
    
    # 2. 统一翻转（只执行一次）
    flipped = 0
    for fi, (wrong, correct) in face_votes.items():
        if (wrong + correct > 0) and (wrong > correct):
            bm.faces[fi].normal_flip()
            flipped += 1
    
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return flipped
```

---

## 三、实测数据

| 模型 | 面数 | 射线数 | 翻转数 | 收敛轮数 |
|------|------|--------|--------|----------|
| tripoTpose | 1,930,105 | 50,000 | **0** | 1 |
| 混元Apose | 1,499,588 | 50,000 | **0** | 1 |

**之前的 319 面翻转是 BVH 缓存 bug 误伤，投票制正确判定为 0。**

---

## 四、为什么投票制有效

| 机制 | 作用 |
|------|------|
| 检测与修改解耦 | 避免 BVH 缓存法线导致的重复翻转 |
| 多数表决 | 单条偏折射线误伤被多数正确判定覆盖 |
| 统一执行 | 所有面只翻转一次，不会翻转回错误方向 |

---

## 五、Shift+N 为什么不可靠

`normals_make_consistent` 基于面邻接传播"统一方向"，在 AI 高模多层网格（衣物外层+内层+身体层）上传播断裂。

实测（tripoTpose，193 万面）：
- 第 1 次：12.7 万面朝内（暴增）
- 第 2 次：12.4 万面朝内
- 第 3 次：8.8 千面朝内（部分恢复但不稳定）

**用户经验**："做了两遍才好，做了 3 遍又错了" —— 非确定性，不可复现。

---

## 六、遗留问题（非几何）

| 问题 | 性质 | 处理 |
|------|------|------|
| 腿部白色斑块 | 贴图/纹理 | UV/贴图阶段处理 |
| 裤脚毛边 | 贴图/UV | 非几何问题 |
| 腰部贴图瑕疵 | 贴图 | 黑色斑块渗透，非几何 |