# 01_1 眼窝制作

## 位置
01高模修复之后、02 QR之前。

## 功能
- 自动检测虹膜中心（贴图暗像素法）
- 按眼裂尺寸开孔（26×18mm椭圆）
- 压凹成窝（最深10mm，平滑衰减）
- 清理边界环

## 输入
- `01高模修复与黏连检测/models/01_highpoly_repair.blend`

## 输出
- `models/01_1_eye_socket.blend`（含双眼窝，供02 QR读取）

## 参数
- 虹膜中心：自动检测（贴图暗像素8%）
- 开孔：宽26mm × 高18mm 椭圆
- 压凹：半径15mm，最深10mm
- 方向：+Y（往头内）

## 运行
```bash
cd scripts
"D:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --python run_eye_socket.py
```

## 验证
- `screenshots/01_1_face_front.png`：正面特写
- `screenshots/01_1_face_side.png`：侧面特写
- 中心区顶点数应为0（完全打穿）

## 注意
- 运行前会覆盖 `01_highpoly_repair.blend`，建议先备份
- 右眼洞内偏浅灰是光线角度，脚本已验证完全贯穿

## 附：3DDFA-V3 调研结论（2026-08-04，用户指定调研项）

**结论：当前不需要，留作后备。**

3DDFA-V3（CVPR2024 Highlight，官方实现 github.com/wang-zidu/3DDFA-V3）：单张照片 → BFM人脸网格（35,709顶点）+ 68/106/134关键点 + 8部件语义分割（含眼睛区域mask）。

| 判断维度 | 结论 |
|---|---|
| 能否用于眼部定位 | 能（眼睛区域分割/关键点是其核心输出之一） |
| 本管线是否需要 | 不需要。输入是3D高模不是照片，且贴图上有画好的眼睛，"UV采样贴图亮度→暗像素聚类→质心"的轻量方法已实测成功（双眼各500+暗像素顶点，质心稳定），本步骤的 `iris_detect.py` 即此方法 |
| 后备价值 | 若未来模型是纯素模（贴图没画眼睛），自动定位会失败，此时可用3DDFA-V3：渲染高模正脸图→2D眼部landmarks/分割→射线反投影回网格得眼区。此路线写入方案但不进当前管线 |
| 部署成本 | 较重：conda + PyTorch + nvdiffrast(或cython CPU渲染器) + 预训练权重下载。零预算下能不用就不用 |

完整设计依据见 `方案md记录/v3_QuadRemesher/08眼窝与眼球集成/眼窝与眼球集成设计方案.md` 第二章。
