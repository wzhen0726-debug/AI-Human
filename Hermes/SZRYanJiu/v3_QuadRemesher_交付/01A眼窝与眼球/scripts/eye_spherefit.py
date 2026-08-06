"""eye_spherefit - 对原始高模眼区鼓包做球面拟合

原始高模的眼睛是"画出来的鼓包"(无独立眼球物体), 眼睑皮肤贴着鼓包球面塑形.
拟合出雕塑时的"虚拟原始眼球"球心与半径, 把GLB眼球放回同一位置 => 眼睑自然包裹.

输入: 01_highpoly_repair.blend + 3DDFA眼中心(表面交点, 作为拟合种子)
输出: fit结果dict {side: {center, radius}}
"""
import numpy as np

def fit_sphere(P):
    """最小二乘球拟合 (线性化): minimize sum((|p-c|^2 - r^2)^2)"""
    A = np.hstack([2*P, np.ones((len(P),1))])
    b = (P**2).sum(1)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    c = sol[:3]
    r = np.sqrt(sol[3] + (c**2).sum())
    return c, r

def fit_eye_spheres(V, ddfa_centers, xz_radius=0.016, inlier_resid=0.003):
    """对每只眼做两轮球拟合(第二轮剔除离群).
    
    V: (N,3) 原始高模顶点数组
    ddfa_centers: {"L": [x,y,z], "R": [x,y,z]} 3DDFA角膜表面交点
    返回 {"L": {"center": np(3), "radius": float}, "R": {...}}
    """
    out = {}
    for side in ("L", "R"):
        c3 = np.array(ddfa_centers[side], dtype=np.float64)
        dx = V[:,0]-c3[0]; dz = V[:,2]-c3[2]
        cand = (dx*dx + dz*dz < xz_radius**2) & (V[:,1] < c3[1] + 0.002)
        P = V[cand]
        if len(P) < 50:
            out[side] = {"center": c3.copy(), "radius": 0.0145, "n": len(P), "ok": False}
            continue
        c, r = fit_sphere(P)
        dist = np.linalg.norm(P - c, axis=1)
        inl = np.abs(dist - r) < inlier_resid
        c2, r2 = fit_sphere(P[inl])
        resid = np.abs(np.linalg.norm(P[inl]-c2, axis=1) - r2)
        out[side] = {"center": c2, "radius": r2, "n": int(inl.sum()),
                     "resid_mean": float(resid.mean()), "resid_max": float(resid.max()), "ok": True}
    return out
