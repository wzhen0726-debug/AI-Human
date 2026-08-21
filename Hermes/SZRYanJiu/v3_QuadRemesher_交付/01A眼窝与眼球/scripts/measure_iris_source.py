"""在源Eye.blend内直接测Eye_Iris边界圆直径(边界边=只连1个面的边)."""
import bpy, os, sys
import numpy as np
import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye002_config import *

bpy.ops.wm.open_mainfile(filepath=EYE002_BLEND)
for name in ("Eye_Iris", "Eye_Sclera"):
    o = bpy.data.objects.get(name)
    if not o:
        print(f"{name}: NOT FOUND"); continue
    bm = bmesh.new(); bm.from_mesh(o.data)
    bpts = []
    seen = set()
    for e in bm.edges:
        if len(e.link_faces) == 1:
            for v in e.verts:
                if v.index not in seen:
                    seen.add(v.index)
                    bpts.append(v.co[:])
    if not bpts:
        print(f"{name}: 无边界边(封闭壳)")
    else:
        a = np.array(bpts)
        cen = a.mean(axis=0)
        r = np.sqrt((a[:,0]-cen[0])**2 + (a[:,1]-cen[1])**2 + (a[:,2]-cen[2])**2)
        print(f"{name}: 边界点数={len(bpts)} 边界圆半径中位={np.median(r)*1000:.2f}mm → 直径={2*np.median(r)*1000:.2f}mm")
        # 虹膜盘朝向: 边界圆平面法向≈最大方差轴
        print(f"{name}: x范围={np.ptp(a[:,0])*1000:.1f} y范围={np.ptp(a[:,1])*1000:.1f} z范围={np.ptp(a[:,2])*1000:.1f}mm")
    bm.free()
print("done")
