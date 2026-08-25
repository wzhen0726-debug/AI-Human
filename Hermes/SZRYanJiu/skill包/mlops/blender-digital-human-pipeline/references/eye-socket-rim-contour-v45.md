# Eye Socket Rim Contour — v45 半自动标记点工作流

## 背景
3DDFA 眼裂轮廓（26.8×9.7mm 杏仁形，6 点）是"眼裂"（上下眼睑之间的缝），不是"眼窝边界"（眼眶凹陷的完整外缘）。用户实测发现 3DDFA 轮廓偏小偏上，要求改用模型实际贴图眼睛边界。

## 关键发现
- 模型眼睛是**贴图画的**（非几何凹陷），几何上虹膜中心只有 19 个顶点，无真实眼窝折痕
- 因此"实际眼窝边界"= 贴图里画的眼睛轮廓（睫毛根部深色眼睑缘线）
- 从几何提取眼窝边界不可行（径向梯度法抓到的都是噪声）

## 半自动标记点工作流

### 1. 生成标记点模板
脚本：`scripts/place_eyelid_markers.py`
- 只出一边（R 眼，x 正），12 个 Empty 球（2.5mm），show_in_front=True
- 初始位置 = 3DDFA 眼裂加密 12 点（用户只需微调）
- 每个标记点加 Shrinkwrap 约束（NEAREST_SURFACE），拖动时自动吸附模型表面
- 命名：`LM_01_外眼角_outer_canthus_R` 等

### 2. 用户 GUI 调整
- 打开 `models/01A_markers_eyelid.blend`
- 正视图（Numpad 1），拖动 12 个标记点到贴图睫毛根部深色眼睑缘线
- 只调 R 眼（x 正），保存

### 3. 镜像 R→L
脚本：`scripts/mirror_markers.py`
- 镜像公式：L(x, y, z) = (-R_x, R_y, R_z)
- 删除 L 眼旧标记点，创建新镜像标记点（带 Shrinkwrap 约束）

### 4. 读取轮廓
脚本：`scripts/read_eyelid_markers.py`
- **关键修复**：只投影 y 到表面，保留用户打点的 x,z（不改变形状）
- 旧版 bug：KD-tree 投影把 x,z 也改成最近顶点坐标，导致轮廓变形
- 输出：`screenshots/3ddfa/eyelid_contour_manual.json`（结构同 eyelid_contour.json）
- 管线 config 中 `EYELID_CONTOUR_JSON` 指向 manual JSON

## 面朝向修复（v45）
- 诊断：上半部分（z≥中心）有 6.5% 翻转面，集中在 z[1.662,1.675] 倒角带到碗外缘
- 根因：`bmesh.update_edit_mesh` 后 mode 切换 EDIT→OBJECT→EDIT 重新计算 mesh normals，翻转了之前修好的面
- 修复：在 UV 分配后、退出 EDIT 前，加 final flip pass（阈值 `normal.y > 0.05`）
- 同时扩大面朝向检查半径 0.021→0.025（rim 扩大到 10.9mm 后旧半径漏检）

## Fallback 镜像
如果用户想手动镜像（不信任脚本），可以用 Blender 的 Mirror 功能：
1. 选中所有 R 眼标记点
2. 应用 scale 镜像（x: -1）

## 回退到 3DDFA
config 中 `EYELID_CONTOUR_3DDFA_JSON` 保留原始 3DDFA 轮廓路径，可随时切回。