# 眼窝面朝向/接缝圆润 — custom_normal根因 + bmesh索引陷阱 + 多环fillet (2026-08-13 v31/v32)

用户反复反馈"面朝向反了没解决、接缝太锐利"，多轮normal_flip/reverse_faces/recalc全部无效。
最终用控制实验定位真根因，并踩出一串bmesh索引陷阱。全部经端到端验证(18/18 ALL_PASS)。

## 1. 面朝向"修了没效果"的真根因：FBX custom_normal属性

**根因链**：
1. FBX导入的mesh带 `custom_normal` attribute (INT16_2D, domain=CORNER, 每corner一个法线)。
   Blender视口渲染/Face Orientation着色**用custom normal，不反映面绕序**。
2. bmesh新建的面(碗面/fillet带)在该属性上是零向量 → 着色发黑破碎 = 用户看到的"面朝向反了"。
3. 所有 `normal_flip()`/`reverse_faces()` 只改绕序不改custom normal → **显示毫无变化** → "修了没效果"的假象。

**控制实验(必做)**：对比 winding法线 vs `me.corner_normals`(FBX真值)：
```python
fn = np.empty(len(me.polygons)*3, dtype=np.float32); me.polygons.foreach_get('normal', fn)
cn = np.empty(len(me.corner_normals)*3, dtype=np.float32); me.corner_normals.foreach_get('vector', cn)
# loop_start取每面平均corner normal，dot>0=一致
```
实测输入模型绕序与corner normals吻合99.99% → **绕序本来就是对的，不需要任何翻转**。

**修复**：加载后立即删属性，让绕序说了算：
```python
attr = obj.data.attributes.get('custom_normal')
if attr: obj.data.attributes.remove(attr)
sharp = obj.data.attributes.get('sharp_face')
if sharp:
    for i in range(len(sharp.data)): sharp.data[i].value = False
```

## 2. 高模上法线统一的三个错误方案(全部实测翻车)

| 方案 | 结果 | 原因 |
|---|---|---|
| 全局 `recalc_face_normals` | 后脑勺朝内面 67551→199339，恶化3倍 | 高模非流形边破坏flood-fill传播 |
| 质心规则(法线背离顶点质心就翻) | 翻掉422589面，灾难 | 下颌底/腋下等悬垂面法线本就指向质心，头部非凸体 |
| 带区域边界的局部recalc | 重翻31/12面 | 区域边界把碗从皮肤锚点切断，recalc失去正确参考 |

**正解**：删custom_normal + **几何朝向兜底**——只对开口内的面(ring0多边形内+Y深度带)逐面判断：
```python
ring0_poly = [(c[0], c[2]) for c in ring0_coords]   # 坐标快照! 见陷阱2
for f in bm.faces:
    fc = f.calc_center_median()
    if -0.13 < fc.y < -0.08 and point_in_polygon(fc.x, fc.z, ring0_poly):
        if f.normal.dot(center - fc) < 0:   # 背离眼球 → 翻
            f.normal_flip()
```
开口内只有碗/fillet带，皮肤面在开口外不受影响。几何判据不依赖拓扑传播，对非流形免疫。

## 3. bmesh索引陷阱(每个都造成过灾难，血泪教训)

### 陷阱A：新顶点v.index是stale的
`bm.verts.new()`创建的顶点在 `ensure_lookup_table()` 之前 `.index` 是旧值(可能全部相同)。
用它做dict key → 键碰撞 → **89个顶点塌成1个点 → 2136个退化面**。
**规则：新建顶点的位置计算/平滑一律用enumerate索引，永远不用v.index。**

### 陷阱B：dissolve/mode切换后顶点索引重排
保存 `ring0_indices = [v.index ...]`，中间经过 dissolve_faces + mode_set(OBJECT/EDIT) 后，
用旧索引 `bm.verts[i]` 重建得到**乱序散点** → point_in_polygon匹配到海量面 →
一次误翻184866面(整个头部翻乱)。
**规则：跨dissolve/mode切换传递ring必须用坐标快照 `[(v.co.x,v.co.y,v.co.z)]`，
重建时用坐标最近邻匹配，绝不依赖索引。**

### 陷阱C：UV捕获时机
在共享顶点(ring0)上创建新面后，`v.link_loops[0]` 可能返回新面的loop(默认UV=(0,0))，
取到的ring0_uv是(0,0) → 碗面贴图采样角落发黑。
**规则：ring0_uv必须在创建任何新面(chamfer/fillet/碗)之前捕获。**

### 陷阱D：sliver溶解误吞合法微小几何
按"面积<阈值+内部面"溶解碎片时，碗底极点三角扇(末环半径0.05mm，面积极小)也满足判据被误溶
→ 碗底开放边+非流形边。
**规则：溶解判据加深度带限制(如 `fc.y < rim_y + 0.001`)，把极点扇等合法微小几何排除在外。**
溶解后必须复查 open_edges / nonmanifold / ngon / degenerate。

### 陷阱E：recalc_face_normals要求面不重复
BMFace是按需包装对象，`zone + refs` 可能有同一底层面的两个包装 → ValueError。
**去重用 f.index 做key，不用 id(f)。**

## 4. 接缝圆润：多环fillet(用户要求加大倒角+增加面数)

用户明确："这是个高模，我需要你增加面数去做圆润的变化"——**不接受移动顶点/纯smooth shading糊弄**。
单环chamfer(ring0→ring1)只有两个硬折角。v32方案：
1. `CHAMFER_FILLET_RINGS=4` 个中间环：ring0沿"朝碗轴+朝碗底"方向线性插值到ring1(3mm宽2mm深)。
2. Laplace 6轮圆角化：只动中间环，ring0(皮肤边界)固定 → 折线变曲线。
   平滑用邻环+同环邻居4点平均，全部enumerate索引(陷阱A)。
3. 相邻环quad连接，碗面从ring1开始生成。
4. 所有中间环UV继承ring0对应顶点(在v2uv里统一分配)。

验证指标：接缝皮肤tri-fillet quad共享边的法线夹角 mean≈21°，开放边0。

## 5. 验证与判断纪律(用户规则)

- 定量优先：几何bbox/法线/UV用数值判断，vision只用于有无/穿帮的定性确认。
- **判断"面朝向反了"的正确地面真值**：从正面相机看 `f.normal.dot(cam_pos-fc)<0` 的面数，
  并**与输入模型基线对比**——输入模型眼区本就有~94个背面(眼睑悬垂底面，合法几何)，
  流程不新增即为合格。不要用"normal.y方向"这类会误伤凹面/悬垂面的粗判据下结论。
- 每次改动后跑固定检查集：open_edges / nonmanifold(输入自带≤1) / ngon / degenerate / UV-zero /
  碗面朝开口比例 / 前脸+后脑勺朝内面数 vs 输入基线。
