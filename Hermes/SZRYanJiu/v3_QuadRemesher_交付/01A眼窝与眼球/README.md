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
| 2026-08-17 v37 | 面朝向全修复+几何定向 | v36删recalc换reverse_faces→update_edit_mesh撤销翻转(0%正确). v37根因: recalc本身也是错的(强制碗面+皮肤同向, 但二者应反向→皮肤面翻反+575). 改用纯几何定向: 碗面+倒角带面确定性翻向眼球(100%正确), 不碰皮肤面. 同时倒角改圆弧fillet(1/4圆弧, 3mm宽度精确), UV碗面avg_uv+倒角带ring0继承. 验证: 17/19 PASS, bowl+chamfer 100%朝眼球, 开放边0. 剩余: non_manifold 4(极点扇), front_inward接近基线. | scripts/socket_ops.py |
| 2026-08-13 v32 | ring0索引灾难修复 | v31教训: ring0顶点索引在dissolve+mode切换后重排失效 → R侧polygon乱序 → 几何兜底误翻184866面(整个头部翻乱)。修复: ①ring0_coords坐标快照构建polygon(不依赖索引) ②recalc参考面用坐标最近邻重建 ③几何兜底加Y深度带限制(-0.13~-0.08)双重保险。修复后geometric flip=126/169(正常量级)。 | scripts/socket_ops.py |
| 2026-08-13 v32 | 极点扇误溶修复 | flipped_slivers溶解(口沿皮肤碎片)误吞碗底极点三角扇(面积极小+满足原判据) → 碗底开放边+非流形边。修复: 加y上限<rim_y+1mm(极点扇在rim_y+12~15mm, 不受影响)。验证: 开放边0, 非流形仅剩输入自带1个。 | scripts/socket_ops.py |
| 2026-08-13 v31 | 面朝向真正根因 | FBX导入带custom_normal属性(INT16_2D CORNER, 5790212个) → Blender显示/渲染用custom normal而非绕序。新建碗面corner在该属性上是零向量→着色发黑破碎=用户看到的"面朝向反"；之前所有normal_flip/reverse_faces只改绕序不改custom normal→显示无变化→"修了没效果"。控制实验: 输入模型绕序与FBX corner normals吻合99.99%(1929789/1930069)，绕序本来就对。修复: ①main()加载时删custom_normal属性(绕序说了算) ②make_eye_cup末尾加几何朝向保证: 开口内(ring0多边形内)的面法线背离眼球中心就翻转(兜底拓扑recalc的启发式漏翻)。 | scripts/run_eye_socket.py + scripts/socket_ops.py |
| 2026-08-13 v31 | 废弃的全局法线方案(实验记录) | ①全局recalc_face_normals: 高模非流形边破坏flood-fill传播，后脑勺朝内面67551→199339恶化3倍。②质心规则翻转: 翻掉422589面(下颌底/腋下等悬垂面法线本就指向质心)，灾难性。③带区域边界的局部recalc: 把碗从皮肤锚点切断→重翻。结论: 全局/区域启发式对高模全部不可靠，几何判据兜底+删custom_normal才是正解。 | — |
| 2026-08-13 | 后脑勺穿透修复 | `fix_socket_normals` 的 `point_in_polygon` 只检查 X,Z 投影无 Y 限制，后脑勺同 X,Z 位置 395 面法线被误翻（+Y→-Y），视觉效果=穿透。根因: 3DDFA 眼睑轮廓 XZ 投影穿过头部中心。修复: 加 `fc.y < 0` 限制（前脸/碗全在 Y<0，后脑勺 Y>+0.05）。已验证: 后脑勺 391 面全部朝 +Y 正常。 | v3_QuadRemesher_交付/01A眼窝与眼球/scripts/run_eye_socket.py |
| 2026-08-13 | 开口轮廓加密+margin | 6 点折线杏仁形→24 点平滑多边形（弧长等距插值），加 0.5mm 径向 margin。解决"开口形状差一丢丢没对齐贴图/模型"。删面数 414→455 (L) / 397→432 (R)。 | v3_QuadRemesher_交付/01A眼窝与眼球/scripts/socket_ops.py |
| 2026-08-13 | 文件清理 | models/ 只保留 01_1_eye_socket.blend + 01_2_eyeball_placed.blend，删除旧版备份/暗像素版/glb 检查文件。诊断用临时贴图截图也清理。 | — |
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
