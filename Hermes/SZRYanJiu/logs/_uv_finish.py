# -*- coding: utf-8 -*-
"""UV改造收尾: 控制台挂接 / README / 方案md(新记录+索引+复盘) / 交付版同步"""
import io, os, shutil, filecmp

BASE = r"E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu"
DEMO = os.path.join(BASE, "演示版_终端控制端")
MD = os.path.join(BASE, "方案md记录")
DELV = os.path.join(BASE, "v3_QuadRemesher_交付")

def rd(p): return io.open(p, encoding="utf-8").read()
def wr(p, s): io.open(p, "w", encoding="utf-8", newline="").write(s)
def sub(p, pairs):
    s = rd(p)
    for old, new in pairs:
        assert old in s, f"MISS in {os.path.basename(p)}: {old[:60]}"
        s = s.replace(old, new, 1)
    wr(p, s); print("  ✓ 更新", os.path.relpath(p, BASE))

# ---------- 1. 控制台 step_03 ----------
p = os.path.join(DEMO, "控制台.py")
sub(p, [
 ('''    if not run_blender(os.path.join(BASE, "03自动UV", "scripts", "03_auto_uv.py"),
                       "03_UV", "Smart UV Project"):
        summary("环节 03", False, t0, []); return False
    out = os.path.join(BASE, "03自动UV", "输出", "03_auto_uv.blend")
    ok = deliver(out, os.path.join(BASE, "03自动UV", "输出"))
    summary("环节 03 自动UV", ok, t0, [f"{D}UV范围{W} 少接缝无碎岛(66°角度限制)"])
    return ok''',
  '''    if not run_blender(os.path.join(BASE, "03自动UV", "scripts", "03_auto_uv.py"),
                       "03_UV", "UV展开+浪费检测/参数寻优", done_mark="UV_DONE"):
        summary("环节 03", False, t0, []); return False
    out = os.path.join(BASE, "03自动UV", "输出", "03_auto_uv.blend")
    ok = deliver(out, os.path.join(BASE, "03自动UV", "输出"))
    pick = f"{D}UV{W} 浪费检测+参数寻优(判据自参照, 无写死阈值)"
    try:
        for ln in io.open(os.path.join(LOGS, "03_UV.txt"), encoding="utf-8", errors="ignore"):
            if "选定:" in ln:
                pick = f"{D}UV{W} " + ln.split("选定:")[1].strip(); break
    except Exception:
        pass
    summary("环节 03 自动UV", ok, t0, [pick])
    return ok'''),
])

# ---------- 2. 演示版 README ----------
p = os.path.join(DEMO, "README.md")
sub(p, [
 ("| `03` | 自动UV展开 | Smart Project 少接缝无碎岛 | ~10 秒 |",
  "| `03` | 自动UV展开 | Smart Project + **UV浪费检测&参数自动寻优**(利用率/空块/密度 全数据计算) | ~1 分钟 |"),
])

# ---------- 3. 新方案md记录 ----------
doc = os.path.join(MD, "v3_QuadRemesher/03自动UV/UV空间浪费检测与参数寻优_20260917.md")
wr(doc, """# 03 自动UV — 大面积浪费检测 + 参数自动寻优（2026-09-17）

## 问题
实测：原 UV 展开（Smart UV Project 66° + 自带打包）存在**大面积浪费** —— 左中/左下整块连续空
白（最大空方块边长 0.238，面积占地图 5.68%），利用率仅 30.9%。

## 检测方案（全部由数据算出，无写死阈值）

每次展开后测量四项：

| 指标 | 算法 |
|---|---|
| 利用率 U | Σ\\|UV面面积\\| / 1.0（逐面 Shoelace 求和） |
| 最大空方块 | 布局栅格化(256²) + 2格膨胀封孔 → 最大空方块 DP（边长/面积，归一化 0~1） |
| 岛统计 | UV连通分量（共享边且两端UV相等）→ 岛数 / 最大岛面积与边长 / 中位岛边长 |
| 纹素密度CV | 逐面 (UV面积 / 3D面积) 的变异系数（保护烘焙密度均匀性） |

**废料判据（自参照）**：`最大空方块面积 ≥ 最大岛面积` → 大面积浪费
（含义：空块大到能装下最大的岛 = 打包失败；判据不含任何写死常量）

## 参数寻优（自动重跑）

候选阶梯（每候选：展开→测量）：

- 66° Smart UV（既有"少接缝"定案）= **基准**
- 66°/75°/82°/89° 各 + 岛屿纹素密度均匀化(`average_islands_scale`) + **CONCAVE 重打包**
  (`pack_islands`: rotate=True, scale=True, margin_method=SCALED, margin=0.01)

选择规则：满足废料判据、且密度CV ≤ 基准CV 的候选中，取**利用率最高**；全不通过则取最高并告警。
选定后用该参数再重跑一次定状态 → 保存 + 输出前后布局PNG。

## 实测（本模型 161,083 面，程序用时 ~60s）

| 候选 | 利用率 | 最大空方块 | 岛数 | 密度CV | 判定 |
|---|---|---|---|---|---|
| 基准 66°(自带打包) | 30.9% | 0.238 (5.68%) | 429 | 0.114 | ✗ 浪费(5.68%≥5.54%) |
| 66°+均匀化+重打包 | 41.6% | 0.020 (0.04%) | 429 | 0.108 | ✓ |
| **75°+均匀化+重打包（选定）** | **41.8%** | **0.020 (0.04%)** | **421** | **0.106** | ✓ |
| 82°+均匀化+重打包 | 38.7% | 0.020 (0.04%) | 478 | 0.109 | ✓（U更低） |
| 89°+均匀化+重打包 | 42.9% | 0.066 (0.44%) | 333 | 0.221 | ✗ 密度CV变差（被约束剔除） |

**结果：利用率 30.9% → 41.8%（+10.9pp）**，大面积空块消失（0.238→0.020）。
视觉复核（前后布局图）：岛形态不变、仅重排/旋转、无重叠、无越界。

## 位置与下游

- 脚本：`演示版_终端控制端/03自动UV/scripts/03_auto_uv.py`（交付版已同步）
- 前后布局图：`03自动UV/输出/03_uv_layout_before.png / _after.png / _对比.png`
- 下游重跑：04烘焙（贴图处理 溢出 15816→9433px，40.4% 清除）、05 提取/标准化/重定向
  ALL PASS、06 GLB 重导入复核（比例 0.00mm / 动画签名 0.11mm）——全链一致。
""")
print("  ✓ 新建", os.path.relpath(doc, BASE))

# ---------- 4. 根README 结论13 ----------
p = os.path.join(MD, "README.md")
sub(p, [
 ("12. **管线集成 (07, 2026-09-17)**: `演示版_终端控制端/控制台.py` 一条命令跑 01→06；录屏前全链自检 22 项 0 缺失",
  """12. **管线集成 (07, 2026-09-17)**: `演示版_终端控制端/控制台.py` 一条命令跑 01→06；录屏前全链自检 22 项 0 缺失
13. **UV浪费检测与参数寻优 (03, 2026-09-17)**: 展开后自动测量 利用率/最大空方块/岛统计/密度CV；**判据自参照**（最大空方块面积≥最大岛面积=大面积浪费）→ 参数阶梯(66°/75°/82°/89° × 均匀化+CONCAVE重打包)自动重跑选优；本模型 利用率 30.9%→41.8%、空块消失，全链已刷新"""),
])

# ---------- 5. 复盘追加 ----------
p = os.path.join(MD, "项目问题复盘总记录.md")
with io.open(p, "a", encoding="utf-8", newline="") as f:
    f.write("""

### 追加（09-17 当日后续）：UV 大面积浪费

| 项 | 经过 | 结论/正确做法 |
|---|---|---|
| UV展开浪费 | 用户截图指出大面积空白；原算法"跑完就存"无任何质量检测 | **检测写成算法的一部分**：利用率/最大空方块/岛统计/纹素密度CV 全部实测计算；**判据自参照不写死**（"空块大到能装下最大的岛"=浪费）；参数阶梯自动重跑选优（约束=密度CV不劣于基准）；本模型 30.9%→41.8%、空块 0.238→0.020 |
| 经验 | 教训：**凡是"生成结果"的环节都应带自测+可调参数重跑**，而不是靠人眼看图发现 | 同 03B/04/05 的自查体系；布局前后图 + 指标表随产物落盘 |
""".replace("\n", "\r\n"))
print("  ✓ 追加 复盘")

# ---------- 6. 交付版同步 ----------
jobs = [
 (os.path.join(DEMO, "03自动UV/scripts/03_auto_uv.py"),
  os.path.join(DELV, "03自动UV/scripts/03_auto_uv.py")),
 (doc, os.path.join(MD, "v3_QuadRemesher/03自动UV/UV空间浪费检测与参数寻优_20260917.md")),
]
for src, dst in jobs[:1]:
    if os.path.exists(dst) and filecmp.cmp(src, dst, shallow=False):
        print("  = 交付版已同", os.path.basename(src))
    else:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst); print("  ✓ 同步交付版", os.path.relpath(dst, BASE))
print("完成")
