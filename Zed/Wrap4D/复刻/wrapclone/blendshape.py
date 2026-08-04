"""形态键 (Blendshape/Shape Key) Delta 迁移.

数字人工作流: 基础网格带有一组表情形态键(如 ARKit 52 个),
包裹到新扫描后, 利用拓扑一致性把所有形态键迁移到包裹结果上:
    shape_i_wrapped = wrapped + (shape_i_base - base)

输入输出均为一组 OBJ 文件(顶点顺序一致), 可脱离 Blender 批量处理.
Blender 插件内也实现了同样逻辑(直接操作 shape key 数据).
"""

from __future__ import annotations

import os

import numpy as np

from .mesh_io import load_mesh, save_mesh


def delta_transfer(base_neutral: np.ndarray, wrapped: np.ndarray,
                   shape_vertices: np.ndarray) -> np.ndarray:
    """对单个形态键做 delta 迁移."""
    base_neutral = np.asarray(base_neutral, dtype=np.float64)
    wrapped = np.asarray(wrapped, dtype=np.float64)
    shape_vertices = np.asarray(shape_vertices, dtype=np.float64)
    if not (base_neutral.shape == wrapped.shape == shape_vertices.shape):
        raise ValueError("顶点数量不一致, 无法做 delta 迁移: "
                         f"base{base_neutral.shape} wrapped{wrapped.shape} "
                         f"shape{shape_vertices.shape}")
    return wrapped + (shape_vertices - base_neutral)


def batch_transfer_dir(base_obj: str, wrapped_obj: str, shapes_dir: str,
                       out_dir: str, pattern: str = ".obj") -> list[str]:
    """批量迁移目录中的所有形态键 OBJ, 返回输出文件列表."""
    base = load_mesh(base_obj)
    wrapped = load_mesh(wrapped_obj)
    os.makedirs(out_dir, exist_ok=True)
    outs = []
    for fn in sorted(os.listdir(shapes_dir)):
        if not fn.lower().endswith(pattern):
            continue
        shape = load_mesh(os.path.join(shapes_dir, fn))
        new_verts = delta_transfer(base.vertices, wrapped.vertices, shape.vertices)
        shape.vertices = new_verts
        out_path = os.path.join(out_dir, fn)
        save_mesh(shape, out_path)
        outs.append(out_path)
    return outs
