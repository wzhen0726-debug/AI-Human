"""包裹引擎 (逆向对齐 Wrap 2025 Wrapping/FastWrapping 节点).

官方参数结构(扒自 Gallery 工程文件默认值):
    globalControlPointsWeightInitial/Final = 10      控制点权重(软约束)
    globalPoint2PlaneFittingWeight         = 1       点对面拟合权重(主导)
    globalPoint2PointFittingWeight         = 0.1     点对点拟合权重
    globalSmoothWeightMax                  = 1       平滑权重(初)
    globalSmoothWeightMin                  = 0.05    平滑权重(末)
    minCosBetweenNormals                   = 0.65    法向兼容阈值
    nICPIterations                         = 5       外层ICP迭代(更新对应)
    nOptimizationIterations                = 20      内层优化迭代(固定对应求解)
    samplingMin/Max                        = 0.2/5   对应搜索半径倍率(随迭代递增)
    maxDp/minDp                            = 0.01/0.002  位移钳制/收敛阈值
    polygons                               = []      参与包裹的面片集(SelectPolygons 白名单)

流程: RBF/相似变换初对齐 -> 外层ICP(重找对应+扩半径) x 内层优化(平滑衰减求解)
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve, cg
from scipy.spatial import cKDTree
import trimesh

from .geometry import RBFDeformer, umeyama, apply_transform, build_graph_laplacian

try:
    import rtree  # noqa: F401
    HAS_RTREE = True
except ImportError:
    HAS_RTREE = False


class WrapResult:
    def __init__(self, mesh: trimesh.Trimesh, stats: dict):
        self.mesh = mesh
        self.stats = stats


def _sample_target_surface(target: trimesh.Trimesh, n_samples: int):
    pts = [np.asarray(target.vertices, dtype=np.float64)]
    nrm = [np.asarray(target.vertex_normals, dtype=np.float64)]
    try:
        if n_samples > 0 and len(target.faces) > 0:
            samples, face_idx = trimesh.sample.sample_surface(target, n_samples)
            pts.append(np.asarray(samples, dtype=np.float64))
            nrm.append(np.asarray(target.face_normals[face_idx], dtype=np.float64))
    except Exception:
        pass
    return np.vstack(pts), np.vstack(nrm)


def _closest_on_surface(target: trimesh.Trimesh, points: np.ndarray):
    """精确最近表面点 + 重心插值法向. 返回 (点, 法向, 距离)."""
    closest, dist, tid = trimesh.proximity.closest_point(target, points)
    tris = target.triangles[tid]
    bary = trimesh.triangles.points_to_barycentric(tris, closest)
    vnorm = np.asarray(target.vertex_normals)[np.asarray(target.faces)[tid]]
    n = np.einsum("ij,ijk->ik", bary, vnorm)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = n / np.maximum(ln, 1e-12)
    return closest, n, dist


class Wrapper:
    def __init__(self, base: trimesh.Trimesh, target: trimesh.Trimesh):
        self.base = base
        self.target = target
        L = build_graph_laplacian(len(base.vertices), base.faces)
        mean_deg = float(L.diagonal().mean()) or 1.0
        Ln = (L / mean_deg).tocsr()
        self._LtL = (Ln.T @ Ln).tocsr()
        self._LtL3 = sp.kron(self._LtL, sp.eye(3, format="csr")).tocsr()
        # 基础网格平均边长 (对应搜索半径的基准, 对齐 Wrap sampling 倍率语义)
        e = np.asarray(base.vertices)[np.asarray(base.faces)]
        self._mean_edge = float(np.linalg.norm(e[:, 0] - e[:, 1], axis=1).mean())
        _ = target.vertex_normals
        self._samples, self._sample_normals = (None, None)

    # ---------------- 初对齐 ----------------
    def initial_align(self, src_ctrl, dst_ctrl, use_rbf: bool = True) -> np.ndarray:
        verts = np.asarray(self.base.vertices, dtype=np.float64)
        if src_ctrl is None or dst_ctrl is None or len(src_ctrl) < 3:
            return verts
        src_ctrl = np.asarray(src_ctrl, dtype=np.float64)
        dst_ctrl = np.asarray(dst_ctrl, dtype=np.float64)
        if use_rbf and len(src_ctrl) >= 4:
            return RBFDeformer().fit(src_ctrl, dst_ctrl)(verts)
        R, t, s = umeyama(src_ctrl, dst_ctrl, with_scale=True)
        return apply_transform(verts, R, t, s)

    # ---------------- 对应搜索 ----------------
    def _correspondences(self, verts, mode, target_samples):
        if mode == "surface" and HAS_RTREE:
            return _closest_on_surface(self.target, verts)
        if self._samples is None:
            self._samples, self._sample_normals = _sample_target_surface(
                self.target, target_samples)
        dist, idx = cKDTree(self._samples).query(verts, workers=-1)
        return self._samples[idx], self._sample_normals[idx], dist

    # ---------------- 求解 ----------------
    @staticmethod
    def _solve_spd(A, b):
        diag = A.diagonal()
        M = sp.diags(1.0 / np.maximum(np.abs(diag), 1e-12))
        x, info = cg(A, b, M=M, rtol=1e-6, maxiter=500)
        if info != 0:
            x = spsolve(A.tocsc(), b)
        return x

    def _solve_step(self, verts, corr_pts, corr_nrm, w,
                    p2p_w, p2plane_w, lam):
        """数据项: w*p2p*||d-r||^2 + w*p2plane*(n·(d-r))^2; 平滑项: lam*||L d||^2."""
        n = len(verts)
        r = corr_pts - verts
        if p2plane_w > 0.0:
            a = w * p2p_w
            bcoef = w * p2plane_w
            nnT = corr_nrm[:, :, None] * corr_nrm[:, None, :]
            D = a[:, None, None] * np.eye(3)[None] + bcoef[:, None, None] * nnT
            b = a[:, None] * r + bcoef[:, None] * corr_nrm * \
                np.einsum("ij,ij->i", corr_nrm, r)[:, None]
            Dflat = D.reshape(n, 9)
            ridx = np.repeat(np.arange(n)[:, None] * 3 + np.arange(3)[None, :], 3, axis=1).ravel()
            cidx = np.tile(np.arange(n)[:, None] * 3 + np.arange(3)[None, :], (1, 3)).ravel()
            A_data = sp.csr_matrix((Dflat.ravel(), (ridx, cidx)), shape=(3 * n, 3 * n))
            A = (A_data + lam * self._LtL3).tocsr()
            d = self._solve_spd(A, b.ravel())
            return d.reshape(n, 3)
        a = w * p2p_w
        A = (sp.diags(a) + lam * self._LtL).tocsc()
        rhs = a[:, None] * r
        disp = np.empty_like(verts)
        for c in range(3):
            disp[:, c] = self._solve_spd(A, rhs[:, c])
        return disp

    # ---------------- 主流程 ----------------
    def wrap(self,
             src_ctrl: np.ndarray | None = None,
             dst_ctrl: np.ndarray | None = None,
             src_ctrl_ids: np.ndarray | None = None,
             mask: np.ndarray | None = None,
             # ---- Wrap 官方参数 ----
             n_icp_iterations: int = 5,
             n_optimization_iterations: int = 20,
             smooth_weight_max: float = 1.0,
             smooth_weight_min: float = 0.05,
             point2plane_weight: float = 1.0,
             point2point_weight: float = 0.1,
             control_points_weight: float = 10.0,
             min_cos_normals: float = 0.65,
             sampling_min: float = 0.2,
             sampling_max: float = 5.0,
             min_dp: float = 0.002,
             max_dp: float = 0.01,
             # ---- 实现细节参数 ----
             correspondence: str = "surface",
             target_samples: int = 80000,
             use_rbf_init: bool = True,
             lock_control_points: bool = False,
             trim_fraction: float = 0.0,
             final_snap: bool = True,
             progress_cb=None) -> WrapResult:
        """执行包裹 (Wrap 官方迭代结构).

        外层 ICP (更新对应, 搜索半径 sampling_min→max × 平均边长 递增) x
        内层优化 (固定对应, 平滑权重 smooth_weight_max→min 几何衰减).
        mean|d| < min_dp×包围盒 时提前收敛; 单步位移钳制 max_dp×包围盒.
        """
        verts = self.initial_align(src_ctrl, dst_ctrl, use_rbf=use_rbf_init)
        n = len(verts)
        base_faces = np.asarray(self.base.faces)

        if mask is None:
            mask_vec = np.ones(n)
        else:
            mask_vec = np.clip(np.asarray(mask, dtype=np.float64).ravel(), 0.0, 1.0)
            assert len(mask_vec) == n, "遮罩长度必须等于基础网格顶点数"

        tgt_diag = float(np.linalg.norm(self.target.bounds[1] - self.target.bounds[0])) \
            if self.target.bounds is not None else 1.0
        clamp = max_dp * tgt_diag
        conv_thresh = min_dp * tgt_diag

        ctrl_ids = None
        if src_ctrl_ids is not None and dst_ctrl is not None \
                and len(src_ctrl_ids) == len(dst_ctrl):
            ctrl_ids = np.asarray(src_ctrl_ids, dtype=np.int64)
            ctrl_ids = ctrl_ids[(ctrl_ids >= 0) & (ctrl_ids < n)]
            if len(ctrl_ids) == 0:
                ctrl_ids = None

        total = max(1, n_icp_iterations * n_optimization_iterations)
        step = 0
        mean_d = 0.0

        for icp in range(n_icp_iterations):
            # 搜索半径随 ICP 进程递增 (对齐 Wrap samplingMin->Max 语义)
            if n_icp_iterations > 1:
                t_icp = icp / (n_icp_iterations - 1)
            else:
                t_icp = 1.0
            radius_mult = sampling_min + (sampling_max - sampling_min) * t_icp
            max_dist = max(radius_mult * self._mean_edge, 1e-9)

            cp, cn, dist = self._correspondences(verts, correspondence, target_samples)
            mean_d = float(np.mean(dist))
            w = (dist < max_dist).astype(np.float64)
            if trim_fraction > 0:
                thresh = np.percentile(dist, 100.0 * (1.0 - trim_fraction))
                w *= (dist <= thresh).astype(np.float64)
            if min_cos_normals > -1.0:
                vn = np.asarray(trimesh.Trimesh(
                    verts, base_faces, process=False).vertex_normals)
                w *= (np.einsum("ij,ij->i", vn, cn) > min_cos_normals).astype(np.float64)
            w *= mask_vec
            # 控制点: 目标锁定 + 软权重 (Wrap globalControlPointsWeight=10)
            if ctrl_ids is not None:
                cp = cp.copy()
                cp[ctrl_ids] = dst_ctrl
                w = w.copy()
                w[ctrl_ids] = np.maximum(w[ctrl_ids], control_points_weight)
            if (w > 0).sum() < 10:
                w = np.ones(n) * mask_vec
                if ctrl_ids is not None:
                    w[ctrl_ids] = np.maximum(w[ctrl_ids], control_points_weight)

            for _ in range(n_optimization_iterations):
                t = step / max(1, total - 1)
                # 平滑权重几何衰减 max -> min
                lam = float(np.exp(np.log(smooth_weight_max) +
                                   (np.log(smooth_weight_min) - np.log(smooth_weight_max)) * t))
                disp = self._solve_step(verts, cp, cn, w,
                                        point2point_weight, point2plane_weight, lam)
                dn = np.linalg.norm(disp, axis=1)
                scale = np.minimum(1.0, clamp / np.maximum(dn, 1e-12))
                disp = disp * scale[:, None]
                verts = verts + disp
                if lock_control_points and ctrl_ids is not None:
                    verts[ctrl_ids] = dst_ctrl
                step += 1
                md = float(dn.mean())
                if progress_cb is not None:
                    progress_cb(step, total, mean_d)
                if md < conv_thresh:
                    break
            if md < conv_thresh:
                break

        if final_snap:
            lam = smooth_weight_min * 0.1
            for _ in range(2):
                cp, cn, dist = self._correspondences(verts, correspondence, target_samples)
                w = mask_vec.copy()
                if ctrl_ids is not None:
                    w[ctrl_ids] = np.maximum(w[ctrl_ids], control_points_weight)
                    cp = cp.copy(); cp[ctrl_ids] = dst_ctrl
                disp = self._solve_step(verts, cp, cn, w,
                                        point2point_weight, point2plane_weight, lam)
                verts = verts + disp

        wrapped = trimesh.Trimesh(vertices=verts, faces=base_faces, process=False)
        if "obj_data" in self.base.metadata:
            wrapped.metadata["obj_data"] = self.base.metadata["obj_data"]
        try:
            wrapped.visual = self.base.visual.copy()
        except Exception:
            pass

        _, _, fdist = self._correspondences(verts, correspondence, target_samples)
        stats = {
            "mean_dist": float(np.mean(fdist)),
            "median_dist": float(np.median(fdist)),
            "p95_dist": float(np.percentile(fdist, 95)),
            "max_dist": float(np.max(fdist)),
            "masked_vertices": int((mask_vec < 0.5).sum()),
            "steps": step,
        }
        return WrapResult(wrapped, stats)
