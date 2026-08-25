# 05骨骼绑定 — 文件夹说明

**日期**: 2026-08-25 整理 | **目标**: 半自动打点 → Mixamo 22+骨骼 → GLB

## 两套流程分离（重要）

| 目录 | 内容 | 谁用 |
|---|---|---|
| `A_半自动打点/` | 打点模板、测量数据、镜像脚本 | **用户打点阶段** |
| `B_骨骼绑定/` | 骨骼生成、权重、导出 | **生成阶段** |
| `C_诊断工具/` | 模型分析、参考图、验证脚本 | 辅助 |

## A_半自动打点（照 01A 眼窝模板逻辑）

流程：`measure_joints.py`(测量) → `rig_semiauto_setup.py`(放标记) → 用户微调 → `mirror_rig_markers.py`(镜像L侧)

- `measure_joints.py` — 几何测量关节位置(身高分布+手臂厚度剖面+腿宽剖面)，写入 `joints_measured.json`
- `rig_semiauto_setup.py` — 用测量数据放 R 侧 8 点 + 中线，空 `LM_L` 集合
- `06_rig_markers.blend` — 打点模板（用户在此微调）
- `joints_measured.json` — 测量结果
- `mirror_rig_markers.py` — R 侧镜像到 L 侧

## B_骨骼绑定

- `rig_from_markers.py` — 读标记 → 生成 Mixamo 骨架(22+手指30+脚) → 自动权重 → 姿态纯净检查 → 导出
- `06_rig_final.blend` — 绑定结果（已清理标记点，保持 rest pose）
- `06_rig_final.glb` — 导出（含骨骼+权重+贴图）

### 关键防护：姿态纯净检查（根因修复 2026-08-25）

教训：验证测试的 pose 残留被保存进交付文件 → 头骨 28.6° 前倾把眼珠带歪（虹膜朝下）。
规则：**交付文件永远保持 rest pose**，检测到的残留姿态一律清零。
**验证测试必须在临时副本上做，不能动交付文件。**

## C_诊断工具

- `analyze_model.py` — 模型几何/姿态分析
- `render_shoulder_ref_v2.py` — 肩部打点参考图(PIL标注)
- `check_markers.py` / `diagnose_bones.py` / `verify_rig.py` / `verify_glb.py` / `validate_and_export.py` — 各环节验证
- `pose_test.py` — ⚠️ 姿态测试，**只能在临时副本跑**

## 运行顺序（完整重做一遍）

```
1. blender -b --python A_半自动打点/measure_joints.py
2. blender -b --python A_半自动打点/rig_semiauto_setup.py
3. [用户] 打开 A_半自动打点/06_rig_markers.blend 微调标记 → Ctrl+S
4. blender -b --python A_半自动打点/mirror_rig_markers.py
5. blender -b --python B_骨骼绑定/rig_from_markers.py -- --markers A_半自动打点/06_rig_markers.blend --output B_骨骼绑定/06_rig_final.glb
```

## 已知取舍（2026-08-25）

- 当前用**手写 Mixamo 骨架**方案，未用已安装的 Auto-Rig Pro 3.74.60。ARP 有 Smart 自动检测+手指/脚部完善绑定，但需要下载 AI 模型文件且绑定逻辑为 GUI 驱动，脚本化调用风险较高。待与用户确认是否改用。
