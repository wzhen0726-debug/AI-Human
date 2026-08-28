"""决定性诊断: 模型几何真实特征点 vs AI标记点 vs go_detect生成的骨架.
判断骨架偏移的根因到底是 标记错 还是 go_detect内部错."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
RIG = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "07_arp_rig_v6.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG)

body = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices))
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')

print(f"身体: {body.name}")
print(f"身体matrix_world缩放: {[round(s,4) for s in body.matrix_world.to_scale()]}")
print(f"身体dimensions: {[round(d,3) for d in body.dimensions]}")
print(f"骨架matrix_world缩放: {[round(s,4) for s in arm.matrix_world.to_scale()]}")
print(f"骨架dimensions: {[round(d,3) for d in arm.dimensions]}")

# 几何特征点: 顶点世界坐标统计
import statistics
n = len(body.data.vertices)
verts = [body.matrix_world @ body.data.vertices[i].co for i in range(0, n, 20)]
zs = [v.z for v in verts]
zs.sort()
H = max(zs) - min(zs)
print(f"\n模型高度: {H:.3f}m, 底={min(zs):.3f}, 顶={max(zs):.3f}")

# 各高度的X跨距与重心
def slice_info(z0, z1):
    pts = [v for v in verts if z0 <= v.z <= z1]
    if not pts: return None
    xs = [p.x for p in pts]
    return {"z": (z0+z1)/2, "x_min": min(xs), "x_max": max(xs),
            "cx": statistics.mean(xs), "n": len(pts)}

print("\n=== 几何切片 (找肩/腕/胯/膝/踝的真实位置) ===")
zbot = min(zs)
for frac, label in [(0.03,"踝"),(0.29,"膝"),(0.50,"胯"),(0.72,"肘/腕"),(0.80,"肩"),(0.82,"颈"),(0.88,"下巴"),(0.97,"头顶")]:
    z = zbot + H*frac
    si = slice_info(z-0.01, z+0.01)
    if si:
        print(f"{label} z≈{si['z']:.3f}: x∈[{si['x_min']:.3f},{si['x_max']:.3f}] cx={si['cx']:.3f} (n={si['n']})")

# AI标记点对照
print("\n=== AI标记点 (step1实测) ===")
marks = {"root_loc":(0.0,0.0002,0.9007), "chin_loc":(0.0,-0.1138,1.5875),
         "neck_loc":(0.0,0.0382,1.4731), "shoulder_loc":(0.2289,0.0478,1.4349),
         "elbow_loc":(0.4579,0.0953,1.4349), "hand_loc":(0.7154,0.0193,1.4349),
         "thigh_loc":(0.1144,0.0002,0.9007), "knee_loc":(0.1144,0.0002,0.5191),
         "foot_loc":(0.1144,0.0762,0.1376)}
for k, v in marks.items():
    o = bpy.data.objects.get(k)
    in_scene = f"场景中={o.location[:]}" if o else "场景无此对象"
    print(f"{k}: 记录={v} {in_scene}")

# 骨架关键骨
print("\n=== 生成骨架关键骨 (世界系) ===")
for bn in ["c_root_master.x","c_neck.x","c_head.x","shoulder.l","arm_stretch.l","forearm_stretch.l","hand.l","thigh_stretch.l","leg_stretch.l","foot.l"]:
    b = arm.data.bones.get(bn)
    if b:
        h = arm.matrix_world @ b.head_local
        print(f"{bn}: ({h.x:.3f},{h.y:.3f},{h.z:.3f})")
print("DIAG_DONE")
