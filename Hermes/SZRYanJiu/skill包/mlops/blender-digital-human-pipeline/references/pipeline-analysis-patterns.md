# WBS Contradiction Analysis & Pipeline Versioning

## WBS Contradiction Analysis Pattern

When receiving a technical plan or WBS from a user, do NOT accept it at face value. Systematically analyze for internal contradictions before implementing:

1. **Read every task and cross-reference with technical constraints**
2. **Identify contradictions**: Task A says X, but Task B requires Y. Are they compatible?
3. **Research each contradiction**: Is it fixable with adjustment? Or is it a fundamental conflict?
4. **Produce a discrepancy table**: What the WBS says → Why it's wrong → Correction
5. **Estimate timeline impact**: How much time does each fix add?
6. **Deliver corrected WBS + discrepancy analysis**

### Example contradictions found in a digital human pipeline WBS:

| WBS Statement | Contradiction | Resolution |
|---------------|---------------|------------|
| "Delete eye separation" | Baking requires separating high-poly eyes | ONLY if using MetaHuman wrap template (empty eye sockets). For Quad Remesher, eyes are part of mesh — no separation needed |
| "Smart UV Project, 0.5 weeks" | Smart UV Project is not production-quality | Replace with auto edge-angle seam detection + standard Unwrap (still automated) |
| "30万面" | Mixamo upload boundary (~25-50万面 risk) | Lower to 20-25万面 |
| "Disable Symmetry X" | Mixamo binding quality suffers | If clothing is tight/symmetric, enable Symmetry X |

## "全自动化" Constraint

When the user explicitly states the entire pipeline must be fully automated, this is a **hard constraint**. Do NOT:
- Propose manual UV unwrapping
- Propose manual weight painting corrections
- Propose any step requiring human Blender interaction

Instead:
- Find automated alternatives for every step
- Accept quality tradeoffs that come with automation
- Document which quality aspects are impacted by full automation
- Use auto edge-angle seam detection instead of manual seam marking
- Use auto weight repair scripts instead of manual weight painting

## Three-Version Archive Pattern

When a project evolves through distinct technical approaches, produce per-version archives for context compression across sessions:

1. **One folder per version** (v1_MetaHumanWrap, v2_镜像对称, v3_QuadRemesher)
2. **Each folder contains**: Complete technical archive MD + all relevant source files + reference documents
3. **Archive MD format**: Environment → Goal → Steps → Problems → Solutions → Final State → Key API/Tech Notes
4. **Copy actual files** into the folder, do NOT use file path indexes (paths break across PCs)

### Archive MD headers:
```
# 版本[N]：[方案名称] — 完整技术档案
## 环境
## 项目目标  
## 技术调研过程
### 调研1：[名称]
### 调研2：[名称]
...
## 代码实现
## 问题与解决
## 最终状态
## 关键API/技术备忘
## 文件清单
```

## Quad Remesher Pipeline: Eye Separation Clarification

When using Quad Remesher (not MetaHuman template wrap), eyes are part of the input mesh and get remeshed naturally. Eye separation is ONLY needed for MetaHuman wrap pipelines where the template head has empty eye sockets. For Quad Remesher pipelines, do NOT separate eyes — they stay in the mesh throughout.
