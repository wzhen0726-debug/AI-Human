"""网格加载/保存, 以及 trimesh <-> pyvista 转换.

OBJ 使用自定义解析器, 完整保留 v/vt/vn 索引结构:
- 顶点顺序与文件一致 (Blender 往返无损的关键)
- UV (vt) 与法向 (vn) 随面索引原样保留, 包裹结果导出时不丢失
PLY/STL/OFF 等格式走 trimesh.
"""

from __future__ import annotations

import os

import numpy as np
import trimesh

OBJ_EXTS = {".obj"}


class ObjData:
    """OBJ 文件的完整索引结构."""

    def __init__(self):
        self.vertices = np.empty((0, 3))      # v
        self.uvs = np.empty((0, 2))           # vt
        self.normals = np.empty((0, 3))       # vn
        self.faces = np.empty((0, 3), dtype=np.int64)      # v 索引(三角化)
        self.face_uvs = np.empty((0, 3), dtype=np.int64)   # vt 索引, -1 表示无
        self.face_normals = np.empty((0, 3), dtype=np.int64)

    @property
    def has_uv(self) -> bool:
        return len(self.uvs) > 0 and len(self.face_uvs) == len(self.faces) \
            and (self.face_uvs >= 0).any()


def _parse_face_token(tok: str):
    parts = tok.split("/")
    v = int(parts[0])
    vt = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    vn = int(parts[2]) if len(parts) > 2 and parts[2] else 0
    return v, vt, vn


def _fix_index(i: int, count: int) -> int:
    return i - 1 if i > 0 else count + i


def load_obj(path: str) -> ObjData:
    data = ObjData()
    verts, uvs, norms = [], [], []
    f_v, f_vt, f_vn = [], [], []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("v "):
                verts.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("vt "):
                uvs.append([float(x) for x in line.split()[1:3]])
            elif line.startswith("vn "):
                norms.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("f "):
                toks = line.split()[1:]
                parsed = [_parse_face_token(t) for t in toks]
                # fan 三角化 ngon
                for k in range(1, len(parsed) - 1):
                    tri = [parsed[0], parsed[k], parsed[k + 1]]
                    f_v.append([t[0] for t in tri])
                    f_vt.append([t[1] for t in tri])
                    f_vn.append([t[2] for t in tri])
    data.vertices = np.array(verts, dtype=np.float64).reshape(-1, 3)
    data.uvs = np.array(uvs, dtype=np.float64).reshape(-1, 2) if uvs else np.empty((0, 2))
    data.normals = np.array(norms, dtype=np.float64).reshape(-1, 3) if norms else np.empty((0, 3))
    nv, nvt, nvn = len(data.vertices), len(data.uvs), len(data.normals)
    data.faces = np.array([[_fix_index(i, nv) for i in f] for f in f_v], dtype=np.int64)
    data.face_uvs = np.array([[-1 if i == 0 else _fix_index(i, nvt) for i in f] for f in f_vt],
                             dtype=np.int64)
    data.face_normals = np.array([[-1 if i == 0 else _fix_index(i, nvn) for i in f] for f in f_vn],
                                 dtype=np.int64)
    return data


def save_obj(vertices, obj_data: ObjData | None, path: str,
             extra_uvs=None, extra_faces=None):
    """写出 OBJ. 若提供 obj_data 则沿用其 vt/vn/面索引, 仅替换 v 坐标;
    否则用 extra_uvs(每顶点)/extra_faces 写出."""
    vertices = np.asarray(vertices, dtype=np.float64)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# PyWrap exported\n")
        for v in vertices:
            f.write(f"v {v[0]:.7g} {v[1]:.7g} {v[2]:.7g}\n")
        if obj_data is not None:
            for vt in obj_data.uvs:
                f.write(f"vt {vt[0]:.7g} {vt[1]:.7g}\n")
            for vn in obj_data.normals:
                f.write(f"vn {vn[0]:.7g} {vn[1]:.7g} {vn[2]:.7g}\n")
            for i, face in enumerate(obj_data.faces):
                toks = []
                for k in range(3):
                    vi = face[k] + 1
                    vti = obj_data.face_uvs[i][k]
                    vni = obj_data.face_normals[i][k]
                    if vti >= 0 and vni >= 0:
                        toks.append(f"{vi}/{vti+1}/{vni+1}")
                    elif vti >= 0:
                        toks.append(f"{vi}/{vti+1}")
                    elif vni >= 0:
                        toks.append(f"{vi}//{vni+1}")
                    else:
                        toks.append(str(vi))
                f.write("f " + " ".join(toks) + "\n")
        elif extra_faces is not None:
            has_uv = extra_uvs is not None and len(extra_uvs) > 0
            if has_uv:
                for vt in extra_uvs:
                    f.write(f"vt {vt[0]:.7g} {vt[1]:.7g}\n")
            for face in extra_faces:
                if has_uv:
                    f.write("f " + " ".join(f"{i+1}/{i+1}" for i in face) + "\n")
                else:
                    f.write("f " + " ".join(str(i + 1) for i in face) + "\n")


def load_mesh(path: str, y_up_to_z_up: bool = False) -> trimesh.Trimesh:
    ext = os.path.splitext(path)[1].lower()
    if ext in OBJ_EXTS:
        data = load_obj(path)
        mesh = trimesh.Trimesh(vertices=data.vertices, faces=data.faces, process=False)
        mesh.metadata["obj_data"] = data
    else:
        mesh = trimesh.load(path, force="mesh", process=False)
        if mesh.is_empty:
            raise ValueError(f"无法从文件读取网格: {path}")
    # glTF/GLB 规范恒为 Y-up, 自动转到 Z-up 视口约定
    if ext in (".glb", ".gltf"):
        y_up_to_z_up = True
    if y_up_to_z_up:
        rotate_yup_to_zup(mesh)
    return mesh


def rotate_yup_to_zup(mesh: trimesh.Trimesh):
    """Y-up 模型转 Z-up: (x,y,z) -> (x,z,-y), 同步处理 obj_data 的顶点与法向."""
    R = np.array([[1.0, 0.0, 0.0],
                  [0.0, 0.0, 1.0],
                  [0.0, -1.0, 0.0]])
    M = np.eye(4)
    M[:3, :3] = R
    mesh.apply_transform(M)
    data = mesh.metadata.get("obj_data")
    if data is not None:
        data.vertices = np.asarray(mesh.vertices)
        if len(data.normals) > 0:
            data.normals = data.normals @ R.T


def save_mesh(mesh: trimesh.Trimesh, path: str):
    ext = os.path.splitext(path)[1].lower()
    if ext in OBJ_EXTS:
        obj_data = mesh.metadata.get("obj_data")
        if obj_data is not None:
            save_obj(mesh.vertices, obj_data, path)
        else:
            # GLB/PLY 等来源: 尝试保留每顶点 UV
            uv = getattr(mesh.visual, "uv", None)
            has_uv = uv is not None and len(uv) == len(mesh.vertices)
            save_obj(mesh.vertices, None, path,
                     extra_uvs=np.asarray(uv) if has_uv else None,
                     extra_faces=np.asarray(mesh.faces))
        return
    mesh.export(path)


def mesh_stats(mesh: trimesh.Trimesh) -> str:
    has_uv = "obj_data" in mesh.metadata and mesh.metadata["obj_data"].has_uv
    return f"顶点 {len(mesh.vertices)} / 面片 {len(mesh.faces)}" + (" / 含UV" if has_uv else "")


def to_polydata(mesh: trimesh.Trimesh):
    import pyvista as pv
    faces = np.hstack([
        np.full((len(mesh.faces), 1), 3, dtype=np.int64),
        np.asarray(mesh.faces, dtype=np.int64),
    ])
    return pv.PolyData(np.asarray(mesh.vertices, dtype=np.float64), faces)


def nearest_vertex(mesh: trimesh.Trimesh, point) -> int:
    d = np.linalg.norm(np.asarray(mesh.vertices) - np.asarray(point), axis=1)
    return int(np.argmin(d))
