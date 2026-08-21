# 01A 眼窝与眼球

> 状态：眼窝 ✅ v48 内圆角定案（用户满意）；眼球摆入 ✅ v3e 定案（解剖参考点定位，vision 四项验收通过）；颜色面板 ✅ 常驻插件已启用

## 位置
01高模修复之后、02 QR之前。眼窝在高模上做（QR会把洞口边缘重拓扑成干净quad边界环），眼球是独立物体不进QR/UV/烘焙。

## 快速使用（给不懂建模的人）

### 换眼睛颜色（3步）
1. 打开 `models/01_2_eyeball_placed.blend`
2. 3D视图按 **N** 键 → 侧边栏选 **"眼睛颜色"** 标签
3. 选 **虹膜颜色**（蓝/棕/绿/榛/红/紫/丧尸）+ **血丝程度**（无/中/重）→ 点 **"应用眼睛颜色"** → Ctrl+S 保存

（插件已装为常驻 addon `eye_color_panel`，打开任何 blend 都可用；命令行版：`blender -b 文件.blend --python set_eye_color.py -- 棕色 中`）

### 重新摆眼球（换眼睛模型后）
改 `scripts/eye002_config.py` 后跑 `run_eyeball_v2.py`。摆位按解剖规律自动算（换模型自动适配）：
- **规律1·深度**：角膜顶点与眼睑开口平面共面（凸出量 `EYE_PROTRUSION_MM`=0.1mm）
- **规律2·高度**：虹膜底缘贴下眼睑缘（高度偏移 `EYE_Z_OFFSET_MM`=1.4mm）
- **规律3·左右**：x=眼裂轮廓中心，两眼同一偏移天然同步

不满意可在 GUI 微调：3D视图按 **N** → **"眼球位置"** 标签 → 拖滑块（前后/上下/左右，左右眼同步）→ **"保存到管线"**（写入 `eyeball_finetune_manual.json`，以后重跑自动用）。

## 功能

### 眼窝制作（run_eye_socket.py，v48 inward_fillet 定案）
- 眼裂轮廓：用户 Blender GUI 半自动标记12点/眼 → Shrinkwrap吸附 → 镜像到另一只眼（`screenshots/3ddfa/eyelid_contour_manual.json`）
- 开孔+封碗+内圆角：`SOCKET_VARIANT="inward_fillet"`（只内收1.2mm+下沉0.6mm无外扩 → 无M形凸脊、接缝平滑）
- 验证：`check_integrity_local.py`（KD-tree 0.01mm重复点判定/边界边/非流形/极点扇全绿）

### 眼球摆入（run_eyeball_v2.py，v4 解剖规律定位 + 半自动微调）
- 眼睛模型002（Eye_Iris+Eye_Sclera+Eye_Shadow，append后join单对象、删父empty）
- 摆位规律（用户GUI手动微调反推，v4复现与手动位置完全一致）：
  - 深度：角膜顶点与眼睑开口平面共面（凸出0.1mm）
  - 高度：虹膜底缘贴下眼睑缘（002=开口中心上+1.4mm，上睑自然盖虹膜顶1.5mm）
  - 左右：x=轮廓中心，两眼同一偏移天然同步
- 角膜距自动测量（002实测15.31mm），换模型不用手写参数
- GUI微调面板：N面板"眼球位置"标签，滑块微调左右同步，可"保存到管线"
- 自动上色（按 EYE_COLOR/EYE_BLOODLINE）+ 验证渲染（正面/特写）

## 输入
- `01高模修复与黏连检测/models/01_highpoly_repair.blend`
- `原始模型/Metahuman低模/眼睛模型002/Eye.blend` + `Textures/`（7色系×血丝等级，19个颜色变体）
- `screenshots/3ddfa/eyelid_contour_manual.json`（用户手动标记眼裂轮廓，眼窝与眼球共用基准）

## 输出
- `models/01_1_eye_socket.blend`（v48眼窝，供02 QR读取；备份 `_v48_final.blend`、两方案对比版）
- `models/01_2_eyeball_placed.blend`（v3e眼球，榛色/无血丝）
- `screenshots/` 各阶段验证截图（`01_2_eye002_front.png` 为v3e验收图）

## 运行
```bash
cd scripts
# 眼窝(v48)
"D:/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b --python run_eye_socket.py
# 眼球摆入(v3e)
"D:/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b --python run_eyeball_v2.py
# 命令行换色
"D:/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b ../models/01_2_eyeball_placed.blend --python set_eye_color.py -- 棕色 中
```

## 主要脚本
| 脚本 | 作用 |
|---|---|
| `run_eye_socket.py` + `socket_ops.py` + `eye_socket_config.py` | 眼窝管线（开孔/封碗/内圆角/法线） |
| `run_eyeball_v2.py` + `eye002_config.py` | 眼球摆入（v3解剖定位+自动上色） |
| `set_eye_color.py` / `switch_eyeball_color.py` | 换色（N面板+命令行 / 管线内） |
| `eye_color_panel_addon.py` | 常驻中文颜色面板插件（已安装启用） |
| `eye002_make_registry.py` → `eye002_colors.json` | 扫描Textures生成颜色注册表 |
| `place_eyelid_markers.py` / `mirror_markers.py` / `read_eyelid_markers.py` | 眼裂轮廓半自动标记 |
| `check_integrity_local.py` / `check_eyeball_fit.py` | 完整性/适配检查 |
| `render_clay_eye.py` / `render_wireframe.py` | 素模/线框验证渲染 |

完整过程记录（含所有坑与迭代）：`01A眼窝与眼球_技术方案详细记录.md`（第1-20章）。

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
