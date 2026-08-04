"""Blender 协同专项测试 (不依赖 Blender, 测试 PyWrap 侧核心):

1. 自定义 OBJ IO: 顶点顺序 + UV 往返保留
2. 包裹结果导出后 UV 仍在
3. vid 格式点对加载 + 坐标解析
4. 形态键 Delta 迁移数学正确
"""

import os
import sys
import tempfile

import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wrapclone.mesh_io import load_obj, save_obj, load_mesh, save_mesh, ObjData
from wrapclone.geometry import RBFDeformer
from wrapclone.wrapping import Wrapper
from wrapclone.point_pairs import PointPairManager
from wrapclone import blendshape


def _make_textured_obj(path, n=50):
    """生成带 UV 的测试 OBJ (三角网格)."""
    rng = np.random.default_rng(0)
    verts = rng.normal(scale=1.0, size=(n, 3))
    faces = np.array([[i, (i + 1) % n, (i + 2) % n] for i in range(n - 2)])
    uvs = rng.random((n, 2))
    # vt 索引 = 顶点索引 (一一对应, 便于校验)
    face_uvs = faces.copy()
    face_nrm = np.full_like(faces, -1)
    data = ObjData()
    data.vertices = verts
    data.uvs = uvs
    data.faces = faces
    data.face_uvs = face_uvs
    data.face_normals = face_nrm
    save_obj(verts, data, path)
    return verts, uvs, faces


def test_obj_uv_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "t.obj")
        verts, uvs, faces = _make_textured_obj(p)
        data = load_obj(p)
        assert len(data.vertices) == len(verts), "顶点数不一致"
        assert np.allclose(data.vertices, verts, atol=1e-4), "顶点坐标改变"
        assert data.has_uv, "UV 丢失"
        assert len(data.uvs) == len(uvs)
        assert np.allclose(data.uvs, uvs, atol=1e-4), "UV 坐标改变"
        assert np.array_equal(data.face_uvs, faces), "UV 面索引改变"
        print("[OK] OBJ UV 往返无损 (顶点序 + vt + 面索引)")


def test_wrap_preserves_uv():
    with tempfile.TemporaryDirectory() as td:
        base_p = os.path.join(td, "base.obj")
        verts, uvs, faces = _make_textured_obj(base_p)
        # 目标 = 基础做小幅 RBF 变形
        rng = np.random.default_rng(1)
        idx = rng.choice(len(verts), 6, replace=False)
        rbf = RBFDeformer().fit(verts[idx], verts[idx] + rng.normal(scale=0.05, size=(6, 3)))
        tgt_verts = rbf(verts)
        tgt = trimesh.Trimesh(tgt_verts, faces, process=False)
        tgt_p = os.path.join(td, "target.obj")
        tgt.export(tgt_p)

        base = load_mesh(base_p)
        target = load_mesh(tgt_p)
        w = Wrapper(base, target)
        result = w.wrap(src_ctrl=verts[idx], dst_ctrl=tgt_verts[idx], src_ctrl_ids=idx,
                        n_icp_iterations=5, target_samples=20000)
        out_p = os.path.join(td, "wrapped.obj")
        save_mesh(result.mesh, out_p)
        out = load_obj(out_p)
        assert out.has_uv, "包裹结果导出后 UV 丢失!"
        assert len(out.uvs) == len(uvs)
        assert np.allclose(out.uvs, uvs, atol=1e-4), "包裹结果 UV 坐标改变"
        assert np.array_equal(out.face_uvs, faces), "包裹结果 UV 面索引改变"
        assert len(out.vertices) == len(verts), "包裹结果顶点数改变"
        print("[OK] 包裹结果保留 UV 与顶点序")


def test_vid_points_resolve():
    with tempfile.TemporaryDirectory() as td:
        rng = np.random.default_rng(0)
        base = trimesh.creation.icosphere(subdivisions=2)
        target = trimesh.Trimesh(base.vertices + 0.1, base.faces, process=False)
        ids = rng.choice(len(base.vertices), 5, replace=False)
        pp = os.path.join(td, "points.json")
        import json
        with open(pp, "w") as f:
            json.dump({"format": "vids", "base_vids": ids.tolist(),
                       "target_vids": ids.tolist(), "names": ["a","b","c","d","e"]}, f)
        mgr = PointPairManager()
        mgr.load(pp)
        assert mgr.unresolved, "vid 点对应被识别为已解析"
        mgr.resolve_positions(base, target)
        assert not mgr.unresolved
        for i, pair in enumerate(mgr.pairs):
            assert np.allclose(pair.base_pos, base.vertices[ids[i]])
            assert np.allclose(pair.target_pos, target.vertices[ids[i]])
        print("[OK] vid 格式点对加载 + 坐标解析正确")


def test_delta_transfer():
    base = np.zeros((10, 3))
    base[3] = [1, 0, 0]
    wrapped = base + np.array([0, 5, 0])           # 整体平移
    shape = base.copy(); shape[3] = [1, 1, 0]      # 形态键: 顶点3再偏移 (0,1,0)
    out = blendshape.delta_transfer(base, wrapped, shape)
    # 期望: wrapped + (shape-base). 顶点3 = [1,5,0]+(0,1,0)=[1,6,0]; 其余=wrapped
    assert np.allclose(out[0], [0, 5, 0])
    assert np.allclose(out[3], [1, 6, 0])
    print("[OK] Delta 迁移数学正确")

    # 顶点数不一致应报错
    try:
        blendshape.delta_transfer(base, wrapped[:-1], shape)
        assert False
    except ValueError:
        pass


def test_batch_transfer():
    with tempfile.TemporaryDirectory() as td:
        rng = np.random.default_rng(0)
        verts = rng.normal(size=(20, 3))
        faces = np.array([[i, i+1, (i+2) % 20] for i in range(18)])
        base = trimesh.Trimesh(verts, faces, process=False); base.metadata["obj_data"] = None
        wrapped_v = verts + np.array([0, 2, 0])
        shapes_dir = os.path.join(td, "shapes"); os.makedirs(shapes_dir)
        from wrapclone.mesh_io import save_obj, ObjData
        for k in range(3):
            sv = verts.copy(); sv[k] += [0.5, 0, 0]
            d = ObjData(); d.vertices = sv; d.faces = faces
            d.face_uvs = np.full_like(faces, -1); d.face_normals = np.full_like(faces, -1)
            save_obj(sv, d, os.path.join(shapes_dir, f"s{k}.obj"))
        from wrapclone.mesh_io import save_obj as _so, ObjData as _OD
        bd = _OD(); bd.vertices = verts; bd.faces = faces
        bd.face_uvs = np.full_like(faces, -1); bd.face_normals = np.full_like(faces, -1)
        _so(verts, bd, os.path.join(td, "base.obj"))
        wd = _OD(); wd.vertices = wrapped_v; wd.faces = faces
        wd.face_uvs = np.full_like(faces, -1); wd.face_normals = np.full_like(faces, -1)
        _so(wrapped_v, wd, os.path.join(td, "wrapped.obj"))

        out_dir = os.path.join(td, "out")
        outs = blendshape.batch_transfer_dir(
            os.path.join(td, "base.obj"), os.path.join(td, "wrapped.obj"),
            shapes_dir, out_dir)
        assert len(outs) == 3
        for k in range(3):
            m = load_mesh(os.path.join(out_dir, f"s{k}.obj"))
            expect = wrapped_v.copy(); expect[k] += [0.5, 0, 0]
            assert np.allclose(m.vertices, expect), f"批量迁移结果 {k} 错误"
        print("[OK] 批量形态键迁移正确")


if __name__ == "__main__":
    test_obj_uv_roundtrip()
    test_delta_transfer()
    test_vid_points_resolve()
    test_wrap_preserves_uv()
    test_batch_transfer()
    print("\nBlender 协同专项测试全部通过")
