"""Brush 节点: 顶点编辑笔刷 (对标 Wrap 的 Brush 节点).

官方参数语义(扒自 Gallery 工程): radius=14, strength=25, opacity,
falloff=50, symmetry, useGeodesicDistance, minFactor/maxFactor.

实现三种笔刷:
  move      移动(沿拖动方向位移, 对标 brushType 移动类)
  smooth    平滑(局部 Laplacian)
  attract   吸附到扫描表面(向最近表面点靠拢, 修整局部贴合)
衰减: w = (1 - d/r)^(falloff/50), 中心1 -> 边缘0.
对称: 以世界 x=0 平面镜像 (symmetry=1 为 X 对称).
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import scipy.sparse.csgraph as csgraph


def _falloff_weights(dist: np.ndarray, radius: float, falloff: float) -> np.ndarray:
    t = np.clip(dist / max(radius, 1e-12), 0.0, 1.0)
    power = max(falloff, 5.0) / 50.0
    return (1.0 - t) ** power


def _geodesic_dist(mesh_vertices, faces, center_vid: int, radius: float) -> np.ndarray:
    """以 center_vid 为源, 在 radius 包围盒内的测地(沿边最短路径)距离."""
    from .geometry import build_graph_laplacian
    n = len(mesh_vertices)
    verts = np.asarray(mesh_vertices)
    box = np.abs(verts - verts[center_vid]).max(axis=1) < radius * 1.5
    idx = np.where(box)[0]
    if len(idx) == 0:
        return np.full(n, np.inf)
    edges = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    mask = box[edges].all(axis=1)
    edges = edges[mask]
    if len(edges) == 0:
        return np.full(n, np.inf)
    elen = np.linalg.norm(verts[edges[:, 0]] - verts[edges[:, 1]], axis=1)
    W = sp.coo_matrix((elen, (edges[:, 0], edges[:, 1])), shape=(n, n))
    W = (W + W.T).tocsr()
    dist = csgraph.dijkstra(W, indices=center_vid)
    return dist


class MeshBrush:
    """对一个网格施加笔刷编辑."""

    def __init__(self, mesh):
        self.mesh = mesh

    def _dist(self, center, center_vid, radius, geodesic):
        verts = np.asarray(self.mesh.vertices)
        if geodesic and center_vid is not None and len(self.mesh.faces) > 0:
            return _geodesic_dist(verts, np.asarray(self.mesh.faces), center_vid, radius)
        return np.linalg.norm(verts - center, axis=1)

    def stroke_move(self, center, delta, radius=14.0, strength=25.0, falloff=50.0,
                    geodesic=False, symmetry=False):
        """移动笔刷: center 附近顶点沿 delta 位移."""
        self._apply(center, delta * strength / 100.0, radius, falloff, geodesic, symmetry,
                    mode="move")

    def stroke_smooth(self, center, radius=14.0, strength=25.0, falloff=50.0,
                      geodesic=False, symmetry=False):
        self._apply(center, None, radius, falloff, geodesic, symmetry, mode="smooth",
                    strength=strength / 100.0)

    def stroke_attract(self, center, target_mesh, radius=14.0, strength=25.0,
                       falloff=50.0, geodesic=False, symmetry=False):
        self._apply(center, None, radius, falloff, geodesic, symmetry, mode="attract",
                    strength=strength / 100.0, target=target_mesh)

    def _apply(self, center, delta, radius, falloff, geodesic, symmetry,
               mode, strength=0.25, target=None):
        center = np.asarray(center, dtype=np.float64)
        centers = [center]
        deltas = [delta]
        if symmetry:
            c2 = center.copy(); c2[0] = -c2[0]
            centers.append(c2)
            if delta is not None:
                d2 = np.asarray(delta, dtype=np.float64).copy(); d2[0] = -d2[0]
                deltas.append(d2)
            else:
                deltas.append(None)
        verts = np.asarray(self.mesh.vertices)
        for c, d in zip(centers, deltas):
            cv = int(np.argmin(np.linalg.norm(verts - c, axis=1)))
            dist = self._dist(c, cv, radius, geodesic)
            w = _falloff_weights(dist, radius, falloff)
            w[dist > radius] = 0.0
            if not w.any():
                continue
            if mode == "move":
                self.mesh.vertices = verts + w[:, None] * d
            elif mode == "smooth":
                self._smooth(w, strength)
            elif mode == "attract" and target is not None:
                self._attract(w, strength, target)
            verts = np.asarray(self.mesh.vertices)

    def _smooth(self, w, strength):
        from .geometry import build_graph_laplacian
        verts = np.asarray(self.mesh.vertices)
        faces = np.asarray(self.mesh.faces)
        L = build_graph_laplacian(len(verts), faces)
        deg = L.diagonal()
        avg = (sp.diags(1.0 / np.maximum(deg, 1e-12)) @ (sp.diags(deg) - L)) @ verts
        self.mesh.vertices = verts + (w * strength)[:, None] * (avg - verts)

    def _attract(self, w, strength, target):
        import trimesh as _t
        verts = np.asarray(self.mesh.vertices)
        sel = w > 0
        if not sel.any():
            return
        closest, _, _ = _t.proximity.closest_point(target, verts[sel])
        newv = verts.copy()
        newv[sel] = verts[sel] + (w[sel] * strength)[:, None] * (closest - verts[sel])
        self.mesh.vertices = newv
