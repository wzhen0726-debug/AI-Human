"""验证: 实时镜像驱动是否生效(临时挪R点→看L点跟随→立即还原)."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

R = bpy.data.objects["LM_04_右肩_shoulder_R"]
L = bpy.data.objects["LM_04_左肩_shoulder_L"]

orig = R.location.copy()
Lv0 = L.matrix_world.translation.copy()
print(f"初始: R={tuple(round(v,3) for v in orig)}, L={tuple(round(v,3) for v in Lv0)}")

# 临时挪R点 (+0.05, -0.02, +0.03)
R.location = (orig.x + 0.05, orig.y - 0.02, orig.z + 0.03)
bpy.context.view_layer.update()
Lv1 = L.matrix_world.translation.copy()
print(f"挪R后: R={tuple(round(v,3) for v in R.location)}, L={tuple(round(v,3) for v in Lv1)}")

ok = (abs(Lv1.x - (orig.x + 0.05) * -1) < 0.001 and
      abs(Lv1.y - (orig.y - 0.02)) < 0.001 and
      abs(Lv1.z - (orig.z + 0.03)) < 0.001)
print(f"同步镜像验证: {'✅ 左点实时跟随(x取反,y/z同步)' if ok else '❌ 失败'}")

# 立即还原
R.location = orig
bpy.context.view_layer.update()
print(f"已还原: R={tuple(round(v,3) for v in R.location)}")
print("VERIFY_LIVE_DONE")
