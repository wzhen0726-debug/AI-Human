"""诊断: go_detect生成的_auto对象最终位置 — 验证标记是否被内部检测覆盖."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
RIG = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "07_arp_rig_v6.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)

# 我设的标记点
marks = {"root_loc":(0.0,0.0002,0.9007), "chin_loc":(0.0,-0.1138,1.5875),
         "neck_loc":(0.0,0.0382,1.4731), "shoulder_loc":(0.2289,0.0478,1.4349),
         "elbow_loc":(0.4579,0.0953,1.4349), "hand_loc":(0.7154,0.0193,1.4349),
         "hand_tip_loc":(0.9062,0.0192,1.4349), "thigh_loc":(0.1144,0.0002,0.9007),
         "knee_loc":(0.1144,0.0002,0.5191), "foot_loc":(0.1144,0.0762,0.1376)}

print("=== _auto对象最终位置 (go_detect内部检测结果) ===")
autos = [o for o in bpy.data.objects if o.name.endswith("_auto")]
print(f"_auto对象数: {len(autos)}")
for o in sorted(autos, key=lambda x: x.name):
    p = o.matrix_world.translation
    # 对应标记
    base = o.name.replace("_auto", "").replace(".l", "_loc").replace(".r", "_loc")
    mk = marks.get(base)
    comp = ""
    if mk:
        import math
        d = math.sqrt((p.x-mk[0])**2 + (p.y-mk[1])**2 + (p.z-mk[2])**2)
        comp = f" vs标记差{d*100:.1f}cm"
    print(f"{o.name}: ({p.x:.3f},{p.y:.3f},{p.z:.3f}){comp}")

# 原标记对象还在吗
print("\n=== 原标记对象 ===")
for k in marks:
    o = bpy.data.objects.get(k)
    print(f"{k}: {'在 '+str(tuple(round(v,3) for v in o.matrix_world.translation)) if o else '不存在'}")
print("DIAG2_DONE")
