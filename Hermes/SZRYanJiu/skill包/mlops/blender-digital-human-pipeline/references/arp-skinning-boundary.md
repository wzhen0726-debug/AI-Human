# ARP Auto-Rig Pro 使用边界 (2026-08-26实测)

## 关键结论: ARP的match/bind生成的是"父级绑定"不是"顶点组蒙皮"
实测 `06_rig_arp_mixamo.blend`: 339骨骼、65根变形骨有mixamorig:前缀, 但mesh**顶点组0个、无armature修改器**, parent=cs_grp。骨骼动但网格不变形(MANUAL_BEND_MOVED=0)。
→ ARP后台跑出的rig要交付动画, 必须补"蒙皮权重"步骤(用arp_to_mixamo.py重命名后, 还需手工绑定权重, 或改用我们的手写版54骨骼流程, 后者已验证100%权重+行走动画通过)。

## 用户最终需求
交付Godot用: **纯mesh+骨骼, 无控制器**(ARP的IK/FK控制器在Godot不工作)。ARP后台去控制器导出可用 `arp_strip_controllers.py`(留mixamorig:骨,删其余), 但蒙皮权重仍缺。

## 推荐路径
需要手指精细动画时手写版骨骼已含30根手指骨(fan形展开), 且权重100% — 比ARP版完整。ARP版当前仅作骨骼结构参考。