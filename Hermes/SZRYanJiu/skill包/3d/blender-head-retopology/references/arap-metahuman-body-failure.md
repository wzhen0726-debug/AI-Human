# ARAP 在 MetaHuman Body 上的失败分析 (2026-07-28)

## 问题

libigl 的 `arap_precomputation` 在 MetaHuman Body 网格上失败，报错 `RuntimeError: arap_precomputation failed`。

## 根因

**MetaHuman Body 有 14 个连通分量**（connected components），不是单一连通网格：

| 分量 | 顶点数 | 中心位置 | 说明 |
|------|--------|----------|------|
| 0-1 | 3345x2 | (±0.1, -0.05, 0.66) | 左右腿（大腿+小腿） |
| 2-3 | 2927x2 | (±0.8, 0.1, 1.36) | 左右手（手掌） |
| 4-5 | 2789x2 | (±0.48, 0.05, 1.43) | 左右手臂（上臂+前臂） |
| 6-7 | 2125x2 | (±0.77, 0.1, 1.34) | 左右手指 |
| 8-9 | 2003x2 | (±0.15, 0.25, -0.29) | 左右脚（脚底） |
| 10-11 | 1789+1565 | (0, ±0.05, 1.28) | 躯干前后 |
| 12-13 | 1301x2 | (±0.15, 0.25, -0.29) | 左右脚（脚背） |

**ARAP 要求网格是连通的**，多个连通分量导致预计算失败。

## 检测方法

```python
from collections import defaultdict

# 构建邻接表
adj = defaultdict(set)
for f in F:
    for i in range(3):
        adj[f[i]].add(f[(i+1)%3])
        adj[f[(i+1)%3]].add(f[i])

# BFS找连通分量
visited = np.zeros(len(V), dtype=bool)
components = []
for i in range(len(V)):
    if not visited[i]:
        queue = [i]
        comp = []
        while queue:
            v = queue.pop(0)
            if visited[v]:
                continue
            visited[v] = True
            comp.append(v)
            for u in adj[v]:
                if not visited[u]:
                    queue.append(u)
        components.append(comp)

print(f'连通分量: {len(components)}')
```

## 后果

即使提取最大连通分量（3345 verts），约束点也只剩 3 个（总共 16 个），ARAP 很快收敛但无实际意义。

## 解决方案

1. **分区域独立求解**：四肢、躯干分别做 ARAP，然后合并
2. **用最大连通分量**：只用躯干部分（但损失四肢）
3. **换方法**：RBF、Laplacian、骨骼驱动等不依赖连通性的方法

## 不要做的事

- ❌ 不要在不检查连通性的情况下直接 `arap_precomputation`
- ❌ 不要假设 MetaHuman Body 是单一连通网格
- ❌ 不要试图用 ARAP 处理多分量网格而不分组

## 参考

- libigl ARAP 文档：https://libigl.github.io/
- MetaHuman Body 结构分析：见 `metahuman-body-wrap-workflow.md`
