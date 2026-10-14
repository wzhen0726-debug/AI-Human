# V2 流程代码复核文档（每环节一份）

> 基线：`V2正式基线_20261012`（10-12 clean all 全新完整跑，用户验收达标）。
> 本目录 = 该版流程的**逻辑说明 + 完整核心代码**（代码逐字节取自正式脚本，附 md5 可对账）。

## 环节文档

| 文档 | 环节 | 核心脚本 |
|---|---|---|
| `00_总控_控制台.md` | 总控（控制台.py） | 控制台.py |
| `01_高模修复.md` | 高模修复与黏连检测 | run_repair.py、repair.py、adhesion.py |
| `01a_眼窝眼球.md` | 3DDFA 锚 + 打点 + 眼窝重建 | regen_iris_3ddfa.py、_3ddfa_render_front.py、_3ddfa_backproject.py、place_eyelid_markers.py、setup_marker_gui.py、mirror_markers.py、read_eyelid_markers.py、run_eye_socket.py、socket_ops.py、rim_ring_recalibrate.py、assign_socket_material.py、iris_detect.py、eye_socket_config.py |
| `02_QR拓扑.md` | QR 拓扑 + 眼窝碗 + 眼球摆入 | 02_qr_auto.py、selfint_clean.py、rim_restore.py、02qr_socket_cup.py、run_eyeball_v2.py、eyeball_config.py、eye002_config.py |
| `03_自动UV.md` | 自动 UV 展开 | 03_auto_uv.py |
| `04_纹理烘焙.md` | 纹理烘焙 4K + 溢出处理 | 04_bake.py、texture_fix.py |
| `05_骨骼绑定.md` | 骨骼绑定与动作重定向 | step1_ai_markers.py、step2_go_detect.py、step3_to_7_rig_and_walk.py、normalize_to_tpose.py、retarget_mixamo.py |
| `06_GLB导出.md` | GLB 导出与自查 | 06_output_glb.py |

## 全链数据流

```
raw_model.glb
  → 01 修复/校正/焊接/黏连 → 01_highpoly_repair.blend
  → 01a ⓪3DDFA锚(iris_3ddfa.json) ①放点+GUI手调 ②镜像 ③72点轮廓(eyelid_contour_manual.json)
        ④眼窝开孔+rim重标定+眼角留空+碗 → 01_1_eye_socket.blend  ⑤材质分区 → _qr.blend
  → 02 QR拓扑(重抽择优)+rim恢复+自交清理 → 碗重建(纯rim) → 眼球摆入并入 → 02_qr_150k_socket.blend / 01_2
  → 03 UV(自参照三判据寻优) → 03_auto_uv.blend
  → 04 烘焙4K(源=01闭合眼睑高模)+texture_fix → 04_bake.blend + diffuse/normal 4k
  → 05 AI打点+GUI → go_detect → 55骨+权重+眼球 → 标准化(四肢47骨) → 增量重定向(走跑跳) → 04_动作测试.blend
  → 06 GLB导出+五关自查 → 06_角色_走跑跳.glb
```

## 环境

- Blender 5.1 无头：`D:/Program Files/Blender Foundation/Blender 5.1/blender.exe -b --factory-startup -noaudio --python-exit-code 1`
- 3DDFA-V3：`SZRYanJiu/3DDFA-V3/.venv`（torch 2.5.1+cu121，CPU 推理 ~10s/图；目录只读）
- QR 引擎：QuadRemesher 扩展 xremesh.exe（禁并行/禁中文 temp 路径）；AutoRigPro 插件（05）
- 运行入口：`python 控制台.py all`（或单环节 01/01a/01r/02/03/04/05/06；clean 清理）

## 代码行数清单

| 文档 | 脚本 | 行数 |
|---|---|---|
| 00_总控_控制台.md | 控制台.py | 609 |
| 01_高模修复.md | 01高模修复/scripts/run_repair.py | 71 |
| 01_高模修复.md | 01高模修复/scripts/repair.py | 534 |
| 01_高模修复.md | 01高模修复/scripts/adhesion.py | 346 |
| 01a_眼窝眼球.md | 01a眼窝眼球/scripts/regen_iris_3ddfa.py | 127 |
| 01a_眼窝眼球.md | 01a眼窝眼球/scripts/_3ddfa_render_front.py | 77 |
| 01a_眼窝眼球.md | 01a眼窝眼球/scripts/_3ddfa_backproject.py | 83 |
| 01a_眼窝眼球.md | 01a眼窝眼球/scripts/place_eyelid_markers.py | 281 |
| 01a_眼窝眼球.md | 01a眼窝眼球/scripts/setup_marker_gui.py | 75 |
| 01a_眼窝眼球.md | 01a眼窝眼球/scripts/mirror_markers.py | 261 |
| 01a_眼窝眼球.md | 01a眼窝眼球/scripts/read_eyelid_markers.py | 129 |
| 01a_眼窝眼球.md | 01a眼窝眼球/scripts/run_eye_socket.py | 198 |
| 01a_眼窝眼球.md | 01a眼窝眼球/scripts/socket_ops.py | 4207 |
| 01a_眼窝眼球.md | 01a眼窝眼球/scripts/rim_ring_recalibrate.py | 763 |
| 01a_眼窝眼球.md | 01a眼窝眼球/scripts/assign_socket_material.py | 275 |
| 01a_眼窝眼球.md | 01a眼窝眼球/scripts/iris_detect.py | 99 |
| 01a_眼窝眼球.md | 01a眼窝眼球/scripts/eye_socket_config.py | 247 |
| 02_QR拓扑.md | 02QR拓扑/scripts/02_qr_auto.py | 927 |
| 02_QR拓扑.md | 02QR拓扑/scripts/selfint_clean.py | 635 |
| 02_QR拓扑.md | 02QR拓扑/scripts/rim_restore.py | 924 |
| 02_QR拓扑.md | 02QR拓扑/scripts/02qr_socket_cup.py | 278 |
| 02_QR拓扑.md | 01a眼窝眼球/scripts/run_eyeball_v2.py | 267 |
| 02_QR拓扑.md | 01a眼窝眼球/scripts/eyeball_config.py | 48 |
| 02_QR拓扑.md | 01a眼窝眼球/scripts/eye002_config.py | 48 |
| 03_自动UV.md | 03自动UV/scripts/03_auto_uv.py | 456 |
| 04_纹理烘焙.md | 04纹理烘焙/scripts/04_bake.py | 453 |
| 04_纹理烘焙.md | 04纹理烘焙/scripts/texture_fix.py | 1102 |
| 05_骨骼绑定.md | 05骨骼绑定/ARP新版测试_20260831/scripts/step1_ai_markers.py | 131 |
| 05_骨骼绑定.md | 05骨骼绑定/ARP新版测试_20260831/scripts/step2_go_detect.py | 70 |
| 05_骨骼绑定.md | 05骨骼绑定/ARP新版测试_20260831/scripts/step3_to_7_rig_and_walk.py | 395 |
| 05_骨骼绑定.md | 05骨骼绑定/ARP新版测试_20260831/scripts/normalize_to_tpose.py | 601 |
| 05_骨骼绑定.md | 05骨骼绑定/ARP新版测试_20260831/scripts/retarget_mixamo.py | 412 |
| 06_GLB导出.md | 06GLB导出/scripts/06_output_glb.py | 301 |

合计 15430 行（33 个脚本）。
