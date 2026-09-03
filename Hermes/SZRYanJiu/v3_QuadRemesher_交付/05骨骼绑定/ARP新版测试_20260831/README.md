# 05 骨骼绑定（ARP 标记点驱动）

数字人骨骼绑定：AI 打点 + 用户 GUI 微调 → ARP go_detect → 提取 55 骨 Mixamo 命名骨架 → 自动权重 → 行走/跑步/跳跃动画验证。

## 产物

| 文件 | 说明 |
|---|---|
| `01_AI打点.blend` | AI 预置 17 个标记点（用户可在 GUI 微调，镜像约束自动跟随） |
| `02_go_detect骨架.blend` | ARP 生成的 348 骨（含 66 参考骨 + 30 手指） |
| `03_骨骼绑定.blend` | **最终骨架**：55 骨 Mixamo 命名 + 权重 + 眼球（蒙皮到 Head 骨） |
| `04_动作测试.blend` | 行走动画验证（贴地 0 腾空、Hips 起伏 4.8cm） |
| `多动画测试/` | anim_StandardWalk / anim_Running / anim_Jump（各含眼球，支撑期贴地全对） |

## 脚本（`scripts/`）

| 脚本 | 功能 |
|---|---|
| `run_all.py` | **一键管线**：`python run_all.py`（内部依次调 step1→2→3-7，自动跑自检） |
| `step1_ai_markers.py` | AI 打点（截图补丁：256分辨率+灰模Emission） |
| `step2_go_detect.py` | ARP go_detect 生成参考骨架 |
| `step3_to_7_rig_and_walk.py` | 提取55骨+align_roll+权重+眼球蒙皮+行走验证 |
| `check_markers.py` | 点位自检（对称/高度/链条/比例/root-thigh结构） |
| `qa_rig.py` | 骨架质量自检（骨数/对称/连贯/权重/零长度骨） |
| `qa_walk.py` | 行走质量自检（Hips起伏/膝盖轨迹） |
| `multi_anim_test.py` | 多动画测试（对03骨架套多个Mixamo动画） |
| `sole_qa.py` | 贴地精查（区分离地期和支撑期错误） |

## 用法

```bash
# 全流程(步骤1后建议GUI确认点位再继续)
python scripts/run_all.py

# 从步骤3续跑(点位已调好)
python scripts/run_all.py 3
```

## 关键规则（血泪教训）

1. **读带约束的对象位置必须 `evaluated_get(dg).matrix_world.translation`**，`o.location` 是约束前的假值
2. **ARP 肘关节会被内部"肘朝向修正"偏移 2.5cm**，建骨后要把 LeftForeArm.head 对回用户的 elbow_loc
3. **Hips 垂直起伏不能删**（删了双脚腾空+滑步），Hips 局部 y 轴=世界垂直
4. **用户打点即权威**：点打在哪骨骼就在哪，不做自动中心化/解剖修正
5. **root 点在骨盆上缘**（高于胯点 6-7cm），不是大腿根
6. **眼球不进 QR/烘焙**，在 05 绑定阶段并入并蒙皮到 Head 骨（顶点组权重 1.0）
7. **所有硬编码按身高/bbox 比例参数化**（跨体型通用）

## 文档

- `点位指南.md` — 17 个标记点的体表位置指南（速览表在前）
- `测试记录.md` — 本次从0重跑的完整对错记录
- 硬编码审计：`../../硬编码参数化审计_20260902.md`
