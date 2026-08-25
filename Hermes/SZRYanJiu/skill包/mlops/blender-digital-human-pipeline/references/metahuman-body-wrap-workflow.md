# MetaHuman Body Wrap Workflow

> 2026-07-27 test02 session: MetaHuman Body (32K verts) wrapped onto Tripo T-pose (1.1M verts)

## 一、输入资产

| 资产 | 路径 | 顶点 | 面 | 备注 |
|------|------|------|-----|------|
| Tripo T-pose 高模 | `原始模型/AI生成高模/02_tripoTpose/raw_model.glb` | 1,137,322 | ~1,930,148 | 最精致，含衣服 |
| MetaHuman Body | `原始模型/Metahuman低模/Metahuman_Low_01.blend` | 32,334 | 60,816 | A-pose，无骨骼 |
| MetaHuman Head | 同上 | 24,414 | 48,004 | 独立网格 |
| MetaHuman Face | 同上 | 10,243 | 16,090 | 眼睛/牙齿 |

## 二、坐标系统一（关键）

### 问题
- Tripo 旋转后： X=厚度(0.31m), Y=深度(1.79m 含T-pose手臂), Z=身高(1.80m)
- MetaHuman 原始： X=肩宽(1.159m), Y=深度(0.426m), Z=身高(1.496m)
- **X/Y 轴定义互换**

### 统一方案
1. MetaHuman 绕 Z 轴 **-90°** 旋转 (x→-y, y→x)，使 X=厚度、Y=深度
2. 缩放 MetaHuman Z 轴到 Tripo 身高 (1.8m)
3. 中心对齐 + 底部对齐（脚接地）

### 验证
- 对齐后 MetaHuman Z 范围： [-0.002, 1.798] ≈ Tripo [0.000, 1.800]
- 缩放因子： 1.203

## 三、特征点检测（拓扑分析法）

### 失败方案（不要重复）
- **比例估算**：肘在 62% 身高、腕在 42% 身高 —— A-pose 模型误差 30-50cm
- **X 阈值分类**：X>0.4 找右臂 —— 遗漏上臂顶点（Y>1.3 为 0）

### 成功方案：凹陷度+分层检测
```python
# 1. 计算每个顶点的凹陷度（法线方向与邻居平均位置的点积）
# 2. 按 Z 轴分层（踝/膝/髋/肩/肘/腕/骨盆/胸/颈）
# 3. 每层找凹陷度最高的点（关节窝）
# 4. 左右对称检测（镜像验证）
```

**结果**: 14 个特征点（缺 knee_r），但左右不对称（dX 最大 0.24）

### 发现：MetaHuman 有轻微不对称
- 左右脚踝 Y 坐标差异 0.351m
- 左右肘部 Y 坐标差异 0.706m（右肘检测错误）
- 左右肩部 X 坐标差异 0.108m

## 四、包裹流程（修正后）

### 错误流程（v1）
1. 旋转手臂到 T-pose
2. Shrinkwrap 全身
3. **结果**: Shrinkwrap 将手臂拉回身体，T-pose 失效（X 范围 1.182→0.273）

### 正确流程（v3）
1. **只 Shrinkwrap 躯干**（顶点组限制，不含手臂）
2. **旋转手臂到 T-pose**（不再 Shrinkwrap 手臂）
3. 导出

**关键**: 手臂旋转后**不再** Shrinkwrap，否则被拉回

### 手臂顶点分类（距离法）
```python
# 基于到肩膀的距离分类（<0.5m）
# 左肩: (center_x - 0.15, 0, shoulder_z)
# 右肩: (center_x + 0.15, 0, shoulder_z)
# 左臂: 到左肩距离 < 到右肩距离 且 < 0.5m
# 右臂: 到右肩距离 < 到左肩距离 且 < 0.5m
```

**结果**: 左臂 6,387 顶点， 右臂 1,637 顶点（分类不均，部分手臂顶点被分到躯干）

## 五、结果

### 精度
| 指标 | 值 |
|------|-----|
| 平均距离 | 2.06mm |
| <1mm | 17.8% |
| <2mm | 51.0% |
| 最大距离 | 7.55mm |

### 尺寸
- X （肩宽）: 0.761m
- Y （身高）: 1.791m
- Z （深度）: 1.603m

### T-pose 验证
- 左臂 Y 范围： 1.314~1.795 （肘部到肩膀）
- 右臂 Y 范围： 0.791~1.747 （手腕到肩膀）
- 肩宽 (Y=1.5m): 0.761m

### UV
- 1 个 UV 层： DiffuseUV
- U 范围： 1.010~1.990 （MetaHuman 第二通道）
- V 范围： 0.007~0.994

## 六、关键教训

1. **衣服干扰是主要瓶颈**，不是姿势差异。T-pose 旋转没有提升精度（2.01mm→2.06mm）。
2. **Shrinkwrap 顺序很重要**：先包裹躯干，再旋转手臂，不要反过来。
3. **特征点自动检测在 A-pose 上不可靠**，比例估算完全失效。
4. **MetaHuman 有轻微不对称**，左右特征点位置差异大。
5. **手臂分类用距离法**，X 阈值会遗漏上臂。
6. **接受 2mm 精度**，对于绑定和动画已足够，后期在绑定阶段精修。

## 七、Shrinkwrap/RBF 全部失败记录（2026-07-28 test02）

**所有7种方法均失败**，详见 `references/body-wrap-method-comparison.md`。

| 方法 | 结果 | 根因 |
|------|------|------|
| 直接Shrinkwrap(NEAREST) | X span 0.26m, 崩溃 | A-pose手臂拉到躯干衣服表面 |
| 先旋转手臂再Shrinkwrap | X span 0.94m, 变形 | 距离阈值0.6m太小, 手没被捕获 |
| 顶点组限制Shrinkwrap只影响躯干 | Y span压扁0.31m | NEAREST把躯干拉向最近表面 |
| RBF TPS | landmark<30mm✓, 躯干膨胀❌ | 控制点稀疏, 中间区域鼓起 |
| RBF 高斯核 | 同TPS | 不同核函数膨胀程度类似 |
| 锚点迭代平滑 | 未验证(依赖已有wrap) | 最后仍用Shrinkwrap |
| 估算特征点对齐 | 位置不准 | 用T-pose位置标A-pose模型 |

**结论**: Shrinkwrap只做包裹不做变形, RBF只做变形不保持局部刚性。行业标准是多步骤组合: RBF粗对齐→ARAP刚性修正→Surface Deform贴合。详见 `references/body-wrap-method-comparison.md`。

## 七、文件清单

| 文件 | 说明 |
|------|------|
| `aligned_scene.blend` | 坐标系统一后的场景 |
| `vertex_groups.blend` | 手臂/躯干顶点组分类 |
| `wrapped_torso_tpose_arms_v2.blend` | 最终包裹结果 |
| `body_landmarks_final.json` | 14 个特征点 |
| `wrapped_metahuman_v2.glb` | 导出 GLB (4.0MB) |
| `wrapped_metahuman.fbx` | 导出 FBX (1.9MB) |
