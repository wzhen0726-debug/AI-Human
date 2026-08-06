# 01A 眼窝与眼球

> 状态：眼窝 ✅ 已交付；眼球摆入 ⚠️ 参数未定案（详见 `方案md记录/v3_QuadRemesher/01A眼窝与眼球/问题分析_眼球摆入.md`）

## 位置
01高模修复之后、02 QR之前。眼窝在高模上做（QR会把洞口边缘重拓扑成干净quad边界环），眼球是独立物体不进QR/UV/烘焙。

## 功能

### 眼窝制作（run_eye_socket.py）
- 自动检测虹膜中心（贴图暗像素法，双眼各500+暗像素顶点，质心稳定）
- 按眼裂尺寸开孔（26×18mm椭圆，双眼各删 ~700 面）
- 压凹成窝（半径15mm、最深10mm、cosine平滑衰减）
- 验证：中心区残留顶点=0（完全打穿）

### 眼球摆入（run_eyeball.py）
- 导入 eye_01.glb，按x坐标拆左右眼（GLB命名与位置相反，按位置分配）
- 摆入眼窝：球心=开口中心沿全局前向(-Y)内缩 `EYE_PUSH_IN`；朝向=局部+Z(瞳孔)对准全局-Y（平视）
- 强制贴图显示（Image Texture直连Base Color）
- 渲染正面/侧面/特写验证图

## 输入
- `01高模修复与黏连检测/models/01_highpoly_repair.blend`
- `原始模型/Metahuman低模/眼睛模型001/eye_01.glb`（双眼各802顶点/1536面，直径约29mm，自带1024贴图）

## 输出
- `models/01_1_eye_socket.blend`（含双眼窝，供02 QR读取）
- `models/01_2_eyeball_placed.blend`（含眼球，⚠️ 参数未定案，仅供对照）
- `screenshots/` 各阶段验证截图

## 参数

| 参数 | 值 | 说明 |
|---|---|---|
| 开孔 | 26×18mm 椭圆 | 略小于眼裂31.5mm，让眼睑压住眼球 |
| 压凹 | 半径15mm，最深10mm | cosine平滑衰减 |
| EYE_SCALE | 1.0 | 眼球缩放，先不缩，渲染定夺，备0.85-0.9 |
| EYE_PUSH_IN | 0.022（22mm） | ⚠️ 未定案，视觉验证结果矛盾 |
| PUPIL_LOCAL_DIR | (0, -0.04, 0.997) | 瞳孔=局部+Z，实测 |

## 运行
```bash
cd scripts
# 眼窝
"D:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --python run_eye_socket.py
# 眼球摆入
"D:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --python run_eyeball.py
```

## 附：3DDFA-V3 调研结论（2026-08-04）

**结论：当前不需要，留作后备。**

3DDFA-V3（CVPR2024 Highlight）：单张照片 → BFM人脸网格 + 关键点 + 8部件语义分割（含眼睛区域mask）。

| 判断维度 | 结论 |
|---|---|
| 能否用于眼部定位 | 能（眼睛区域分割/关键点是其核心输出） |
| 本管线是否需要 | 不需要。输入是3D高模不是照片，贴图上有画好的眼睛，轻量方法已实测成功 |
| 后备价值 | 若未来模型是纯素模（贴图没画眼睛），可用3DDFA-V3：渲染正脸图→2D眼部landmarks→射线反投影回网格。此路线写入方案但不进当前管线 |
| 部署成本 | 较重：conda + PyTorch + nvdiffrast + 预训练权重。零预算下能不用就不用 |

完整设计依据见 `方案md记录/v3_QuadRemesher/01A眼窝与眼球/眼窝与眼球集成设计方案.md`。
