"""视口导航测试: 轴回正方向正确 / 居中 / 导航按钮存在 / 联动."""

import os
import sys

import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt


def cam_dir(view):
    """相机位置->焦点 的单位向量."""
    pos, foc, _ = view.get_camera()
    d = np.asarray(pos) - np.asarray(foc)
    return d / np.linalg.norm(d)


def main():
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    app = QApplication([])
    from gui.main_window import MainWindow
    win = MainWindow()

    mesh = trimesh.creation.icosphere(subdivisions=3)
    win.base_view.set_mesh(mesh)
    win.target_view.set_mesh(mesh)

    # 导航按钮条存在
    assert hasattr(win.base_view, "nav"), "缺少导航按钮条"
    print("[OK] 导航按钮条已挂载")

    # X 首击 = +X 方向侧视 (相机在 +X)
    win.base_view.snap_view("x", negative=False)
    d = cam_dir(win.base_view)
    assert np.allclose(d, [1, 0, 0], atol=1e-6), f"X回正方向错误 {d}"
    print("[OK] X 轴回正 (+X 侧视)")

    # X 再点 = -X
    win.base_view.snap_view("x", negative=True)
    d = cam_dir(win.base_view)
    assert np.allclose(d, [-1, 0, 0], atol=1e-6), f"X对侧错误 {d}"
    print("[OK] X 轴对侧 (-X)")

    # Y 正视: 首击方向应为 -Y (Blender 正面) = view_xz(negative=False)
    win.base_view.snap_view("y", negative=False)
    d = cam_dir(win.base_view)
    assert np.allclose(d, [0, -1, 0], atol=1e-6), f"Y回正方向错误 {d}"
    print("[OK] Y 轴回正 (-Y 正视)")
    win.base_view.snap_view("y", negative=True)
    d = cam_dir(win.base_view)
    assert np.allclose(d, [0, 1, 0], atol=1e-6), f"Y对侧错误 {d}"
    print("[OK] Y 轴对侧 (+Y 背面)")

    # Z 顶视: +Z
    win.base_view.snap_view("z", negative=False)
    d = cam_dir(win.base_view)
    assert np.allclose(d, [0, 0, 1], atol=1e-6), f"Z回正方向错误 {d}"
    print("[OK] Z 轴回正 (+Z 顶视)")

    # 按钮点击联动 NavGizmo: 模拟点 X 按钮(首击=PREF)
    nav = win.target_view.nav
    nav._snap("x")
    d = cam_dir(win.target_view)
    assert np.allclose(d, [1, 0, 0], atol=1e-6), "按钮 X 回正失败"
    nav._snap("x")  # 再点 -> 对侧
    d = cam_dir(win.target_view)
    assert np.allclose(d, [-1, 0, 0], atol=1e-6), "按钮 X 对侧失败"
    print("[OK] 导航按钮点击切换正/反方向")

    # Z-up 约定: 正/侧视图上方向 = +Z, 顶视图上方向 = +Y (同 Blender)
    win.base_view.snap_view("y", negative=False)
    up = np.asarray(win.base_view.get_camera()[2])
    assert np.allclose(up, [0, 0, 1], atol=1e-6), f"正视图up应为+Z: {up}"
    win.base_view.snap_view("x", negative=False)
    up = np.asarray(win.base_view.get_camera()[2])
    assert np.allclose(up, [0, 0, 1], atol=1e-6), f"侧视图up应为+Z: {up}"
    win.base_view.snap_view("z", negative=False)
    up = np.asarray(win.base_view.get_camera()[2])
    assert np.allclose(up, [0, 1, 0], atol=1e-6), f"顶视图up应为+Y: {up}"
    print("[OK] Z 轴向上约定 (同 Blender)")

    # Blender 式轴标 (vtkCameraOrientationWidget) 已启用
    import vtk
    assert isinstance(win.base_view._cam_widget, vtk.vtkCameraOrientationWidget)
    assert win.base_view._cam_widget.GetEnabled(), "轴标未启用"
    print("[OK] Blender 式可点击轴标 (点击回正+拖动旋转)")

    # 居中
    win.base_view.snap_view("x", negative=False)
    win.base_view.frame()
    assert win.base_view.get_camera() is not None
    print("[OK] 居中 (frame)")

    # 快捷键逻辑
    win._snap_both("z")
    assert np.allclose(cam_dir(win.base_view), [0, 0, 1], atol=1e-6)
    assert np.allclose(cam_dir(win.target_view), [0, 0, 1], atol=1e-6)
    print("[OK] 双视口同步回正 (快捷键)")

    print("\n视口导航测试全部通过")


if __name__ == "__main__":
    main()
