"""验证: L侧点是否实时跟随R侧(临时移动R肩, 检查L肩同步, 再还原)."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

R = bpy.data.objects["LM_04_右肩_shoulder_R"]
L = bpy.data.objects["LM_04_左肩_shoulder_L"]

rx0, ry0, rz0 = R.location.copy()
lx0 = L.matrix_world.translation.copy()
print(f"初始: R=({rx0:.3f},{ry0:.3f},{rz0:.3f}) L=({lx0.x:.3f},{lx0.y:.3f},{lx0.z:.3f})")

# 移动R肩 (+0.05, +0.02, +0.03)
R.location = (rx0 + 0.05, ry0 + 0.02, rz0 + 0.03)
bpy.context.view_layer.update()
lx1 = L.matrix_world.translation.copy()
print(f"挪R后: R=({rx0+0.05:.3f},{ry0+0.02:.3f},{rz0+0.03:.3f}) L=({lx1.x:.3f},{lx1.y:.3f},{lx1.z:.3f})")

# 期望: L.x = -(rx0+0.05), L.y = ry0+0.02, L.z = rz0+0.03
exp_x = -(rx0 + 0.05)
ok = abs(lx1.x - exp_x) < 0.001 and abs(lx1.y - (ry0+0.02)) < 0.001 and abs(lx1.z - (rz0+0.03)) < 0.001
print(f"期望: L=({exp_x:.3f},{ry0+0.02:.3f},{rz0+0.03:.3f}) → {'✅同步镜像成功' if ok else '❌未同步'}")

# 还原
R.location = (rx0, ry0, rz0)
bpy.context.view_layer.update()
print(f"已还原: R=({R.location.x:.3f},{R.location.y:.3f},{R.location.z:.3f}) L=({tuple(round(v,3) for v in L.matrix_world.translation)})")
print("VERIFY_SYNC_DONE")
