# 管线交付目录审计 — 程序与常见发现 (2026-09-02 实战)

> 用途: 用户要求"检查整个交付目录是否合理、没有bug"时的标准审计流程。
> 适用于任何多阶段管线交付目录(01修复→02拓扑→03UV→04烘焙→05绑定→06导出)。

## 审计步骤(按序)

### 1. 全量语法扫描(一次ast遍历, 不分批)
```python
import ast, os
for root, _, files in os.walk(交付目录):
    for f in files:
        if f.endswith('.py'):
            try: ast.parse(open(os.path.join(root,f),encoding='utf-8').read())
            except SyntaxError as e: 记录
```
典型发现: 被截断的废弃脚本(如写到一半的6行文件)。`_工作区_过程文件` 里的旧脚本常是死代码, 直接删。

### 2. 路径引用核对
正则提取字面量绝对路径 `([A-Za-z]:\\[^'"\n\r]+|\bE:/[^\s'"\n\r]+|\bD:/...)`, 逐个 `os.path.exists`。
`os.path.join` 拼接的路径无法静态解析, 靠历次成功运行的日志验证。
注意: 缺失文件不一定是bug — 先看代码有无 `os.path.exists()` 兜底(如修复贴图可选替换)。

### 3. 输入/输出链核对
对每个主脚本 `grep -nE "open_mainfile|_BLEND|IN ="` 找输入, 确认它指向上一阶段的真实产物文件。
时间线交叉验证: `ls -la` 看产物时间, 确认"04用的是哪一版眼窝"(例: 02用rim_sharp版, 04高模用eye_socket版 — 需读README确认是有意的)。

### 4. 自检脚本过时值(高发!)
决策变更后, 配套的自检脚本参考值必须同步更新, 否则自检永远报错。
实例: root点从"与胯同高0.88"改为"骨盆上缘~0.94"后, `check_markers.py` 的 `EXPECTED_Z["root_loc"]` 和 root-thigh 容差(改为4-10, 实测该模型10.4)都要改。

### 5. 入口脚本健壮性
- 成功判定不能只看 returncode: Blender `--python` 脚本内部异常也可能exit 0 → 必须校验各步骤的完成标记(如 `STEP1_DONE`)。
- 传参要两种都支持: `python run_all.py 2` 和 `-- 2`(Blender传参)。
- 重跑会覆盖人工产物的步骤(如step1 AI打点)必须**先自动备份**(带时间戳)再覆盖。

### 6. 文档一致性
README的目录结构表、"最后更新"日期、各步骤状态(✅/进行中)与实际文件对照。

## 提交时注意
- git-bash 下 `2>nul` 会创建真实 `nul` 文件(见 `arp-marker-binding-2026-09.md` 坑7), 提交前 `git status` 发现就删掉: `os.remove("\\\\?\\" + 完整绝对路径)`。
- 二进制(.blend/.png/.glb)走 .gitignore 不入git, 只提交 py/md。

## 本目录已确认的"不用改"清单(避免重复纠结)
- 04烘焙 FIXED_TEX 缺文件: 有 os.path.exists 兜底, 设计如此
- eye_spherefit.py: 死代码(无调用者), 拟合结果已预存, 眼球属解剖常数已验收
- 02QR TargetQuadCount=140000 / 03UV island_margin=0.01: 质量档位非体型参数
- Hips尾与Spine头前后差1cm: ARP参考骨解剖设计(骨盆与腰椎连接点前后错开), 不是断开
