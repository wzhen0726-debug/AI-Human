# Delivery & Documentation Convention (user rule, 2026-08-05)

Applies to the digital-human pipeline delivery directories (e.g.
`Hermes/SZRYanJiu/v3_QuadRemesher_交付/`). The user corrected this twice —
treat as a hard rule for every pipeline step.

## What goes where

| Content | Location |
|---|---|
| README (方案说明/参数/输入输出/验证结果) | delivery dir root ✅ |
| `scripts/` — re-runnable py scripts | delivery dir ✅ |
| Products (blend/fbx/png) | delivery dir, local only via `.gitignore` ✅ |
| Failure records / problem analysis (问题分析) | `方案md记录/v3_QuadRemesher/` — NOT delivery |
| Operation manuals (操作手册) | `方案md记录/v3_QuadRemesher/` — NOT delivery |
| Work logs (工作记录) | **nowhere** — user's private work content; do not write, do not retain |

## After any pipeline rerun

1. Update the delivery README with the fresh verification numbers
   (face counts, quad %, island count, bake alignment deviation, visual-check verdict).
2. `git add -A && git commit && git push` — the user requires BOTH local files
   and GitHub to be in sync. Empty dirs get a README placeholder; binaries stay gitignored.
3. Never invent verification numbers in the README — only paste values from
   actual run logs.

## Observed correction (2026-08-05)

Agent wrote a work log into `方案md记录/` and started describing it as part of
the delivery flow. User: "工作记录不要放到这个作业流程里，那个是我私人工作，
不用保留" → deleted the file immediately and recorded the preference.
