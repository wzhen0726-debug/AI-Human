# 网格拓扑对称（Smart ReSym）技术调研与测试结论

## 核心原理（ZBrush文档确认）

ZBrush Smart ReSym只操作顶点坐标，不触碰UV和拓扑结构。关键在于**拓扑BFS匹配**而非空间匹配：

1. 从对称轴(X=0)顶点出发
2. 沿边BFS扩散，两侧走相同步数的顶点自动配对
3. 只修改vert.co，UV layer（loop层）完全不动

Maxon官方文档确认：`SmartReSym`、`ReSym`、`Mirror and Weld`均只操作顶点位置，不影响UV坐标。

## Blender中验证的关键结论

### 1. vert.co与UV layer独立（100%验证）
所有测试版本UV差异均为0.000000000000000。bmesh架构中vert.co存储在顶点上，UV存储在loop（面角）上，两者是**完全独立的数据层**。

### 2. Blender 5.1 UV批量读写API
```python
# 读取UV（用"vector"属性，不能用"x"/"y"）
uv_data = mesh.uv_layers.active
uvs = np.empty(nloops * 2, dtype=np.float32)
uv_data.uv.foreach_get("vector", uvs)

# 读取loop→顶点映射
loop_verts = np.empty(nloops, dtype=np.int32)
mesh.loops.foreach_get("vertex_index", loop_verts)

# 写入UV
uv_layer.uv.foreach_set("vector", loop_uv.reshape(-1).astype(np.float32))
```
**不能用"x"/"y"属性名**——Blender 5.1会报AttributeError。

### 3. 匹配率天花板
- 拓扑严格对称模型：100%（球体测试验证）
- 拓扑不完全对称模型：74.4%（空间匹配+BFS均在此处遇到天花板）
- Blender内置`symmetry_snap`：约39%（远不如ZBrush）

### 4. 拉普拉斯变形约束可行
- scipy.sparse.csr_matrix + scipy.sparse.linalg.spsolve
- 128K顶点稀疏矩阵求解0.1秒，约束误差0
- 可平滑传播已匹配顶点的位移到未匹配顶点
- 但74.4%匹配中有错误对→拉普拉斯放大错误

### 5. 删半镜像+UV恢复方案
- 完美对称（差异0.00000000），无破面
- 负侧UV恢复率65.9%（匹配原始负侧UV）+ 34.1%降级用正侧UV
- **但不符合"不删几何"的约束**

### 6. 正确流程顺序
先对称化高模网格坐标（只改vert.co不动UV）→ wrap对称低模（MetaHuman模板天然对称）→ 低模UV展开 → 烘焙（纯空间操作，与高模UV无关）

## 测试记录
详见：镜像测试报告.md（test_mirror目录），含9种方案的完整对比数据。
