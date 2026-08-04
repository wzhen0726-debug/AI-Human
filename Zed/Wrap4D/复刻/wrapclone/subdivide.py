"""SubdivideGeom: 中点细分 (对标 Wrap 的 SubdivideGeom 节点).

保留 UV(线性插值)与 obj_data 索引结构; 返回父顶点映射, 供两步包裹法把
遮罩/控制点从粗网格传递到细分网格 (对齐 Wrap 的 WrappingInTwoSteps 流程).
"""

from __future__ import annotations

import numpy as np
import trimesh

from .mesh_io import ObjData


def subdivide_mesh(mesh: trimesh.Trimesh, n_subdivisions: int = 1):
    """中点细分. 返回 (新网格, parent_map)
    parent_map[j] = (a, b): 新顶点 j 来自旧顶点 a(若 a==b)或旧边 (a,b) 的中点.
    """
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    data = mesh.metadata.get("obj_data")
    uvs = data.uvs if (data is not None and len(data.uvs) > 0) else None
    fuv = data.face_uvs if data is not None else None
    # UV 展开到每顶点(取首次出现): 细分插值需要顶点级 UV
    if uvs is not None and fuv is not None and (fuv >= 0).all():
        vuv = np.zeros((len(verts), 2))
        seen = np.zeros(len(verts), dtype=bool)
        for f_i, f in enumerate(faces):
            for k in range(3):
                if not seen[f[k]]:
                    vuv[f[k]] = uvs[fuv[f_i][k]]
                    seen[f[k]] = True
    else:
        vuv = None

    parent = [ (i, i) for i in range(len(verts)) ]

    for _ in range(n_subdivisions):
        nv = len(verts)
        edge_mid: dict[tuple[int, int], int] = {}
        new_verts = list(verts)
        new_vuv = list(vuv) if vuv is not None else None
        new_parent = list(parent)

        def midpoint(a, b):
            key = (a, b) if a < b else (b, a)
            if key in edge_mid:
                return edge_mid[key]
            idx = len(new_verts)
            new_verts.append((verts[a] + verts[b]) * 0.5)
            if new_vuv is not None:
                new_vuv.append((vuv[a] + vuv[b]) * 0.5)
            new_parent.append((a, b))
            edge_mid[key] = idx
            return idx

        new_faces = []
        for a, b, c in faces:
            ab = midpoint(a, b)
            bc = midpoint(b, c)
            ca = midpoint(c, a)
            new_faces += [[a, ab, ca], [ab, b, bc], [ca, bc, c], [ab, bc, ca]]
        verts = np.asarray(new_verts, dtype=np.float64)
        faces = np.asarray(new_faces, dtype=np.int64)
        if new_vuv is not None:
            vuv = np.asarray(new_vuv, dtype=np.float64)
        parent = new_parent

    out = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    if data is not None:
        nd = ObjData()
        nd.vertices = verts
        nd.faces = faces
        nd.face_normals = np.full((len(faces), 3), -1, dtype=np.int64)
        if vuv is not None:
            nd.uvs = vuv
            nd.face_uvs = faces.copy()
        else:
            nd.uvs = np.empty((0, 2))
            nd.face_uvs = np.full((len(faces), 3), -1, dtype=np.int64)
        out.metadata["obj_data"] = nd
    try:
        out.visual = mesh.visual.copy()
    except Exception:
        pass
    return out, np.asarray(parent, dtype=np.int64)


def transfer_mask(parent: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """遮罩(引擎语义: 1=参与, 0=屏蔽)传递到细分网格: 中点取两端最小值(保守屏蔽)."""
    mask = np.asarray(mask, dtype=np.float64)
    a, b = parent[:, 0], parent[:, 1]
    return np.minimum(mask[a], mask[b])


def transfer_painted(parent: np.ndarray, painted: np.ndarray) -> np.ndarray:
    """涂抹集(bool)传递: 中点任一父顶点被涂抹即被涂抹."""
    a, b = parent[:, 0], parent[:, 1]
    return painted[a] | painted[b]


def nearest_vertex_map(mesh: trimesh.Trimesh, points: np.ndarray) -> np.ndarray:
    """每个点找细分网格最近顶点索引 (控制点 vid 传递)."""
    verts = np.asarray(mesh.vertices)
    return np.array([int(np.argmin(np.linalg.norm(verts - p, axis=1))) for p in points],
                    dtype=np.int64)
