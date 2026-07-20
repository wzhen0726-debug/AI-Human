# 头部贴合自动化管线

MediaPipe 面部识别 + MetaHuman 模板 → Shrinkwrap 包裹 + 拉普拉斯锚定

---

## 目录结构

```
E:/WangZhen_Project/AI/ShuZiRen/Zed/ShiJueShiBieMesh/
├── 原始GLB/
│   ├── 人头对齐_个人使用勿动.blend   # 扫描人头（含 Scan_Head 对象）
│   ├── MetaHuman_head/
│   │   ├── MH_Head_01.obj            # MetaHuman 头部模板
│   │   ├── MH_Head_01.mtl
│   │   └── MH_Head.glb               # 原始 GLB（备用）
│   └── Scan_head/
│       └── Scan_Head.glb             # 原始扫描 GLB（备用）
│
├── scripts/
│   ├── mp_v2_final.py                # ★ 主管线脚本（当前使用）
│   ├── detect_template_landmarks.py  # 模板特征点自动检测
│   ├── create_template.py            # 创建模板文件供手动打点
│   ├── verify_final.py               # 验证输出质量
│   ├── pipeline.py                   # 旧管线（Tripo 身体绑定）
│   └── deprecated/                   # 废弃的测试脚本
│
├── docs/
│   └── workflow.md                   # ★ 本文档
│
└── output_final/
    ├── head_mp_final.blend           # ★ 最终输出
    ├── template_landmarks.json       # 模板特征点索引（21 个顶点）
    ├── face_landmarker.task          # MediaPipe 模型文件
    └── mp_*.png                      # 6 方向渲染图（调试用）
```

---

## 整体流程

```
扫描人头 (.blend)
    │
    ▼
[1] 加载场景 + 6 方向渲染
    │  渲染 ±X, ±Y, ±Z 6张 512×512 PNG
    │
    ▼
[2] MediaPipe 面部检测
    │  对每张渲染图运行 Face Landmarker
    │  选出 landmark 数量最多的方向（最佳视角）
    │
    ▼
[3] 2D → 3D 映射
    │  12 个面部特征点：通过相机射线 → 扫描表面
    │  8 个几何估算点：耳朵 / 后脑 / 头顶 / 后颈（射线估算）
    │
    ▼
[4] 导入模板 + 初始对齐
    │  导入 MH_Head_01.obj
    │  旋转模板匹配扫描朝向（90° X）
    │  质心对齐（仅用 12 个面部点）
    │  统一缩放
    │
    ▼
[5a] Shrinkwrap 包裹（4 轮）
    │  轮 1-2: NEAREST_SURFACEPOINT
    │  轮 3-4: PROJECT（全轴全方向）
    │  每轮后跟 Corrective Smooth
    │
    ▼
[5b] 特征点锚定（20 轮迭代）
    │  12 个面部特征点拉向 MediaPipe 3D 目标
    │  带阻尼的渐进位移
    │  拉普拉斯邻域平滑（仅非锚点区域）
    │
    ▼
[5c] 表面修正
    │  1 轮轻量 Shrinkwrap 修正
    │  重新拉回锚点
    │
    ▼
[6] 质量验证
    │  特征点偏差（目标 < 1mm）
    │  整体表面距离（目标 < 1mm / >99%）
    │
    ▼
[7] 保存 head_mp_final.blend
```

---

## 管线详解

### 1. 加载场景 + 6 方向渲染

**输入**：`人头对齐_个人使用勿动.blend`（包含 `Scan_Head` 对象）

**处理**：
- 打开 blend 文件，获取 `Scan_Head` 网格
- 计算扫描模型的包围盒，确定中心点和尺寸
- 在 6 个方向（±X, ±Y, ±Z）各放置摄像机，距离 = max(包围盒尺寸) + 0.5m
- 每个方向渲染 512×512 PNG（BLENDER_WORKBENCH 引擎）
- 添加 Sun Light（强度 5.0）确保面部光照

**关键参数**：
- 渲染分辨率：512 × 512
- 渲染引擎：`BLENDER_WORKBENCH`（速度快，无需材质）
- 光照：SUN，强度 5.0

### 2. MediaPipe 面部检测

**模型**：`face_landmarker.task`（MediaPipe Face Landmarker）

**处理**：
- 将每张 512×512 渲染图 resize 到 256×256
- BGR → RGB 转换
- 对每张图运行 Face Landmarker（478 个 landmarks）
- 选出 landmark 数量最多的视角（通常是人脸正对的视角）

**选择策略**：因为扫描模型只在正脸方向有面部几何，所以只有人脸的视角才能被 MediaPipe 检测到。程序从 6 个方向中找到含面部 landmark 最多的一帧。

### 3. 2D → 3D 映射

#### 3a. 面部特征点（MediaPipe）

使用透视投影逆变换将 2D landmark 映射到 3D 扫描表面：

```
NDC 坐标:
  nx, ny = (px/w)*2-1, 1-(py/h)*2

相机空间射线:
  ray_cam = (nx × tan(fov/2), ny × tan(fov/2), -1)

世界空间射线:
  ray_world = camera_matrix_3x3 @ ray_cam

扫描本地空间（对象坐标）:
  origin_local = scan_matrix⁻¹ @ camera_position
  dir_local = scan_matrix⁻¹ @ ray_world

射线检测:
  hit, location = scan_obj.ray_cast(origin_local, dir_local)
  → 命中点 = scan_matrix @ location（世界坐标）
```

**12 个 MediaPipe 特征点**：

| 特征点 | MediaPipe 索引 | 对应模板索引 |
|--------|---------------|-------------|
| nose_tip | 1 | 7883 |
| right_eye_inner | 133 | 4395 |
| right_eye_outer | 33 | 7219 |
| left_eye_inner | 362 | 2791 |
| left_eye_outer | 263 | 2772 |
| right_mouth_corner | 61 | 6600 |
| left_mouth_corner | 291 | 2299 |
| chin | 199 | 8023 |
| forehead | 10 | 7694 |
| nose_bridge | 6 | 7878 |
| right_brow | 105 | 4274 |
| left_brow | 334 | 72 |

**重要**：MediaPipe 的 `left`/`right` 命名是从 **图像视角** 定义的（镜像），而非从人的解剖学视角。所以：
- MediaPipe idx 33 → 图像左侧 → 人物右眼 → 对应模板 `right_eye_outer`
- MediaPipe idx 263 → 图像右侧 → 人物左眼 → 对应模板 `left_eye_outer`

#### 3b. 几何估算点（射线估算）

8 个非面部特征点通过几何射线估算，精度较低（通常偏差 50-200mm），**不参与对齐和锚定，仅用于验证**：

```
左耳 (+X 侧): origin=(+0.3, eye_y+0.06, eye_z+offset), dir=(-1,0,0)
右耳 (-X 侧): origin=(-0.3, eye_y+0.06, eye_z+offset), dir=(+1,0,0)
后脑:         origin=(0, 0.3, eye_z), dir=(0,-1,0)
头顶:         origin=(0, 0, 3.0), dir=(0,0,-1)
后颈:         origin=(0, 0.3, min_z), dir=(0,-1,0)
```

### 4. 导入模板 + 初始对齐

**模板**：`MH_Head_01.obj`（MetaHuman 标准头部，约 25K 顶点，纯四边形）

#### 4a. 旋转

模板的顶点坐标直接在数据层被旋转：
```python
for v in template.vertices:
    v.co = Matrix.Rotation(scan_obj.rotation_euler.x, 3, 'X') @ v.co
```
扫描对象通常有 90° X 旋转，模板同样应用 90° X 旋转使其朝向一致。

#### 4b. 质心对齐（仅面部点）

仅使用 12 个可靠的 MediaPipe 面部点计算质心偏移：

```python
模板面部点质心 = mean(模板.vertices[face_indices])
扫描面部点质心 = mean(扫描_3d_landmarks[face_names])
偏移 = 扫描质心 - 模板质心
模板.location += 偏移
```

> 几何估算点（耳朵、后脑等）不参与质心计算，避免其大误差拖偏对齐。

#### 4c. 统一缩放

```python
bbox_ratio = scan_bbox_size / template_bbox_size  # 3 轴分别计算
uniform_scale = mean(bbox_ratio)  # 取平均，保持均匀缩放
template.scale = (us, us, us)
```

### 5a. Shrinkwrap 包裹（4 轮）

| 轮次 | 包裹方式 | 说明 |
|------|---------|------|
| 1 | NEAREST_SURFACEPOINT | 最近点包裹 |
| 2 | NEAREST_SURFACEPOINT | 再次最近点包裹 |
| 3 | PROJECT (全向) | 从 6 个方向投影包裹 |
| 4 | PROJECT (全向) | 再次全向投影包裹 |

每轮包裹后跟一次 Corrective Smooth（2 次迭代，因子 0.15）以防止顶点撕裂。

### 5b. 特征点锚定（20 轮迭代）

这是管线中最关键的一步，解决了 Shrinkwrap 无法保证具体顶点对位的问题。

**算法**：迭代位移 + 拉普拉斯平滑

```
for 迭代 in range(20):
    alpha = 0.3 + 0.7 × (迭代/19)  # 渐进增加位移量

    # 步骤 1: 锚点位移（仅面部 12 点）
    for 每个锚点:
        锚点.co = lerp(当前坐标, 目标坐标, alpha)

    # 步骤 2: 非锚点平滑（拉普拉斯平滑）
    for 每个非锚点顶点:
        邻域平均 = mean(所有邻居坐标)
        新坐标 = lerp(当前坐标, 邻域平均, 0.3)
```

- **锚点**：12 个面部特征点，目标位置来自 MediaPipe 3D 映射
- **阻尼**：前几轮 α 小（0.3），防止初始位移过大撕裂网格；后几轮 α 大（1.0），精确到位
- **平滑**：每次迭代对非锚点顶点做拉普拉斯平滑，保持表面光滑

**收敛情况**：通常在 10 轮内 12 个锚点全部收敛至 0.0mm 误差。

### 5c. 表面修正

锚定完成后，可能产生细微表面偏差。再做一次轻量修正：
- 1 轮 NEAREST_SURFACEPOINT Shrinkwrap
- 1 轮 Corrective Smooth（1 次迭代，因子 0.1）
- 重新拉回锚点到目标位置

### 6. 质量验证

**特征点验证**（仅面部 12 点）：
```
nose_tip: 0.0mm    left_eye_inner: 0.0mm    ...
```

**整体表面验证**（KD 树最近邻）：
```
mean=0.265mm   <1mm: 99.7%
```
对模板的每个顶点，在扫描表面 KD 树中查找最近点距离。均值 < 1mm 为合格。

### 7. 保存

输出 `head_mp_final.blend`，包含：
- `Scan_Head`：原始扫描网格
- 模板对象：贴合后的 MetaHuman 头部（无材质）

---

## 质量指标

| 指标 | 目标值 | 最终实测 |
|------|--------|---------|
| 面部特征点偏差（12 点） | < 1mm | **0.0mm** |
| 整体表面偏差（均值） | < 1mm | **0.265mm** |
| 整体表面偏差（< 1mm 占比）| > 99% | **99.7%** |
| 耳朵 / 后脑几何点偏差 | - 仅供参考 | 50-200mm |

---

## 运行命令

```powershell
& "D:\Program Files\Blender Foundation\Blender 5.1\blender.exe" `
  --background `
  --python "E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\scripts\mp_v2_final.py"
```

**运行时间**：约 4-5 分钟（含 6 次渲染 + MediaPipe 检测 + 4 轮 Shrinkwrap + 20 轮锚定 + 验证）

---

## 关键参数

| 参数 | 值 | 位置 | 说明 |
|------|---|------|------|
| 渲染分辨率 | 512×512 | Line 39-40 | 越大越精确但越慢 |
| MediaPipe 分辨率 | 256×256 | Line 71 | 模型固定输入 |
| Shrinkwrap 轮数 | 4 轮 | Line 226 | 2 NEAREST + 2 PROJECT |
| 锚定迭代次数 | 20 轮 | Line 259 | 通常 10 轮即收敛 |
| 锚定阻尼初始值 | 0.3 | Line 261 | 防止初始撕裂 |
| 拉普拉斯平滑因子 | 0.3 | Line 278 | 控制平滑强度 |
| Corrective Smooth | 2 次 / 0.15 | Line 236 | Shrinkwrap 后修复 |
| 表面修正平滑 | 1 次 / 0.1 | Line 306 | 最终轻量修正 |

---

## Bug 修复记录

### Bug 1: 左右镜像（mp_indices 映射错误）

**问题**：MediaPipe 命名使用图像视角（`left` 在图像左侧 = 人物右侧），但脚本将其映射为模板的解剖学 `left` 顶点（在 +X 侧），导致模板左右眼拉到扫描的对侧。

**修复**：交换所有 left/right 索引——MediaPipe idx 33 → `right_eye_outer`，idx 263 → `left_eye_outer`（同上交换 eyes/mouth/brow）。

**影响**：修复前特征点偏差 60-130mm，修复后全部 0.0mm。

### Bug 2: 质心对齐混入不可靠几何点

**问题**：质心对齐将 8 个几何估算点（耳朵/后脑/头顶/后颈）与 12 个面部点一起计算均值。几何点误差 50-200mm，拖偏质心。

**修复**：质心对齐仅使用 12 个 MediaPipe 面部点（`t_idx_face`）。几何点仅用于验证。

**影响**：修复前初始对齐偏差约 100mm，修复后精准对齐。

### Bug 3: 无特征点锚定

**问题**：Shrinkwrap 仅做"最近点包裹"，不保证具体顶点位置。嘴角顶点可能滑到脸颊，眼点错位。

**修复**：增加 20 轮迭代位移 + 拉普拉斯平滑锚定步骤。

**影响**：修复前面部特征点偏差 60-180mm，修复后全部 0.0mm。

---

## 坐标系约定

- **扫描模型**：`Scan_Head` 在 blend 中有 `rotation_euler.x = 90°`。旋转后，面部朝向 -Y，头顶指向 +Z。
- **模板模型**：`MH_Head_01.obj` 原始朝向 +Z（或 +Y）。代码施加 90° X 旋转使其与扫描对齐。
- **MediaPipe 图像坐标**：(0,0) = 左上角，x 向右，y 向下。
- **NDC 坐标**：x = [-1, +1] 左→右，y = [-1, +1] 下→上（y 翻转后）。
- **Blender 世界坐标**：Z 为上，Y 为前/后，X 为左/右。

---

## 依赖环境

### Blender
- 版本：5.1
- 路径：`D:\Program Files\Blender Foundation\Blender 5.1\blender.exe`

### Python 包（Blender 内置 Python）
- `numpy`（数学计算）
- `mathutils`（向量/矩阵，Blender 内置）
- `opencv-python (cv2)`（图像处理）
- `mediapipe`（面部 landmark 检测）

### 文件依赖
- `face_landmarker.task`：MediaPipe Face Landmarker 模型（需提前下载放到 output_final/）
- `template_landmarks.json`：模板特征点索引文件（由 `detect_template_landmarks.py` 生成）

---

## 模板特征点管理

模板特征点文件 `output_final/template_landmarks.json` 存储了 21 个关键顶点在 MH_Head_01.obj 中的索引号。

**生成方式**：
1. 运行 `detect_template_landmarks.py`（自动检测，精度一般）
2. 在 Blender 中手动打开 `template_clean.blend`，确认/修正每个顶点
3. 导出 JSON

**21 个特征点**：
- 面部（12 个）：nose_tip, left/right_eye_inner/outer, left/right_mouth_corner, chin, forehead, nose_bridge, left/right_brow
- 头部（9 个）：top_of_head, left/right_ear_top/mid/bottom, back_of_head, back_neck

---

## 后续人工检查项

1. 在 Blender 中打开 `head_mp_final.blend`
2. 检查眼、鼻、嘴位置是否对齐（已验证 0.0mm 偏差，但仍需肉眼确认）
3. 检查耳朵区域是否有明显穿透或扭曲
4. 检查后脑贴合是否自然
5. 如需导出 GLB/FBX，可在 Blender 中手动导出

---

## 已知限制

1. **几何估算点不准**：耳朵/后脑/头顶/后颈通过射线估算，偏差 50-200mm。这些点仅用于验证，不影响实际输出。
2. **仅支持正面面部**：MediaPipe 只能检测正面人脸。如果扫描头部含完整头部几何但没有正面面部，管线将失败。
3. **模板拓扑固定**：使用 MetaHuman 标准头部拓扑。如果扫描头部与标准头部比例差异过大（如幼儿、非人），贴合效果会下降。
4. **无材质处理**：输出 blend 不含材质信息，模板使用默认材质。
5. **单线程渲染**：6 张渲染图串行生成，占整个管线的约 1 分钟。
