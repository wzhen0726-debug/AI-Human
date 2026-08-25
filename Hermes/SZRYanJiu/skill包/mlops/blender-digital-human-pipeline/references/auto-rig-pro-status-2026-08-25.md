# Auto-Rig Pro 现状评估与两版策略 (2026-08-25调查)

## 环境事实
- ARP 3.74.60 已安装: `C:\Users\<user>\AppData\Roaming\Blender Foundation\Blender\5.1\scripts\addons\auto_rig_pro-master\`
- Smart 模块 AI 模型文件齐全: `C:\Users\<user>\Documents\AutoRigPro\AI\` (body/手指检测)
- 可脚本化: 主模块91个 + smart 15个 + game-engine 34个 operator (`bl_idname`)
- **警告**: better_fbx 插件与 ARP 有注册冲突(后台模式启动时 `cleanup_line_fx` 报 AttributeError)，是良性噪音不阻断流程。

## 用户决策（2026-08-25原话）
> "两版都留着，但是优先使用arp研究制作，因为我需要手指"
> "你现在的手写方案目前的效果是可以的，所以继续做，看看完善了手部脚步之后的效果如何。但是ARP方案也要做，到时候我可以对比检查差距。"

## 执行要点
1. **两版并存不删**: 手写版(05骨骼绑定/B_骨骼绑定/) + ARP版(待建)，供用户对比检查差距。
2. **优先级**: ARP 研究制作优先——手指权重质量是手写版短板。
3. **禁止行为**: 不要因为ARP脚本化有踩坑风险就跳过它(用户已明确要两版)。也不要只留一版。
4. **验收标准**: 两版都要能播放 `原始模型/Mixamo动画文件/Standard Walk.fbx` 行走动画，且对齐65骨骼命名(见 `mixamo-65bone-alignment-standard.md`)。
5. 早期 ARP 背景模式经验见 `auto-rig-pro-background-mode.md`。
