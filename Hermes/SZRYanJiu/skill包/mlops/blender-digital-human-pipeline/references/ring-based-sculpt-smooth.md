# Ring-based Local Sculpt Smoothing for AI Model Bumps

**适用场景**: AI生成的三维模型（如Tripo）在某个局部区域（如胸口）有一个凸起/鼓包，需要在不影响其他区域的前提下推平。

## 问题
- 直接全局平滑会破坏脖子、肩膀等正常解剖结构
- 法线翻转会搞乱脖子根部（锁骨上窝）的自然凹陷
- 删除极小面会产生破洞，补洞又卡死
- 用凸起顶点自身的邻域做参考会被凸起本身污染（self-contamination）

## 解决方案：环状参考面法

```
inner radius (15mm) = 凸起区域
outer radius (40mm) = 参考面区域
ring zone (15~40mm) = 干净的参考环
```

### 步骤

1. **定位凸起中心**：用最负Y顶点（模型面朝-Y时）或KDTree局部凸起检测
2. **定义半径**：inner_r = 15mm（覆盖凸起），outer_r = 40mm（确保参考面干净）
3. **对每个凸起顶点**：
   - 用KDTree找outer_r范围内的顶点
   - 排除inner_r * 0.7以内的顶点（避免凸起自污染）
   - 剩余顶点做参考面平均位置
   - 将凸起顶点小步长（0.15）推向量参考面平均
4. **迭代**：15次迭代，每5次重建KDTree（顶点坐标已变）
5. **验证**：检查相邻区域（脖子根部z=1.38、肚脐z=1.00）的顶点数是否不变

### 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| inner_r | 15mm | 覆盖凸起本身 |
| outer_r | 40mm | 参考面范围，足够大 |
| 步长 | 0.15 | 小步长模拟雕刻笔刷 |
| 迭代 | 15 | 多次小步长逼近 |
| 排除内圈 | inner_r*0.7 | 避免凸起自污染 |

### 代码模板

```python
import bpy, bmesh
from mathutils import Vector, kdtree

bm = bmesh.new()
bm.from_mesh(obj.data)
bm.verts.ensure_lookup_table()

# 凸起区域
cx, cz = -0.043, 1.209  # 凸起中心
inner_r = 0.015
outer_r = 0.040

bump_verts = [v for v in bm.verts
    if ((v.co.x-cx)**2 + (v.co.z-cz)**2)**0.5 < inner_r]

# KDTree
kd = kdtree.KDTree(len(bm.verts))
for vi, v in enumerate(bm.verts): kd.insert(v.co, vi)
kd.balance()

for it in range(15):
    for v in bump_verts:
        # 环状参考
        ring = []
        for (co, idx, dist) in kd.find_range(v.co, outer_r):
            if dist < inner_r * 0.7: continue
            ring.append(bm.verts[idx].co)
        if len(ring) < 30: continue
        avg = Vector((0,0,0))
        for rv in ring: avg += rv
        avg /= len(ring)
        v.co = v.co.lerp(avg, 0.15)
    
    if (it+1) % 5 == 0:
        kd = kdtree.KDTree(len(bm.verts))
        for vi, v in enumerate(bm.verts): kd.insert(v.co, vi)
        kd.balance()

bm.to_mesh(obj.data); bm.free(); obj.data.update()
```

### 陷阱

- ❌ **不要全局法线翻转**：胸口z=1.20~1.40范围包含脖子根部（z=1.38），锁骨上窝的面法线朝内是正常的解剖结构
- ❌ **不要删除极小面**：AI模型有大量<1mm²的面，删除后补洞在190万面上会卡死
- ❌ **不要用凸起自身做参考**：凸起顶点和它的邻域都是凸的一部分，往自己的平均推没用
- ✅ **用环状参考面**：15~40mm范围内的干净顶点做参考，推平凸起

### 验证方法

修复后检查三个区域：
1. 凸起中心：最负Y值是否从-0.148降到-0.143左右
2. 脖子根部(z=1.38)：顶点数不变（3556个）
3. 肚脐(z=1.00)：顶点数不变（4339个）
4. 非流形边和边界边不变