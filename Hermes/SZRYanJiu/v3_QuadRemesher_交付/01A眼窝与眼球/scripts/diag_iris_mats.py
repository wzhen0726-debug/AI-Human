"""诊断: Eye002_L各材质及其面数, 用材质名定位虹膜面片."""
import bpy, os, sys
import numpy as np
import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
eye = bpy.data.objects["Eye002_L"]
print("MATS:")
for i, m in enumerate(eye.data.materials):
    n = sum(1 for p in eye.data.polygons if p.material_index == i)
    print(f"  [{i}] {m.name} faces={n}")
bm = bmesh.new()
bm.from_mesh(eye.data)
bm.transform(eye.matrix_world)
# 各材质的顶点y范围(判断哪个是角膜最前的虹膜盘)
for i, m in enumerate(eye.data.materials):
    pts = [v.co[:] for f in bm.faces if f.material_index == i for v in f.verts]
    if pts:
        a = np.array(pts)
        print(f"  mat[{i}] {m.name}: ymin={a[:,1].min():.4f} z范围={np.ptp(a[:,2]):.4f} x范围={np.ptp(a[:,0]):.4f}")
bm.free()
print("done")
