"""SubdivideGeom / Brush / Wrap点格式 专项测试."""

import os
import sys
import tempfile

import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wrapclone.subdivide import (subdivide_mesh, transfer_mask, transfer_painted,
                                 nearest_vertex_map)
from wrapclone.brush import MeshBrush, _falloff_weights
from wrapclone.mesh_io import load_mesh, save_mesh, ObjData, save_obj
from wrapclone.point_pairs import PointPairManager


def test_subdivide():
    mesh = trimesh.creation.icosphere(subdivisions=2)
    sub, parent = subdivide_mesh(mesh, 1)
    v0, f0 = len(mesh.vertices), len(mesh.faces)
    assert len(sub.faces) == f0 * 4, "面数应 ×4"
    assert len(parent) == len(sub.vertices)
    # 边数 = 新顶点增量
    print(f"[OK] 细分: {v0}v/{f0}f -> {len(sub.vertices)}v/{len(sub.faces)}f")

    # 遮罩传递: 屏蔽一顶点 -> 其中点子顶点也被屏蔽
    mask = np.ones(v0)
    mask[5] = 0.0
    m2 = transfer_mask(parent, mask)
    assert m2[5] == 0.0, "原顶点遮罩未保留"
    # 顶点5的边中点应被屏蔽
    affected = [j for j, (a, b) in enumerate(parent) if a != b and (a == 5 or b == 5)]
    assert len(affected) > 0 and all(m2[j] == 0.0 for j in affected), "中点遮罩未传递"
    print("[OK] 遮罩传递到细分网格")


def test_subdivide_uv():
    # 带 UV 的 OBJ -> 细分 -> UV 保留且面索引一致
    rng = np.random.default_rng(0)
    verts = rng.normal(size=(6, 3))
    faces = np.array([[0, 1, 2], [2, 3, 4], [1, 4, 5], [0, 2, 3]])
    uvs = rng.random((6, 2))
    d = ObjData(); d.vertices = verts; d.uvs = uvs; d.faces = faces
    d.face_uvs = faces.copy(); d.face_normals = np.full_like(faces, -1)
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "m.obj")
        save_obj(verts, d, p)
        mesh = load_mesh(p)
        sub, parent = subdivide_mesh(mesh, 1)
        nd = sub.metadata["obj_data"]
        assert nd.has_uv, "细分后 UV 丢失"
        assert len(nd.uvs) == len(sub.vertices), "细分 UV 数应与顶点数一致"
        assert nd.face_uvs.shape == sub.faces.shape
        # 导出再导入不丢 UV
        out = os.path.join(td, "sub.obj")
        save_mesh(sub, out)
        d2 = load_mesh(out).metadata["obj_data"]
        assert d2.has_uv
    print("[OK] 细分保留 UV 与导出结构")


def test_brush_move():
    mesh = trimesh.creation.icosphere(subdivisions=3)
    v0 = np.asarray(mesh.vertices).copy()
    br = MeshBrush(mesh)
    center = v0[0].copy()
    br.stroke_move(center, np.array([0.0, 0.0, 0.5]), radius=0.5, strength=100.0,
                   falloff=50.0)
    dv = np.asarray(mesh.vertices) - v0
    # 中心处位移 ≈ delta, 远处为 0
    assert np.allclose(dv[0], [0, 0, 0.5], atol=1e-6), f"中心位移错误 {dv[0]}"
    far = np.linalg.norm(v0 - center, axis=1) > 0.6
    assert np.abs(dv[far]).max() < 1e-9, "远处顶点不应移动"
    print("[OK] 移动笔刷 (中心位移+衰减范围)")


def test_brush_symmetry():
    mesh = trimesh.creation.icosphere(subdivisions=3)
    v0 = np.asarray(mesh.vertices).copy()
    br = MeshBrush(mesh)
    center = np.array([0.5, 0.0, 0.86])
    br.stroke_move(center, np.array([0.0, 0.0, 0.3]), radius=0.3, strength=100.0,
                   symmetry=True)
    dv = np.asarray(mesh.vertices) - v0
    # 镜像侧 (-0.5,0,0.86) 附近也应有位移
    mirror_vid = int(np.argmin(np.linalg.norm(v0 - np.array([-0.5, 0, 0.86]), axis=1)))
    assert np.linalg.norm(dv[mirror_vid]) > 0.01, "X 对称未生效"
    print("[OK] X 对称笔刷")


def test_brush_smooth_attract():
    mesh = trimesh.creation.icosphere(subdivisions=3)
    v0 = np.asarray(mesh.vertices).copy()
    mesh.vertices[0] += np.array([0, 0, 0.4])   # 造一个尖刺
    br = MeshBrush(mesh)
    spike = np.asarray(mesh.vertices)[0].copy()
    br.stroke_smooth(spike, radius=0.4, strength=100.0)
    assert np.asarray(mesh.vertices)[0, 2] < spike[2], "平滑应压低尖刺"
    print("[OK] 平滑笔刷")

    # 吸附: 把一个顶点推出去再吸回目标球面
    mesh2 = trimesh.creation.icosphere(subdivisions=3)
    target = trimesh.creation.icosphere(subdivisions=3)
    mesh2.vertices[0] *= 1.5
    br2 = MeshBrush(mesh2)
    br2.stroke_attract(np.asarray(mesh2.vertices)[0], target, radius=0.6, strength=100.0)
    d_after = abs(np.linalg.norm(mesh2.vertices[0]) - 1.0)
    assert d_after < 0.05, f"吸附后应回到球面附近: {d_after}"
    print("[OK] 吸附到扫描面笔刷")


def test_falloff():
    w = _falloff_weights(np.array([0.0, 0.5, 1.0]), 1.0, 50.0)
    assert w[0] == 1.0 and w[2] == 0.0 and 0 < w[1] < 1
    w2 = _falloff_weights(np.array([0.5]), 1.0, 100.0)
    assert w2[0] < w[1], "falloff 越大衰减越陡"
    print("[OK] 衰减曲线")


def test_brush_geodesic():
    # 薄壁: 欧氏距离近但测地远 -> 测地模式下不受影响
    # 两个近平行面片 (相距 0.05, 几何上很远)
    verts = []
    faces = []
    for layer, z in enumerate([0.0, 0.05]):
        base_i = len(verts)
        grid = 6
        for i in range(grid):
            for j in range(grid):
                verts.append([i * 0.1, j * 0.1, z])
        for i in range(grid - 1):
            for j in range(grid - 1):
                a = base_i + i * grid + j
                faces.append([a, a + grid, a + 1])
                faces.append([a + 1, a + grid, a + grid + 1])
    mesh = trimesh.Trimesh(np.array(verts), np.array(faces), process=False)
    v0 = np.asarray(mesh.vertices).copy()
    br = MeshBrush(mesh)
    br.stroke_move(np.array([0.2, 0.2, 0.0]), np.array([0, 0, 1.0]), radius=0.3,
                   strength=100.0, geodesic=True)
    dv = np.asarray(mesh.vertices) - v0
    # 底层(z=0)应动, 顶层(z=0.05)测地距离无穷远不应动
    top = v0[:, 2] > 0.03
    assert np.abs(dv[top]).max() < 1e-9, "测地模式下穿透了薄壁"
    print("[OK] 测地距离笔刷 (不穿透薄壁)")


def test_wrap_format_io():
    base = trimesh.creation.icosphere(subdivisions=3)
    target = trimesh.Trimesh(base.vertices + np.array([0.1, 0, 0]),
                             base.faces, process=False)
    mgr = PointPairManager()
    ids = [0, 100, 500]
    for k, vid in enumerate(ids):
        mgr.add(base.vertices[vid], target.vertices[vid], base_vid=vid, target_vid=vid)
    with tempfile.TemporaryDirectory() as td:
        pb = os.path.join(td, "base_points.txt")
        pt = os.path.join(td, "target_points.txt")
        mgr.save_wrap_format(base, target, pb, pt)
        import json
        left = json.load(open(pb))
        # 格式校验: {"P1": [tri, u, v]}
        rec = list(left.values())[0]
        assert isinstance(rec[0], int) and 0 <= rec[1] <= 1 and 0 <= rec[2] <= 1
        mgr2 = PointPairManager()
        mgr2.load_wrap_format(base, target, pb, pt)
    assert len(mgr2) == 3
    for i, vid in enumerate(ids):
        assert np.allclose(mgr2.pairs[i].base_pos, base.vertices[vid], atol=1e-3), \
            "Wrap 格式导入位置偏差过大"
    print("[OK] Wrap 官方点格式导出/导入 (triangleInd+重心坐标)")


if __name__ == "__main__":
    test_subdivide()
    test_subdivide_uv()
    test_falloff()
    test_brush_move()
    test_brush_symmetry()
    test_brush_smooth_attract()
    test_brush_geodesic()
    test_wrap_format_io()
    print("\nSubdivide/Brush/Wrap格式 测试全部通过")
