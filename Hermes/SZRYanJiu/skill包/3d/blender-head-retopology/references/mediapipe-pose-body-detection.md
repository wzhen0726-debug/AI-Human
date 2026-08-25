# MediaPipe Pose 全身检测在3D渲染图上的应用

## 概述

MediaPipe Pose（33个关节点）可用于自动检测3D人体模型的关节位置，替代手动打点。但在3D渲染图（非真实照片）上存在系统性偏差，需要标定和校验。

## 检测质量（2026-07-28实测）

### 各视角可用性

| 视角 | 上肢(肩/肘/腕) | 下肢(髋/膝/踝) | 可用性 |
|------|---------------|---------------|--------|
| front(正视) | ✅ vis>0.99 | ✅ vis>0.97 | 全部可用 |
| side_L(左侧) | ❌ vis<0.4 | ❌ vis<0.1 | 失效 |
| side_R(右侧) | ⚠️ 部分可用 | ❌ vis<0.1 | 基本失效 |
| back(背视) | ✅ vis>0.98 | ✅ vis>0.82 | 全部可用 |

**结论**: 只用front+back双视角，侧视图下肢完全失效。

### 上肢检测偏差（系统性）

MediaPipe检测到的上肢位置比实际关节位置**偏外+偏下**：

| 关节 | 实际3D位置 | 实际像素 | MediaPipe像素 | 偏差 |
|------|-----------|---------|--------------|------|
| 左肩 | (-0.199, 0.004, 1.495) | (417, 89) | (597, 256) | (-180, -167) |

**根因**: MediaPipe检测的是人体轮廓上的点（可能包括衣服），不是骨骼关节点。3D渲染图的材质/光照与真实照片不同，T-pose手臂和身体角度在2D图像上不明显。

## 关键陷阱

### 1. left/right 翻转问题

MediaPipe的left/right是从**人的视角**出发的（人面对相机时，人的left在相机的right）。

**必须翻转像素X坐标**:
```python
px = img_size - px  # 1024 - px
```

翻转前：left_shoulder(597,256) → 射线射向X=+0.179（右侧）→ 没命中左肩(X=-0.2)
翻转后：left_shoulder(427,256) → 射线射向X=-0.179（左侧）→ 接近左肩 ✓

### 2. 侧视图下肢完全失效

MediaPipe Pose主要检测正面，侧面关节点置信度极低（visibility < 0.1）。

**后果**: 无法获得Y坐标（前后深度），双视角三角定位只能得到X和Z。

**解决方案**:
- 用front+back双视角获得X和Z
- Y坐标用骨骼辅助（Mixamo髋关节Y坐标参考）
- 或用MediaPipe相对深度z坐标估算前后关系

### 3. 透视相机射线计算

Blender默认50mm透视相机，像素→射线必须考虑焦距：

```python
# 错误（正交假设）:
ray_local = Vector((nx, ny, -1))

# 正确（透视相机）:
fov = 2 * math.atan(sensor_width / (2 * lens))  # 39.6°
tan_half_fov = math.tan(fov / 2)
aspect = sensor_height / sensor_width  # 24/36
ray_local = Vector((nx * tan_half_fov, ny * tan_half_fov * aspect, -1))
```

### 4. 上肢检测不可靠

上肢（肩/肘/腕）在front+back双视角下**全部FAILED**（0/6命中），因为：
- 检测位置偏差大（180px/167px）
- 射线射向空旷区域或错误表面

**下肢成功**（6/6命中），因为下肢检测位置相对准确。

## 推荐工作流

```
1. MediaPipe Pose检测（front+back双视角）
   - 下肢（髋/膝/踝）：可用，直接投影
   - 上肢（肩/肘/腕）：不可靠，需要骨骼辅助校验

2. 骨骼辅助校验
   - 用Mixamo骨骼位置验证MediaPipe检测的关节位置
   - 偏差>5cm时用骨骼位置替代

3. 2D→3D投影
   - front+back双视角三角定位（X和Z）
   - Y坐标用骨骼辅助或相对深度估算

4. RBF+ARAP变形
   - 用校验后的landmark做RBF粗对齐
   - 用ARAP刚性修正消除膨胀
```

## 与面部检测（test01）的对比

| 维度 | 面部（Face Landmarker） | 身体（Pose） |
|------|------------------------|-------------|
| 点数 | 478 | 33 |
| 精度 | 0.4mm | 偏差180px（需标定） |
| 可靠性 | 高（凸面+密集点） | 中（衣服+稀疏点） |
| 侧面检测 | 部分可用 | 完全失效 |
| 衣服干扰 | 无 | 严重 |

## 模型文件

- `pose_landmarker.task`（29.2MB）：MediaPipe Pose Landmarker模型
- 下载地址：https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task

## 33个关节点索引

```
0: nose
1-6: left/right eye (inner/outer/center)
7-8: left/right ear
9-10: mouth left/right
11: left_shoulder    12: right_shoulder
13: left_elbow       14: right_elbow
15: left_wrist       16: right_wrist
17-22: left/right pinky/index/thumb
23: left_hip         24: right_hip
25: left_knee        26: right_knee
27: left_ankle       28: right_ankle
29-32: left/right heel/foot_index
```

## 打包建议

- MediaPipe Pose模型（29.2MB）+ mediapipe库（~50MB）= ~80MB
- 可接受，比PyTorch方案（~2GB）轻量得多
- 无需GPU，CPU即可运行
