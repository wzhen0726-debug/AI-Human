"""读取用户GUI调好的R眼标记点, 镜像到L, 生成新眼裂轮廓JSON.

v45: 只投影y(保留用户打点的x,z), 不改变形状. 镜像=x取负.
"""
import bpy, os, sys, json
import numpy as np
from mathutils import Vector, kdtree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

MARKERS = os.path.join(S01A, "输出", "01A_markers_eyelid.blend")
OUT = os.path.join(S01A, "3ddfa", "eyelid_contour_manual.json")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=MARKERS)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
mesh = obj.data

# KD-tree只用于找表面y, 不改x,z
kd = kdtree.KDTree(len(mesh.vertices))
mat = obj.matrix_world
for v in mesh.vertices:
    kd.insert(mat @ v.co, v.index)
kd.balance()

def surface_y(x, z):
    co, idx, dist = kd.find(Vector((x, -0.11, z)))
    return co.y

result = {}
# ---- v89(2026-09-30, E3 上正式): 眼区镜像轴 env 覆盖(与 mirror_markers.py 同名 env 配对) ----
# 设 EYE_EYE_AXIS_MM=-0.67 → L 侧不再读文件里的 LM_L 标记, 直接用 LM_R(手描权威点)绕该轴
#   镜像生成: x' = 2a - x_R, z 不变, y 仍投到表面 → 等效 L 轮廓 x 平移 -1.2mm(轴差 0.6mm×2)。
#   好处: 不重写 01A_markers_eyelid.blend(LM_R 手调数据只读), 修正轮廓仍可由本步一步复现。
# 默认不设 = 读 LM_L(历史行为不变)。
_AA = os.environ.get("EYE_EYE_AXIS_MM")
_AXIS_OVR = None
if _AA not in (None, ""):
    try:
        _AXIS_OVR = float(_AA) / 1000.0
        print(f"眼区镜像轴 env 覆盖: EYE_EYE_AXIS_MM={_AXIS_OVR*1000:+.4f}mm (L 侧由 LM_R 镜像生成)")
    except ValueError:
        print(f"EYE_EYE_AXIS_MM 无效: {_AA!r} → 忽略(按 LM_L 读)")
for side in ['L', 'R']:
    coll = bpy.data.collections.get(f"LM_{side}")
    if not coll:
        print(f"!! 找不到集合 LM_{side}")
        continue
    objs = sorted([o for o in coll.objects if o.type == 'EMPTY'], key=lambda o: o.name)
    for o in objs:
        print(f"  {o.name}: loc=({o.location.x:.4f},{o.location.y:.4f},{o.location.z:.4f})")
    if side == 'L' and _AXIS_OVR is not None:
        _rc = bpy.data.collections.get("LM_R")
        _ro = sorted([o for o in _rc.objects if o.type == 'EMPTY'], key=lambda o: o.name) if _rc else []
        if len(_ro) >= 8:
            print(f"  [轴覆盖] L 由 LM_R {len(_ro)} 点绕 a={_AXIS_OVR*1000:+.4f}mm 镜像生成(不读 LM_L)")
            pts = np.array([[2.0 * _AXIS_OVR - o.location.x,
                             surface_y(2.0 * _AXIS_OVR - o.location.x, o.location.z),
                             o.location.z] for o in _ro])
        else:
            print(f"  [轴覆盖] LM_R 点不足({len(_ro)}) → 回退按 LM_L 读")
            pts = np.array([[o.location.x, surface_y(o.location.x, o.location.z), o.location.z] for o in objs])
    else:
        pts = np.array([[o.location.x, surface_y(o.location.x, o.location.z), o.location.z] for o in objs])
    # v46e: Catmull-Rom样条加密(消除12点分段线性折线导致的M形折角).
    # 根因: load_eyelid_contour用线性插值加密12→72点, 折角被保留→径向投影→ring0 M形.
    # Catmull-Rom通过所有控制点且切向连续, 消除折角.
    N = len(pts)
    # 弧长参数化, 确定每段输出点数
    seg_len = [np.linalg.norm(pts[(i+1)%N]-pts[i]) for i in range(N)]
    total = sum(seg_len)
    n_out = 72  # 输出72点, 与load_eyelid_contour的n_points一致
    out = []
    for k in range(n_out):
        target = total * k / n_out
        acc = 0.0
        for i in range(N):
            s = seg_len[i]
            if acc + s >= target:
                t = (target - acc) / s if s > 1e-9 else 0.0
                p0 = pts[(i-1)%N]; p1 = pts[i]; p2 = pts[(i+1)%N]; p3 = pts[(i+2)%N]
                t2 = t*t; t3 = t2*t
                pt = 0.5 * ((2*p1) + (-p0+p2)*t + (2*p0-5*p1+4*p2-p3)*t2 + (-p0+3*p1-3*p2+p3)*t3)
                out.append(pt)
                break
            acc += s
    pts = np.array(out)
    w = (pts[:,0].max() - pts[:,0].min()) * 1000
    h = (pts[:,2].max() - pts[:,2].min()) * 1000
    center = pts.mean(axis=0).tolist()
    result[side] = {"rim_3d": [list(map(float, p)) for p in pts],
                    "width_mm": round(float(w), 3), "height_mm": round(float(h), 3),
                    "aspect": round(float(w/h), 3) if h > 0 else 0,
                    "center": center, "source": "manual_markers"}
    print(f"{side}: {len(pts)}点, 宽{w:.1f}mm 高{h:.1f}mm 中心z={center[2]:.4f}")

json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved:", OUT)