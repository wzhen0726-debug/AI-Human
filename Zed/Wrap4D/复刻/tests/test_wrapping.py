"""用合成数据验证包裹算法:

构造: 基础球体 -> 已知的 RBF 平滑变形 + 噪声 -> 目标网格
取若干顶点真值作为控制点对, 运行包裹, 检验包裹结果逼近真值.
"""

import os
import sys
import tempfile

import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wrapclone.geometry import RBFDeformer, umeyama, apply_transform
from wrapclone.wrapping import Wrapper
from wrapclone.point_pairs import PointPairManager


def make_synthetic(seed=0, n_ctrl=12, noise=0.003):
    rng = np.random.default_rng(seed)
    base = trimesh.creation.icosphere(subdivisions=4, radius=1.0)
    idx = rng.choice(len(base.vertices), n_ctrl, replace=False)
    ctrl_src = np.asarray(base.vertices[idx])
    disp = rng.normal(scale=0.18, size=(n_ctrl, 3))
    ctrl_dst = ctrl_src + disp
    rbf = RBFDeformer().fit(ctrl_src, ctrl_dst)
    tgt_verts = rbf(np.asarray(base.vertices))
    tgt_verts += rng.normal(scale=noise, size=tgt_verts.shape)
    target = trimesh.Trimesh(vertices=tgt_verts, faces=np.asarray(base.faces), process=False)
    return base, target, idx, tgt_verts


def test_rbf_interpolation():
    base, target, idx, tgt_verts = make_synthetic()
    # 用全部控制点重建变形场, 验证插值性质
    ctrl_src = np.asarray(base.vertices[idx])
    ctrl_dst = tgt_verts[idx]
    rbf = RBFDeformer().fit(ctrl_src, ctrl_dst)
    err = np.linalg.norm(rbf(ctrl_src) - ctrl_dst, axis=1).max()
    assert err < 1e-8, f"RBF 插值误差过大: {err}"
    print(f"[OK] RBF 插值误差 {err:.2e}")


def test_umeyama():
    rng = np.random.default_rng(1)
    src = rng.normal(size=(10, 3))
    theta = np.deg2rad(30)
    R_true = np.array([[np.cos(theta), -np.sin(theta), 0],
                       [np.sin(theta), np.cos(theta), 0],
                       [0, 0, 1]])
    s_true, t_true = 2.5, np.array([1.0, -2.0, 3.0])
    dst = s_true * (src @ R_true.T) + t_true
    R, t, s = umeyama(src, dst)
    assert abs(s - s_true) < 1e-8
    assert np.allclose(R, R_true, atol=1e-8)
    assert np.allclose(t, t_true, atol=1e-8)
    print("[OK] Umeyama 相似变换估计正确")


def test_rbf_duplicate_points():
    """控制点重复时 RBF 不应崩溃 (正则回退)."""
    src = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 0]], dtype=float)  # 含重复
    dst = src + np.array([0, 0, 0.5])
    rbf = RBFDeformer().fit(src, dst)
    out = rbf(np.array([[0.5, 0.5, 0.5]]))
    assert np.isfinite(out).all()
    print("[OK] RBF 重复控制点鲁棒")


def test_wrapping_converges():
    base, target, ctrl_idx, tgt_verts = make_synthetic()
    src_ctrl = np.asarray(base.vertices[ctrl_idx])
    dst_ctrl = tgt_verts[ctrl_idx]

    initial_err = np.linalg.norm(np.asarray(base.vertices) - tgt_verts, axis=1).mean()
    wrapper = Wrapper(base, target)
    log = []
    result = wrapper.wrap(
        src_ctrl=src_ctrl, dst_ctrl=src_ctrl * 0 + dst_ctrl,
        src_ctrl_ids=ctrl_idx,
        n_icp_iterations=5, n_optimization_iterations=20,
        sampling_min=0.5, sampling_max=10.0, target_samples=40000,
        progress_cb=lambda i, n, d: log.append(d),
    )
    final_err = np.linalg.norm(np.asarray(result.mesh.vertices) - tgt_verts, axis=1).mean()
    print(f"[OK] 包裹误差: 初始 {initial_err:.4f} -> 最终 {final_err:.4f} "
          f"(表面距离 mean={result.stats['mean_dist']:.4f} p95={result.stats['p95_dist']:.4f})")
    assert final_err < initial_err * 0.2, "包裹未有效收敛"
    assert final_err < 0.02, f"包裹精度不足: {final_err}"


def test_wrapping_without_control_points():
    """无控制点时(网格已大致对齐)也能纯 ICP 收敛."""
    base, target, _, tgt_verts = make_synthetic(noise=0.0)
    # 把目标当成"已对齐"场景: 直接用真值附近初始化 -> 用弱变形目标
    wrapper = Wrapper(base, target)
    result = wrapper.wrap(n_icp_iterations=5, sampling_min=2.0, sampling_max=20.0,
                          target_samples=40000)
    d0 = np.linalg.norm(np.asarray(base.vertices) - tgt_verts, axis=1).mean()
    d1 = np.linalg.norm(np.asarray(result.mesh.vertices) - tgt_verts, axis=1).mean()
    print(f"[OK] 无控制点包裹: {d0:.4f} -> {d1:.4f}")
    assert d1 < d0


def test_point_pairs_naming():
    """删除末尾点后, 新点编号应续上 (删 P51 -> 新点还是 P51)."""
    mgr = PointPairManager()
    for i in range(3):
        mgr.add([i, 0, 0], [i, 0, 0])
    assert [p.name for p in mgr.pairs] == ["P1", "P2", "P3"]
    mgr.remove(2)                       # 删 P3
    p = mgr.add([9, 0, 0], [9, 0, 0])
    assert p.name == "P3", f"删除末尾后编号未续上: {p.name}"
    mgr.remove(0)                       # 删中间的 P1
    p = mgr.add([8, 0, 0], [8, 0, 0])
    assert p.name == "P4", f"中间删除后应取最大+1: {p.name}"
    print("[OK] 点编号删除后续接正确")


def test_wrapping_with_mask():
    """遮罩区不参与表面对齐: 被屏蔽顶点不应被吸到目标表面(仅平滑跟随)."""
    base = trimesh.creation.icosphere(subdivisions=4, radius=1.0)
    # 目标 = 基础整体 +X 平移 0.3
    tv = np.asarray(base.vertices) + np.array([0.3, 0, 0])
    target = trimesh.Trimesh(tv, np.asarray(base.faces), process=False)
    bv = np.asarray(base.vertices)
    # 遮罩: 左半球 (x<0) 屏蔽
    mask = (bv[:, 0] >= 0).astype(float)
    wrapper = Wrapper(base, target)
    r = wrapper.wrap(mask=mask, n_icp_iterations=5, n_optimization_iterations=20,
                     sampling_min=2.0, sampling_max=20.0, correspondence="surface")
    # 到目标表面的距离: 未屏蔽区应贴合(~0), 屏蔽区应明显落后(>0)
    from wrapclone.wrapping import _closest_on_surface
    _, _, fdist = _closest_on_surface(target, np.asarray(r.mesh.vertices))
    masked = mask < 0.5
    print(f"[OK] 遮罩包裹: 未屏蔽区表面距离 {fdist[~masked].mean():.4f}(贴合) | "
          f"屏蔽区 {fdist[masked].mean():.4f}(不被强吸) | 屏蔽数 {r.stats['masked_vertices']}")
    assert fdist[~masked].mean() < 0.01, "未屏蔽区应贴合表面"
    assert fdist[masked].mean() > 0.05, "屏蔽区被强行吸附到表面(遮罩失效)"
    assert r.stats["masked_vertices"] == int(masked.sum())


def test_point_pairs_io():
    mgr = PointPairManager()
    mgr.add([0, 0, 0], [1, 1, 1], base_vid=3, target_vid=7, name="鼻尖")
    mgr.add([0.5, 0, 0], [1.5, 1, 1], base_vid=4, target_vid=9)
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "points.json")
        mgr.save(path)
        mgr2 = PointPairManager()
        mgr2.load(path)
    assert len(mgr2) == 2
    assert mgr2.pairs[0].name == "鼻尖"
    assert np.allclose(mgr2.base_points()[1], [0.5, 0, 0])
    assert mgr2.pairs[1].base_vid == 4
    print("[OK] 点对保存/加载正确")


if __name__ == "__main__":
    test_rbf_interpolation()
    test_rbf_duplicate_points()
    test_umeyama()
    test_point_pairs_naming()
    test_point_pairs_io()
    test_wrapping_with_mask()
    test_wrapping_without_control_points()
    test_wrapping_converges()
    print("\n全部测试通过")
