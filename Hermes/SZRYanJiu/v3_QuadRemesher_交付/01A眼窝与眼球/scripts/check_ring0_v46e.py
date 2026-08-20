"""定量分析v46e模型: 找R眼开放边环(ring0)顶点, 按角度排序, 对比轮廓r(θ).
检测M形折角在哪一环: 计算相邻顶点半径跳变 + 与轮廓的径向偏差.
"""
import bpy, os, sys, math, json, bmesh
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]

ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))
C = np.array(ddfa["R"]["center_3d"])
contour = json.load(open(EYELID_CONTOUR_JSON, encoding="utf-8"))["R"]["rim_3d"]
cpts = np.array([[p[0], p[2]] for p in contour])
# 轮廓 r(θ) 插值表
cth = np.arctan2(cpts[:,1]-C[2], cpts[:,0]-C[0])
cr = np.sqrt((cpts[:,0]-C[0])**2 + (cpts[:,1]-C[2])**2)
order = np.argsort(cth)
cth, cr = cth[order], cr[order]

bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(obj.data)
bm.edges.ensure_lookup_table()
# 开放边环(眼区内)
open_vs = set()
for e in bm.edges:
    if len(e.link_faces) == 1:
        m = (e.verts[0].co + e.verts[1].co)/2
        if abs(m.x-C[0])<0.03 and abs(m.z-C[2])<0.03:
            open_vs.add(e.verts[0].index)
            open_vs.add(e.verts[1].index)
print(f"R眼开放边环顶点: {len(open_vs)}")

# 按角度排序
verts = []
for vi in open_vs:
    v = bm.verts[vi]
    dx = v.co.x-C[0]; dz = v.co.z-C[2]
    th = math.atan2(dz, dx)
    r = math.sqrt(dx*dx+dz*dz)
    verts.append((th, r, v.co.y))
verts.sort()
verts = np.array(verts)

def r_at(theta):
    tt = np.concatenate([cth, cth+2*np.pi]); rr = np.concatenate([cr, cr])
    if theta < cth[0]: theta += 2*np.pi
    return np.interp(theta, tt, rr)

# 径向偏差 + 相邻跳变
devs = []
jumps = []
for i in range(len(verts)):
    th, r, y = verts[i]
    rt = r_at(th)
    devs.append((r-rt)*1000)
    th2, r2, _ = verts[(i+1)%len(verts)]
    jumps.append(abs(r2-r)*1000)
devs = np.array(devs); jumps = np.array(jumps)
print(f"径向偏差(vs轮廓): avg={np.abs(devs).mean():.2f}mm max={np.abs(devs).max():.2f}mm")
print(f"相邻半径跳变: avg={jumps.mean():.2f}mm max={jumps.max():.2f}mm")

# 找上弧(z > C.z+6mm)的最大偏差和跳变点
upper = verts[:,2]*1000 > (C[2]+0.006)*1000
print(f"\n上弧顶点: {upper.sum()}/{len(verts)}")
for i in np.where(upper)[0]:
    th, r, y = verts[i]
    rt = r_at(th)
    d = (r-rt)*1000
    if abs(d) > 1.0:
        print(f"  上弧偏差>1mm: θ={math.degrees(th):.0f}° r={r*1000:.1f}mm 偏差={d:+.1f}mm")