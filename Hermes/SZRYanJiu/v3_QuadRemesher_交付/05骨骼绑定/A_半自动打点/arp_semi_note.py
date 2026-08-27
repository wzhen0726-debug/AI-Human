"""ARP版半自动打点模板生成(2026-08-27, 用户要求: 像手写版一样用户打点→保存→我跑剩余).
设计: 复用手写版8点模板(同一套点两用!), 用户已打过一次点, 无需重打.
      手写版模板06_rig_markers.blend直接作为ARP输入.
      ARP Smart需要它自己的标记名(root_loc/neck_loc/chin_loc/shoulder_loc/hand_loc/
      foot_loc/thigh_loc/knee_loc/elbow_loc/hand_tip_loc + _sym), 脚本从LM点换算.
"""
print("ARP半自动打点模板说明:")
print("复用手写版8点: 06_rig_markers.blend (用户已打好)")
print("ARP绑定脚本从LM点换算成ARP标记, 用户无需再打点")
print("ARP_SEMI_NOTE_DONE")