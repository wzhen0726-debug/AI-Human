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
- **不要给标记 Empty 加 Shrinkwrap 约束** —— 约束每帧把点硬拉回表面，用户手动拖动的调整会弹回、无法离开表面调深度。改用场景级**原生面捕捉**：`tool_settings.use_snap=True` + `snap_elements={'FACE'}`（只在拖动时按需吸附，不跟手打架）
- snap 设置要防御式写：Blender 5.x 删了 `use_project`，`snap_elements` 旧版叫 `snap_elements_base` —— 全部 `hasattr`/try-except 包住
- 命名：`LM_01_外眼角_outer_canthus_R` 等

### 2. 用户 GUI 调整
- 控制台用 `blender <markers.blend> --python setup_marker_gui.py` 打开 GUI，setup 脚本自动：①正交前视图对准标记区（按 12 点 bbox 算中心和 ortho_scale，不硬编码坐标）②`shading.type='MATERIAL'` 显示纹理 ③兜底开启面捕捉。headless 下无 VIEW_3D 区域，脚本要静默跳过不报错
- 拖动 12 个标记点到贴图睫毛根部深色眼睑缘线
- 只调 R 眼（x 正），保存

### 3. 镜像 R→L
脚本：`scripts/mirror_markers.py`
- 镜像公式：L(x, y, z) = (-R_x, R_y, R_z)
- 删除 L 眼旧标记点，创建新镜像标记点（同样**不加约束**）

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

## 测试此链的纪律
- **place→mirror→read 测试跑会覆盖用户手调成果**：read 环节重新生成 `eyelid_contour_manual.json`，把用户 GUI 微调的数据替换成自动初始点数据。该 json 被 git 跟踪 = 用户资产；测试完立即 `git checkout HEAD -- <manual.json>` 恢复，提交前用 `git status`/`git diff --stat` 确认它不在暂存区
- markers blend 是运行时中间产物，不入 git，测试覆盖无害
- Blender stdout 混大量插件噪声（better_fbx/ARP/MACHIN3 的 Traceback 都是无害的），判断脚本成败要 grep 脚本自己打印的成功标记行，不能见 Traceback 就算失败

## 下游：眼窝碗面材质分区（QR 用）
手描 rim 轮廓定好后，碗面材质边界**不要**用几何投影（XZ pip/SVD 平面）事后识别——
手描 rim 是眼睑缘，比实际碗口沿小一圈，会漏判碗面。`make_eye_cup` 建碗面时已打
bmesh 标记 `v44tag_L/R==2`（边界=rim），`assign_socket_material.py` 直接读它即可。
QR 阶段 rim 边界归属用几何校正（xremesh 非确定）。
完整方法：`references/qr-eye-socket-material-partition.md`