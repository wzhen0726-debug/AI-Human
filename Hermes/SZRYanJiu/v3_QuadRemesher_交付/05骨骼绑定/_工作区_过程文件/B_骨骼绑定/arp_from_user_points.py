"""ARP用户的Mixamo绑定 v2 (2026-08-27): 直接以用户17点为真源, 复用手写版方案A管线.
背景: arp_rig_v2.py走ARP Smart(guess_markers)把用户点丢给ARP后仍按默认比例长骨
      → 手腕差32cm. 用户判定"骨骼完全不对". 停用Smart自动流程.
原理: rig_semiauto_build.py(手写版方案A管线)吃标记点blend产出52骨mixamorig骨架,
      权重100%. 本脚本只换输入: 读ARP模板的用户17点(含镜像侧), 输出06_rig_arp.blend.
"""
impor...[truncated]