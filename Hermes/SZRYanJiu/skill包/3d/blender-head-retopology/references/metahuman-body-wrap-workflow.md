# MetaHuman Body Wrap Workflow — Failed Attempt Analysis

Date: 2026-07-27. Attempted MetaHuman body wrap onto Tripo T-pose high-poly model.

## Input Assets

| Asset | Vertices | Faces | Pose | Notes |
|-------|----------|-------|------|-------|
| Tripo T-pose | 1,137,322 | ~1,930,148 | T-pose | AI生成，含宽松衣服，1.8m |
| MetaHuman Body | 32,334 | 60,816 | A-pose | 全三角面，无骨骼，UV第二通道 |
| MetaHuman Head | 24,414 | 48,004 | A-pose | 独立网格，UV第一通道 |

## Attempted Workflow

### Phase 1: Coordinate Unification
- Tripo: 绕X轴+90°站立 → 绕Z轴+90°正面朝-Y → 缩放到1.8m
- MetaHuman: 绕Z轴-90°统一坐标系 → 缩放到1.8m
- 结果： 坐标系统一（X=厚度， Y=深度， Z=身高）

### Phase 2: Landmark Detection
- 尝试1: 人体比例估算（肘62%、腕42%身高）→ A-pose误差30-50cm，失败
- 尝试2: 拓扑分析（法线/曲率找关节凹陷）→ 左右不对称dX 0.24，部分失败
- 尝试3: 用户手动空对象标记 → 用户提供16点，成功

### Phase 3: Wrap Attempts

| Attempt | Method | Mean Dist | <2mm% | Max Dist | Result |
|---------|--------|-----------|-------|----------|--------|
| v1 | Shrinkwrap全身 | 2.01mm | 53.1% | 7.55mm | 严重变形 |
| v2 | Shrinkwrap+锚定 | 2.13mm | 50.5% | 8.27mm | 更差 |
| v3 | 先旋转手臂T-pose再Shrinkwrap | 2.06mm | 51.0% | 7.55mm | 无改善 |
| v4 | 先Shrinkwrap躯干再旋转手臂 | — | — | — | 未验证 |

### Phase 4: Deformation Analysis

**Z范围异常**: -0.868 ~ 0.735 （正常应 -0.2 ~ 0.2)
- 48%顶点 (15,591/32,334) |Z| > 0.5
- 全身从脚（Y=0.007）到胸（Y=1.432）受影响

**根因**: Shrinkwrap NEAREST_SURFACEPOINT 将 MetaHuman 顶点投射到 Tripo 衣服表面，而非身体表面。Tripo 含宽松衣服，衣服下无身体几何，Shrinkwrap 无语义理解（衣服 vs 皮肤）。

## Key Failures

### 1. Clothing Interference (PRIMARY)
Tripo高模含宽松衣服，Shrinkwrap被衣服表面吸引：
- 身体轮廓被衣服形状主导
- 48%顶点Z方向异常位移
- 精度无法达到可用水平（>2mm）

### 2. Pose Mismatch (SECONDARY)
- MetaHuman A-pose（手臂下垂45°）
- Tripo T-pose（手臂水平）
- 旋转手臂到T-pose后，Shrinkwrap又拉回A-pose位置

### 3. Shrinkwrap Mechanism (TECHNICAL)
- `NEAREST_SURFACEPOINT` 找最近表面点，无衣服/身体区分
- Tripo表面有衣服褶皱，最近点可能是衣服而非身体
- 需要语义分割或区域约束

## Lessons Learned

1. **不要在含衣服的AI高模上直接Shrinkwrap包裹** — 必须先分离衣服和身体
2. **MetaHuman是全三角面** — 非quad，UV身体第二通道/头部第一通道
3. **用户手动标记比自动检测可靠** — 16空对象标记工作流可行
4. **旋转逻辑要推导，不要试错** — 用映射关系推导旋转矩阵
5. **先Shrinkwrap躯干再旋转手臂** — 顺序反了旋转会失效

## Recommended Alternatives

| Alternative | Feasibility | Effort | Quality |
|-------------|-------------|--------|---------|
| AI分割衣服/身体后包裹 | 80-85% | 0.5-1天 | 高（<1mm） |
| Surface Deform+手动顶点组 | 90% | 1-2天 | 高 |
| 接受Tripo原始拓扑减面 | 100% | 0.5天 | 中（非MetaHuman拓扑） |
| 混合方法：自动粗对齐+手动精修 | 85% | 1-2天 | 高 |

## Next Steps

1. 用户确认方向：分离衣服/接受手动/放弃MetaHuman拓扑
2. 如分离衣服：调研AI分割方法（80-85%准确率）
3. 如手动：16点空对象标记→Surface Deform包裹
4. 如放弃：Tripo直接减面到20-25万面，进入绑定阶段
