# Auto-Rig Pro 后台（-b）绑定管线 — 2026-08-25 补丁清单

## 执行顺序（关键）
`bpy.ops.wm.read_factory_settings(use_empty=True)` **必须先于** `addon_enable('auto_rig_pro-master')`——reset 会卸载插件。
载入模型用 `libraries.load` + link，不要用 `open_mainfile`（会再次重置插件状态）。

## AI Smart 检测后台补丁（缺一即崩/失败）
1. popup 补丁：background 无 OpenGL 上下文，`popup`/`screenshot` 相关 operator 会崩——monkey-patch
2. 截图补丁：`_screenshot_char` 用 Cycles/EEVEE 渲染替代 OpenGL 截图
   - 文件名必须严格是 `front1.jpg` / `char_side.jpg` / `char_top.jpg`（推理 exe 固定读这些名）
   - **强制 `image_settings.file_format='JPEG'`**（场景默认 PNG 会让 exe 找不到文件）
   - **材质用 Emission 自发光 0.8 灰**——后台场景无灯光，BSDF 渲染成黑色剪影，AI 检测不到人体（症状：关键点全在图像边缘 (0,508) 之类）
   - `ai_presets_path` 指向 `...\AutoRigPro\AI`（**不要**带 `\inference` 尾，ARP 会自己追加，带了会变成 `\inference\inference\`）
   - `scn.arp_smart_AI_body_samples = 1`（截图补丁只产 front1，默认 2 张会找 front2 报错）
3. `guess_markers` 崩溃防御：AI 检测点挤在中心时臂角计算会除零崩溃——try/except 包住，崩了就用几何测量的标记位置继续 `go_detect`

## 产物
Smart 检测 + go_detect 产出 339 骨（含控制器）。`mixamo_fk.bmap` 预设可做 ARP→Mixamo 命名映射；补 6 根 End/Spine 后到 65 骨全对齐 Mixamo。

## ⚠️ 未解决/需 GUI 复核（诚实记录，勿当已验证流程）
ARP 生成的是**控制器骨架**（c_* 控制柄 + 变形骨）。2026-08-25 后台实测：armature 修改器在、顶点组与骨骼名匹配（59/65）、权重非零，但**网格变形为 0**（手动弯 pose bone 也不动），根因未定位。控制器约束已清（fix_constraints_walk 路径在此前一轮会话里曾让手写版行走测试通过）。
**结论：ARP 版的蒙皮生效性必须在 Blender GUI 里人工验收，后台脚本验证不可靠。** 手写版（rig_from_markers）绑定+行走测试是已验证的可用路径。
