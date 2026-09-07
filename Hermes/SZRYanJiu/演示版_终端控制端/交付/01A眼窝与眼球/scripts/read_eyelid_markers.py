"""读取用户GUI调好的R眼标记点, 镜像到L, 生成新眼裂轮廓JSON.

v45: 只投影y(保留用户打点的x,z), 不改变形状. 镜像=x取负.
"""
import bpy, os, sys, json
import numpy as np
from mathutils import Vector, kdtree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

MARKERS = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01A_markers_eyelid.blend")
OUT = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")

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
for side in ['L', 'R']:
    coll = bpy.data.collections.get(f"LM_{side}")
    if not coll:
        print(f"!! 找不到集合 LM_{side}")
        continue
    objs = sorted([o for o in coll.objects], key=lambda o: o.name)
    for o in objs:
        print(f"  {o.name}: loc=({o.location.x:.4f},{o.location.y:.4f},{o.location.z:.4f})")
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