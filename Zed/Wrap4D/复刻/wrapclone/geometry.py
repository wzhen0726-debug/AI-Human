"""几何数学工具: RBF 变形场、Umeyama 相似变换、网格图拉普拉斯."""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.spatial.distance import cdist


class RBFDeformer:
    """基于控制点的 RBF(薄板样条)三维变形场.

    给定源控制点 P 和目标控制点 Q, 求解插值函数 f 使 f(p_i) = q_i,
    然后可将 f 作用于任意点集, 得到平滑变形.
    """

    def __init__(self, kernel: str = "thin_plate", smooth: float = 0.0):
        self.kernel = kernel
        self.smooth = float(smooth)
        self._src: np.ndarray | None = None
        self._w: np.ndarray | None = None
        self._affine: np.ndarray | None = None

    def _phi(self, r: np.ndarray) -> np.ndarray:
        if self.kernel == "thin_plate":
            return r  # 三维双调和核 phi(r) = |r|
        if self.kernel == "cubic":
            return r ** 3
        if self.kernel == "quintic":
            return np.where(r < 1.0, (1.0 - r) ** 5, 0.0)
        raise ValueError(f"未知核函数: {self.kernel}")

    def fit(self, src_points: np.ndarray, dst_points: np.ndarray) -> "RBFDeformer":
        src = np.asarray(src_points, dtype=np.float64)
        dst = np.asarray(dst_points, dtype=np.float64)
        assert src.shape == dst.shape and src.ndim == 2 and src.shape[1] == 3
        n = len(src)
        if n < 4:
            raise ValueError("RBF 至少需要 4 个控制点")
        K = self._phi(cdist(src, src))
        K += self.smooth * np.eye(n)
        P = np.hstack([src, np.ones((n, 1))])
        A = np.zeros((n + 4, n + 4))
        A[:n, :n] = K
        A[:n, n:] = P
        A[n:, :n] = P.T
        Y = np.zeros((n + 4, 3))
        Y[:n] = dst
        # 控制点重复/近重复时矩阵奇异: 逐步加大正则, 最终回退 lstsq
        scale = max(float(np.abs(K).max()), 1e-12)
        coef = None
        for eps in (0.0, 1e-10, 1e-8, 1e-6, 1e-4):
            try:
                A_reg = A.copy()
                A_reg[:n, :n] += eps * scale * np.eye(n)
                coef = np.linalg.solve(A_reg, Y)
                break
            except np.linalg.LinAlgError:
                continue
        if coef is None:
            coef = np.linalg.lstsq(A, Y, rcond=None)[0]
        self._src = src
        self._w = coef[:n]
        self._affine = coef[n:]
        return self

    def __call__(self, points: np.ndarray) -> np.ndarray:
        if self._src is None:
            raise RuntimeError("请先调用 fit()")
        pts = np.asarray(points, dtype=np.float64)
        K = self._phi(cdist(pts, self._src))
        P = np.hstack([pts, np.ones((len(pts), 1))])
        return K @ self._w + P @ self._affine


def umeyama(src: np.ndarray, dst: np.ndarray, with_scale: bool = True):
    """相似变换估计: 返回 (R, t, s) 使 dst ~= s * R @ src + t."""
    src = np.asarray(src, dtype=np.float64)
    dst = np.asarray(dst, dtype=np.float64)
    mu_s, mu_d = src.mean(axis=0), dst.mean(axis=0)
    X, Y = src - mu_s, dst - mu_d
    C = (Y.T @ X) / len(src)
    U, D, Vt = np.linalg.svd(C)
    S = np.eye(3)
    if np.linalg.det(U @ Vt) < 0:
        S[2, 2] = -1.0
    R = U @ S @ Vt
    s = 1.0
    if with_scale:
        var = (X ** 2).sum() / len(src)
        if var > 1e-12:
            s = float(np.trace(np.diag(D) @ S) / var)
    t = mu_d - s * (R @ mu_s)
    return R, t, s


def apply_transform(points: np.ndarray, R, t, s) -> np.ndarray:
    return s * (np.asarray(points, dtype=np.float64) @ R.T) + t


def build_graph_laplacian(n_vertices: int, faces: np.ndarray) -> sp.csr_matrix:
    """由三角面片构建网格图拉普拉斯矩阵 L = D - W."""
    faces = np.asarray(faces)
    edges = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = np.sort(edges, axis=1)
    edges = np.unique(edges, axis=0)
    i, j = edges[:, 0], edges[:, 1]
    data = np.ones(len(edges))
    W = sp.coo_matrix((data, (i, j)), shape=(n_vertices, n_vertices))
    W = (W + W.T).tocsr()
    deg = np.asarray(W.sum(axis=1)).ravel()
    return (sp.diags(deg) - W).tocsr()
