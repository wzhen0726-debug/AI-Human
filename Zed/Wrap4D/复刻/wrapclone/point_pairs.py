"""控制点对管理: 增删、查询、JSON 保存/加载."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import numpy as np


@dataclass
class PointPair:
    name: str
    base_pos: list          # [x, y, z]
    target_pos: list
    base_vid: int = -1      # 基础网格最近顶点索引
    target_vid: int = -1    # 目标网格最近顶点索引


class PointPairManager:
    def __init__(self):
        self.pairs: list[PointPair] = []

    def _next_name(self) -> str:
        """取现有最大 P 编号 + 1 (删除末尾点后编号可续上, 中间删除不重号)."""
        maxn = 0
        for p in self.pairs:
            m = re.match(r"^P(\d+)$", p.name)
            if m:
                maxn = max(maxn, int(m.group(1)))
        return f"P{maxn + 1}" if maxn > 0 else f"P{len(self.pairs) + 1}"

    def add(self, base_pos, target_pos, base_vid=-1, target_vid=-1, name=None) -> PointPair:
        name = name or self._next_name()
        pair = PointPair(name=name,
                         base_pos=[float(v) for v in base_pos],
                         target_pos=[float(v) for v in target_pos],
                         base_vid=int(base_vid), target_vid=int(target_vid))
        self.pairs.append(pair)
        return pair

    def remove(self, index: int):
        if 0 <= index < len(self.pairs):
            self.pairs.pop(index)

    def clear(self):
        self.pairs.clear()

    def __len__(self):
        return len(self.pairs)

    def base_points(self) -> np.ndarray:
        return np.array([p.base_pos for p in self.pairs], dtype=np.float64) \
            if self.pairs else np.empty((0, 3))

    def target_points(self) -> np.ndarray:
        return np.array([p.target_pos for p in self.pairs], dtype=np.float64) \
            if self.pairs else np.empty((0, 3))

    def base_vertex_ids(self) -> np.ndarray:
        return np.array([p.base_vid for p in self.pairs], dtype=np.int64) \
            if self.pairs else np.empty((0,), dtype=np.int64)

    def save(self, path: str):
        data = {
            "version": 1,
            "pairs": [
                {"name": p.name, "base": p.base_pos, "target": p.target_pos,
                 "base_vid": p.base_vid, "target_vid": p.target_vid}
                for p in self.pairs
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.clear()
        # 格式2: Blender 桥接插件导出的顶点索引列表
        if "base_vids" in data and "target_vids" in data:
            b_ids, t_ids = data["base_vids"], data["target_vids"]
            names = data.get("names") or [None] * len(b_ids)
            for i, (bv, tv) in enumerate(zip(b_ids, t_ids)):
                self.pairs.append(PointPair(
                    name=names[i] or self._next_name(),
                    base_pos=[0.0, 0.0, 0.0], target_pos=[0.0, 0.0, 0.0],
                    base_vid=int(bv), target_vid=int(tv)))
            return
        # 格式1: 完整坐标点对
        for item in data.get("pairs", []):
            self.pairs.append(PointPair(
                name=item.get("name") or self._next_name(),
                base_pos=[float(v) for v in item["base"]],
                target_pos=[float(v) for v in item["target"]],
                base_vid=int(item.get("base_vid", -1)),
                target_vid=int(item.get("target_vid", -1)),
            ))

    def resolve_positions(self, base_mesh, target_mesh):
        """按顶点索引从网格解析坐标 (vid-only 点对加载后必须调用)."""
        bv = np.asarray(base_mesh.vertices)
        tv = np.asarray(target_mesh.vertices)
        for p in self.pairs:
            if 0 <= p.base_vid < len(bv):
                p.base_pos = [float(x) for x in bv[p.base_vid]]
            if 0 <= p.target_vid < len(tv):
                p.target_pos = [float(x) for x in tv[p.target_vid]]

    @property
    def unresolved(self) -> bool:
        return any(p.base_pos == [0.0, 0.0, 0.0] and p.base_vid >= 0 for p in self.pairs)

    # ---------------- Wrap 官方点格式互通 ----------------
    # Wrap 格式: {"Point00": [triangleInd, u, v], ...}  (三角形索引 + 重心坐标)
    @staticmethod
    def _tri_uv(mesh, pos):
        import trimesh
        closest, _, tid = trimesh.proximity.closest_point(mesh, np.asarray([pos]))
        tri = mesh.triangles[tid[0]]
        bary = trimesh.triangles.points_to_barycentric(tri[None], closest)[0]
        return [int(tid[0]), float(bary[1]), float(bary[2])]

    @staticmethod
    def _pos_of(mesh, rec):
        tid, u, v = int(rec[0]), float(rec[1]), float(rec[2])
        tri = mesh.triangles[tid]
        p = tri[0] * (1.0 - u - v) + tri[1] * u + tri[2] * v
        return [float(x) for x in p]

    def save_wrap_format(self, base_mesh, target_mesh, path_base: str, path_target: str):
        """导出为 Wrap 官方点文件 (可与 Wrap4D 互导)."""
        left, right = {}, {}
        for p in self.pairs:
            left[p.name] = self._tri_uv(base_mesh, p.base_pos)
            right[p.name] = self._tri_uv(target_mesh, p.target_pos)
        with open(path_base, "w", encoding="utf-8") as f:
            json.dump(left, f)
        with open(path_target, "w", encoding="utf-8") as f:
            json.dump(right, f)

    def load_wrap_format(self, base_mesh, target_mesh, path_base: str, path_target: str):
        """从 Wrap 官方点文件导入 (triangleInd+u,v 精确还原表面位置)."""
        with open(path_base, "r", encoding="utf-8") as f:
            left = json.load(f)
        with open(path_target, "r", encoding="utf-8") as f:
            right = json.load(f)
        from .mesh_io import nearest_vertex
        self.clear()
        for name, rec in left.items():
            if name not in right:
                continue
            bp = self._pos_of(base_mesh, rec)
            tp = self._pos_of(target_mesh, right[name])
            self.add(bp, tp, base_vid=nearest_vertex(base_mesh, bp),
                     target_vid=nearest_vertex(target_mesh, tp), name=name)
