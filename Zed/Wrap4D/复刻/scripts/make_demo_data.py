"""生成演示数据: demo/base.obj, demo/target.obj, demo/points.json

场景: 基础球面网格 -> 整体 RBF 变形 + 局部特征(鼻/眼凸包) -> 目标"扫描"网格
控制点取在特征中心, 模拟真实打点流程.
"""

import os
import sys

import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wrapclone.geometry import RBFDeformer
from wrapclone.point_pairs import PointPairManager

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo")


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(42)

    base = trimesh.creation.icosphere(subdivisions=5, radius=1.0)
    verts = np.asarray(base.vertices).copy()

    # 整体平滑变形
    idx = rng.choice(len(verts), 10, replace=False)
    rbf = RBFDeformer().fit(verts[idx], verts[idx] + rng.normal(scale=0.12, size=(10, 3)))
    tverts = rbf(verts)

    # 局部特征: 鼻子(+Z)、左眼、右眼 凸包
    feats = {"鼻尖": np.array([0.0, 0.0, 1.0]),
             "左眼": np.array([-0.45, 0.35, 0.82]),
             "右眼": np.array([0.45, 0.35, 0.82])}
    for c in feats.values():
        c = c / np.linalg.norm(c)
        d = np.linalg.norm(tverts - c, axis=1)
        tverts = tverts + c * (0.18 * np.exp(-(d / 0.18) ** 2))[:, None]

    target = trimesh.Trimesh(tverts, np.asarray(base.faces), process=False)

    # 控制点: 特征中心 + 环绕点(取目标表面上的真值位置)
    mgr = PointPairManager()
    feat_pts = []
    for name, c in feats.items():
        cn = c / np.linalg.norm(c)
        vid = int(np.argmax(np.asarray(base.vertices) @ cn))
        feat_pts.append((name, vid))
    for name, vid in feat_pts:
        mgr.add(base.vertices[vid], target.vertices[vid], base_vid=vid, target_vid=vid, name=name)
    for k, ang in enumerate(np.linspace(0, 2 * np.pi, 8, endpoint=False)):
        cn = np.array([np.cos(ang), np.sin(ang), 0.0])
        vid = int(np.argmax(np.asarray(base.vertices) @ cn))
        mgr.add(base.vertices[vid], target.vertices[vid],
                base_vid=vid, target_vid=vid, name=f"轮廓{k+1}")

    base.export(os.path.join(OUT, "base.obj"))
    target.export(os.path.join(OUT, "target.obj"))
    mgr.save(os.path.join(OUT, "points.json"))
    print(f"演示数据已生成到 {OUT}")
    print(f"  base.obj   顶点 {len(base.vertices)}")
    print(f"  target.obj 顶点 {len(target.vertices)}")
    print(f"  points.json 点对 {len(mgr)}")


if __name__ == "__main__":
    main()
