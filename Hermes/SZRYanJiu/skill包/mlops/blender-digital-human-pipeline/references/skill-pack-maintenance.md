# Skill库维护与跨设备同步规范 (2026-08-25, 用户明确纠正)

## 用户纠正（原话）
> "你的skill只写了我说的那一条，但是我这整个项目中有很多的skill你都没写吗？需要每个都写。然后保存，最好能给我提供skill包位置，方便我跨设备也能使用这些skill"

## 规范
1. **持续捕获**：本项目每个重要定案/踩坑/根因，当次会话就写入 `blender-digital-human-pipeline` 的 references/，不要等到用户要求。主管线已有123+个references，是项目记忆的事实载体。
2. **成对交付**：写reference的同时，把一行指针挂进 SKILL.md 索引，否则未来会话发现不了。
3. **打包交付**：阶段性收口时重新打包到 `skill包/数字人项目skill包_<日期>.zip`（648KB/208文件规模），解压到目标机器 `%LocalAppData%\hermes\skills\` 即可。包内保留 `mlops/`、`3d/`、`software-development/` 分类目录。
4. **打包范围**：主管线 + `blender-body-wrap`(失败档案) + `blender-head-retopology` + `blender-uv-texture-baking` + `glb-inspect-and-report` + `error-first-root-cause`。
5. 打包用 Python `shutil.make_archive`，stage 目录用后删除。

## ⚠️ SKILL.md 体积上限（2026-09-20 实测）

主 SKILL.md 已达 ~100,095 字符，**触顶平台 100,000 上限** —— 任何“增加文字”的 patch 都会报 `SKILL.md content is 100,095 characters (limit: 100,000)` 并**整批回滚**（write_file 也会被连坐）。
- 新内容一律写进 `references/`，指针挂在**已有且必读的 reference**上（如 `bake-qa.md`；主文件的“成对交付”规则暂时无法执行）；
- 需要直接编辑主文件时，先用“净化式 patch”（删旧+增新、净体积下降）把总量压到 9.8 万以下；后续做一次瘦身拆分（把长段移入 references/）。
