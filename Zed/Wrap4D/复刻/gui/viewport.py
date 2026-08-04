"""三维视口: 基于 pyvista QtInteractor, 支持网格表面拾取、点标记、导航轴标."""

from __future__ import annotations

import numpy as np
import vtk
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QToolButton
from pyvistaqt import QtInteractor

from wrapclone.mesh_io import to_polydata, nearest_vertex


class NavGizmo(QWidget):
    """Blender 风格导航按钮条: X/Y/Z 轴回正(再点切对侧) + 居中."""

    snapped = pyqtSignal(str, bool)   # ('x'|'y'|'z', negative) 或 ('home', False)
    # 首击方向: X=+X(右侧), Y=-Y(正面), Z=+Z(顶面) —— pyvista 中均对应 negative=False
    _PREF = {"x": False, "y": False, "z": False}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._neg = dict(self._PREF)
        self._clicked: set = set()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        for label, color, key, tip in [
            ("X", "#c62828", "x", "右侧视图 (再点切对侧)"),
            ("Y", "#2e7d32", "y", "正面视图 (再点切对侧)"),
            ("Z", "#1565c0", "z", "顶面视图 (再点切对侧)")]:
            btn = QToolButton()
            btn.setText(label)
            btn.setToolTip(tip)
            btn.setFixedSize(26, 26)
            btn.setStyleSheet(
                f"QToolButton {{ color: white; background: {color}; "
                f"border-radius: 13px; font-weight: bold; }}"
                "QToolButton:hover { border: 2px solid white; }")
            btn.clicked.connect(lambda _, k=key: self._snap(k))
            lay.addWidget(btn)
        home = QToolButton()
        home.setText("⌂")
        home.setToolTip("居中显示全部 (Frame)")
        home.setFixedSize(26, 26)
        home.setStyleSheet(
            "QToolButton { color: white; background: #546e7a; "
            "border-radius: 13px; font-weight: bold; }"
            "QToolButton:hover { border: 2px solid white; }")
        home.clicked.connect(lambda: self.snapped.emit("home", False))
        lay.addWidget(home)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.adjustSize()

    def _snap(self, axis: str):
        if axis in self._clicked:
            self._neg[axis] = not self._neg[axis]   # 同轴再点 -> 对侧
        else:
            self._clicked.add(axis)
            self._neg[axis] = self._PREF[axis]
        self.snapped.emit(axis, self._neg[axis])


class Viewport(QWidget):
    """一个带标题的三维视口. 打点模式下点击网格表面发出 surface_clicked."""

    surface_clicked = pyqtSignal(object, int)  # (np.ndarray 位置, 顶点索引)
    camera_changed = pyqtSignal()              # 相机交互时发出(用于视口联动)
    brush_started = pyqtSignal(object, int)    # 笔刷按下 (位置, 顶点索引)
    brush_moved = pyqtSignal(object, int)      # 笔刷拖动
    brush_ended = pyqtSignal()                 # 笔刷抬起

    def __init__(self, title: str, mesh_color: str = "#9dc3e6", parent=None):
        super().__init__(parent)
        self._mesh = None
        self._mesh_actor = None
        self._overlay_actor = None
        self._marker_actors: list = []
        self._pick_enabled = False
        self._brush_enabled = False
        self._brushing = False
        self._opacity = 1.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; padding: 2px;")
        layout.addWidget(self.title_label)

        self.plotter = QtInteractor(self)
        self.plotter.set_background("#2b2b2b")
        layout.addWidget(self.plotter.interactor)

        # Blender 风格轴标 (右上): 点击轴回正 + 拖动旋转, Z 轴向上
        self._cam_widget = vtk.vtkCameraOrientationWidget()
        self._cam_widget.SetParentRenderer(self.plotter.renderer)
        self._cam_widget.SetInteractor(self.plotter.iren.interactor)
        self._cam_widget.AnimateOn()          # 点击后平滑动画过渡
        self._cam_widget.On()

        # 左上导航按钮条 (轴回正 + 居中)
        self.nav = NavGizmo(self.plotter.interactor)
        self.nav.snapped.connect(self._on_nav_snap)
        self.nav.move(8, 8)
        self.nav.show()
        self.nav.raise_()

        self.mesh_color = mesh_color
        self._picker = vtk.vtkCellPicker()
        self._picker.SetTolerance(0.002)
        self.plotter.iren.add_observer("LeftButtonPressEvent", self._on_press)
        self.plotter.iren.add_observer("LeftButtonReleaseEvent", self._on_release)
        self.plotter.iren.add_observer("MouseMoveEvent", self._on_move)
        # 相机任何变化(含滚轮缩放/轴标拖动)都发出同步信号 —— 实时联动
        cam = self.plotter.renderer.GetActiveCamera()
        cam.AddObserver(vtk.vtkCommand.ModifiedEvent, self._on_camera_modified)

    # ---------- 网格显示 ----------
    def set_mesh(self, mesh, opacity: float | None = None):
        if opacity is not None:
            self._opacity = opacity
        self._mesh = mesh
        if self._mesh_actor is not None:
            self.plotter.remove_actor(self._mesh_actor)
            self._mesh_actor = None
        self._pd = None
        if mesh is not None:
            self._pd = to_polydata(mesh)
            self._mesh_actor = self.plotter.add_mesh(
                self._pd, color=self.mesh_color, opacity=self._opacity,
                smooth_shading=True, name="main_mesh")
            self.plotter.reset_camera()

    def refresh_mesh(self):
        """顶点被外部修改后原地刷新显示 (不重置相机)."""
        if self._mesh is None or getattr(self, "_pd", None) is None:
            return
        self._pd.points = np.asarray(self._mesh.vertices, dtype=np.float64)
        self._pd.Modified()
        self.plotter.render()

    def set_opacity(self, opacity: float):
        """调整主网格透明度 (不动相机)."""
        self._opacity = opacity
        if self._mesh_actor is not None:
            self._mesh_actor.GetProperty().SetOpacity(opacity)
            self.plotter.render()

    def set_overlay(self, mesh, color: str = "#4caf50", opacity: float = 0.95):
        """叠加显示第二个网格(包裹结果), 不可拾取."""
        if self._overlay_actor is not None:
            self.plotter.remove_actor(self._overlay_actor)
            self._overlay_actor = None
        self._overlay_mesh = None
        self._overlay_pd = None
        if mesh is not None:
            self._overlay_mesh = mesh
            self._overlay_pd = to_polydata(mesh)
            self._overlay_actor = self.plotter.add_mesh(
                self._overlay_pd, color=color, opacity=opacity,
                smooth_shading=True, name="overlay_mesh", pickable=False)
        self.plotter.render()

    def refresh_overlay(self):
        """结果网格顶点被笔刷修改后原地刷新 (不动相机)."""
        if getattr(self, "_overlay_mesh", None) is None or getattr(self, "_overlay_pd", None) is None:
            return
        self._overlay_pd.points = np.asarray(self._overlay_mesh.vertices, dtype=np.float64)
        self._overlay_pd.Modified()
        self.plotter.render()

    def clear(self):
        self.set_mesh(None)
        self.set_overlay(None)
        self.set_markers(None)
        self.set_mask_points(None)
        self._mesh = None

    # ---------- 遮罩显示 ----------
    def set_mask_points(self, positions):
        """在遮罩(被屏蔽)顶点处显示红点. positions 为 (m,3) 或 None 清除."""
        if getattr(self, "_mask_actor", None) is not None:
            self.plotter.remove_actor(self._mask_actor)
            self._mask_actor = None
        if positions is not None and len(positions) > 0:
            import pyvista as pv
            self._mask_actor = self.plotter.add_mesh(
                pv.PolyData(np.asarray(positions, dtype=np.float64)),
                render_points_as_spheres=True, point_size=6.0,
                color="#ff1744", opacity=0.85, pickable=False, reset_camera=False)
        self.plotter.render()

    # ---------- 相机 ----------
    def _on_camera_modified(self, obj, event):
        # 源头节流: 限制 ~60Hz, 避免高模双视口连环重绘导致掉帧
        import time
        now = time.monotonic()
        if now - getattr(self, "_last_cam_emit", 0.0) < 0.016:
            self._cam_dirty = True
            return
        self._last_cam_emit = now
        self._cam_dirty = False
        self.camera_changed.emit()

    def flush_camera_signal(self):
        """把节流期间积压的相机变化补发一次 (交互结束/动画结束后调用)."""
        if getattr(self, "_cam_dirty", False):
            self._cam_dirty = False
            self.camera_changed.emit()

    def get_camera(self):
        return self.plotter.camera_position

    def set_camera(self, cam):
        self.plotter.camera_position = cam
        self.plotter.render()

    def _on_nav_snap(self, code: str, negative: bool):
        if code == "home":
            self.frame()
            return
        self.snap_view(code, negative)

    def snap_view(self, axis: str, negative: bool = False):
        """回正到标准视图: x=侧视 y=正视 z=顶视 (negative=对侧). 世界 Z 轴向上."""
        if axis == "x":
            self.plotter.view_yz(negative=negative)
            self.plotter.camera.up = (0, 0, 1)
        elif axis == "y":
            self.plotter.view_xz(negative=negative)
            self.plotter.camera.up = (0, 0, 1)
        elif axis == "z":
            self.plotter.view_xy(negative=negative)
            self.plotter.camera.up = (0, 1, 0)
        self.plotter.render()

    def frame(self):
        """居中显示全部内容 (Blender 的 Frame/View All)."""
        self.plotter.reset_camera()
        self.plotter.render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "nav"):
            self.nav.raise_()

    # ---------- 点标记 ----------
    def set_markers(self, points, labels=None, color: str = "#e53935",
                    pending=None, highlight_index: int = -1):
        for actor in self._marker_actors:
            self.plotter.remove_actor(actor)
        self._marker_actors.clear()

        import pyvista as pv
        if points is not None and len(points) > 0:
            pts = np.asarray(points, dtype=np.float64)
            sizes = np.full(len(pts), 13.0)
            colors = [color] * len(pts)
            if 0 <= highlight_index < len(pts):
                sizes[highlight_index] = 20.0
                colors[highlight_index] = "#ffeb3b"
            cloud = pv.PolyData(pts)
            cloud["sizes"] = sizes
            actor = self.plotter.add_mesh(
                cloud, render_points_as_spheres=True, point_size=13.0,
                color=color, pickable=False, reset_camera=False)
            self._marker_actors.append(actor)
            if labels:
                label_actor = self.plotter.add_point_labels(
                    pts, labels, font_size=11, text_color="white",
                    always_visible=True, show_points=False,
                    shape_opacity=0.4, name="pt_labels")
                label_actor.SetPickable(False)
                self._marker_actors.append(label_actor)
        if pending is not None:
            actor = self.plotter.add_mesh(
                pv.PolyData(np.asarray(pending, dtype=np.float64).reshape(1, 3)),
                render_points_as_spheres=True, point_size=17.0,
                color="#ffeb3b", pickable=False, reset_camera=False)
            self._marker_actors.append(actor)
        self.plotter.render()

    # ---------- 拾取 ----------
    def set_pick_enabled(self, enabled: bool):
        self._pick_enabled = enabled

    def set_brush_enabled(self, enabled: bool):
        self._brush_enabled = enabled
        if not enabled:
            self._brushing = False

    def _pick_at(self, x, y):
        """在 (x,y) 处拾取主网格, 返回 (位置, 顶点索引) 或 None."""
        if self._mesh is None:
            return None
        if self._picker.Pick(x, y, 0.0, self.plotter.renderer) == 0:
            return None
        if self._picker.GetActor() is not self._mesh_actor:
            return None
        pos = np.array(self._picker.GetPickPosition(), dtype=np.float64)
        return pos, nearest_vertex(self._mesh, pos)

    def _on_press(self, obj, event):
        x, y = self.plotter.iren.get_event_position()
        if self._brush_enabled:
            hit = self._pick_at(x, y)
            if hit is not None:
                self._brushing = True
                self.brush_started.emit(hit[0], hit[1])
            return
        if not self._pick_enabled:
            return
        hit = self._pick_at(x, y)
        if hit is not None:
            self.surface_clicked.emit(hit[0], hit[1])

    def _on_move(self, obj, event):
        if self._brush_enabled and self._brushing:
            x, y = self.plotter.iren.get_event_position()
            hit = self._pick_at(x, y)
            if hit is not None:
                self.brush_moved.emit(hit[0], hit[1])

    def _on_release(self, obj, event):
        if self._brushing:
            self._brushing = False
            self.brush_ended.emit()

    def reset_camera(self):
        self.plotter.reset_camera()
