"""debug: 对原始高模眼区鼓包做球面拟合, 找出雕塑时的"真实眼球"球心与半径
方法: 取3DDFA中心xz附近16mm内、且朝前(y<眼带平面)的顶点, 最小二乘球拟合"""
import bpy, sys, os
import numpy as np
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import DDFA_JSON
from eye_socket_config import IN_BLEND as REPAIR_BLEND

bpy.ops.wm.open_mainfile(filepath=REPAIR_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
mesh = obj.data
nv = len(mesh.vertices)
V = np.empty(nv*3, dtype=np.float32)
mesh.vertices.foreach_get("co", V)
V = V.reshape(nv, 3).astype(np.float64)

d = json.load(open(DDFA_JSON, encoding="utf-8"))

def fit_sphere(P):
    """最小二乘球拟合: minimize sum(|p-c|^2 - r^2)^2 via linear solve"""
    A = np.hstack([2*P, np.ones((len(P),1))])
    b = (P**2).sum(1)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    c = sol[:3]
    r = np.sqrt(sol[3] + (c**2).sum())
    return c, r

for side, key in [("L","L"),("R","R")]:
    c3 = np.array(d[key]["center_3d"], dtype=np.float64)
    print(f"=== {side} ===  3DDFA surface point: {np.round(c3,4)}")
    dx = V[:,0]-c3[0]; dz = V[:,2]-c3[2]
    r_xz = np.sqrt(dx*dx + dz*dz)
    # 候选: xz距中心<16mm, 且朝前(y < c3.y+2mm, 即鼓包表面)
    cand = (r_xz < 0.016) & (V[:,1] < c3[1] + 0.002)
    P = V[cand]
    print(f"  candidates: {len(P)} verts")
    # 迭代拟合: 第一轮全体, 第二轮剔除离群(距拟合球面>3mm)
    c, r = fit_sphere(P)
    dist = np.linalg.norm(P - c, axis=1)
    inl = np.abs(dist - r) < 0.003
    c2, r2 = fit_sphere(P[inl])
    resid = np.abs(np.linalg.norm(P[inl]-c2, axis=1) - r2)
    print(f"  fit(all):  center={np.round(c,4)} r={r*1000:.1f}mm")
    print(f"  fit(inliers={int(inl.sum())}): center={np.round(c2,4)} r={r2*1000:.1f}mm resid_mean={resid.mean()*1000:.2f}mm resid_max={resid.max()*1000:.2f}mm")
    # 球心相对3DDFA表面点的偏移
    off = c2 - c3
    print(f"  center offset from 3DDFA point: dx={off[0]*1000:.1f} dy={off[1]*1000:.1f}(+into head) dz={off[2]*1000:.1f}mm")
    print(f"  => fitted center: ({c2[0]:.4f}, {c2[1]:.4f}, {c2[2]:.4f}), r={r2*1000:.1f}mm")
