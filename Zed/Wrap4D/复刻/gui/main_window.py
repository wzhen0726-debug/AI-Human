"""PyWrap 主窗口: 双视口打点 + 包裹参数面板 + 结果导出."""

from __future__ import annotations

import os
import traceback

import numpy as np
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QEvent, QTimer
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QCheckBox, QSpinBox,
    QDoubleSpinBox, QFileDialog, QMessageBox, QProgressBar, QFormLayout,
    QComboBox, QGridLayout, QSlider, QApplication,
)

from wrapclone.mesh_io import load_mesh, save_mesh, mesh_stats
from wrapclone.point_pairs import PointPairManager
from wrapclone.wrapping import Wrapper
from wrapclone.geometry import umeyama, apply_transform
from wrapclone.blender_detect import find_blender
from wrapclone import blendshape
from gui.viewport import Viewport

DEFAULT_EXCHANGE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "blender_exchange")


class WrapThread(QThread):
    preparing = pyqtSignal()
    progressed = pyqtSignal(int, int, float)
    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, base_mesh, target_mesh, kwargs: dict, parent=None):
        super().__init__(parent)
        self._base = base_mesh
        self._target = target_mesh
        self._kwargs = kwargs

    def run(self):
        try:
            self.preparing.emit()
            # 重量级初始化(拉普拉斯/表面搜索树)在线程内做, 不卡界面
            wrapper = Wrapper(self._base, self._target)
            self._kwargs["progress_cb"] = lambda i, n, d: self.progressed.emit(i, n, d)
            result = wrapper.wrap(**self._kwargs)
            self.done.emit(result)
        except Exception:
            self.failed.emit(traceback.format_exc())


class TwoStepThread(QThread):
    """两步包裹: 粗包 -> 细分 -> 精包 (WrappingInTwoSteps)."""

    progressed = pyqtSignal(int, int, float)
    stage = pyqtSignal(str)
    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, base_mesh, target_mesh, kwargs1, kwargs2, parent_map_info, parent=None):
        super().__init__(parent)
        self._base = base_mesh
        self._target = target_mesh
        self._k1 = kwargs1
        self._k2 = kwargs2
        self._info = parent_map_info  # dict(mask=..., src_ctrl_ids=..., src_ctrl=..., dst_ctrl=...)

    def run(self):
        try:
            from wrapclone.subdivide import (subdivide_mesh, transfer_mask,
                                             nearest_vertex_map)
            self.stage.emit("第一步: 粗包裹中...")
            r1 = Wrapper(self._base, self._target).wrap(**self._k1)
            self.stage.emit("第二步: 细分网格中...")
            sub, parent = subdivide_mesh(r1.mesh, 1)
            k2 = dict(self._k2)
            # 遮罩/控制点传递到细分网格
            if self._info.get("mask") is not None:
                k2["mask"] = transfer_mask(parent, self._info["mask"])
            ctrl_ids = self._info.get("src_ctrl_ids")
            if ctrl_ids is not None and len(ctrl_ids) > 0:
                moved_pos = np.asarray(r1.mesh.vertices)[ctrl_ids]
                k2["src_ctrl"] = moved_pos
                k2["src_ctrl_ids"] = nearest_vertex_map(sub, moved_pos)
            self.stage.emit("第二步: 精细包裹中...")
            r2 = Wrapper(sub, self._target).wrap(**k2)
            r2.stats["subdivided_vertices"] = len(sub.vertices)
            self.done.emit(r2)
        except Exception:
            self.failed.emit(traceback.format_exc())


class _NoWheelFilter(QObject):
    """屏蔽未聚焦控件的滚轮事件, 防止滚动面板时误改参数."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and not obj.hasFocus():
            return True
        return super().eventFilter(obj, event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyWrap - 拓扑包裹工具 (Wrap4D 风格)")
        self.resize(1500, 900)

        self.base_mesh = None
        self.target_mesh = None
        self.wrapped_mesh = None
        self.base_path = ""
        self.target_path = ""
        self.pairs = PointPairManager()
        self.pending: dict = {}          # 'base'/'target' -> (pos, vid)
        self.pick_mode = False
        self.mask_mode = False
        self.brush_mode = False
        self._painted: np.ndarray | None = None   # 基础网格涂抹区(bool)
        self._reassign: tuple | None = None  # ('base'|'target', 行号)
        self._syncing_camera = False
        self._sync_pending: Viewport | None = None
        self._wrap_thread: WrapThread | None = None

        self._build_ui()
        self._connect()
        self._update_hint()

        # 视图快捷键 (类 Blender: Ctrl+1正视 3侧视 7顶视 0居中)
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui import QKeySequence
        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self._snap_both("y"))
        QShortcut(QKeySequence("Ctrl+3"), self, lambda: self._snap_both("x"))
        QShortcut(QKeySequence("Ctrl+7"), self, lambda: self._snap_both("z"))
        QShortcut(QKeySequence("Ctrl+0"), self, self._frame_both)

    def _snap_both(self, axis: str):
        for v in (self.base_view, self.target_view):
            v.nav._clicked.add(axis)          # 与按钮一致的首击方向
            v.snap_view(axis, v.nav._PREF[axis])

    def _frame_both(self):
        self.base_view.frame()
        self.target_view.frame()

    # ================= UI =================
    def _build_ui(self):
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        panel = QWidget()
        vbox = QVBoxLayout(panel)

        # ---- 网格 ----
        g_mesh = QGroupBox("网格")
        form = QVBoxLayout(g_mesh)
        self.btn_load_base = QPushButton("加载基础网格 (Base)...")
        self.btn_load_target = QPushButton("加载扫描网格 (Target)...")
        self.lbl_base = QLabel("未加载")
        self.lbl_target = QLabel("未加载")
        self.lbl_base.setWordWrap(True)
        self.lbl_target.setWordWrap(True)
        row_op = QHBoxLayout()
        row_op.addWidget(QLabel("扫描透明度"))
        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(10, 100)
        self.slider_opacity.setValue(100)
        row_op.addWidget(self.slider_opacity)
        row_axis = QHBoxLayout()
        self.chk_yup = QCheckBox("导入时 Y-up→Z-up (GLB/GLTF 自动)")
        self.chk_yup.setToolTip("OBJ/PLY/STL 等来自 Y-up 软件(Maya/部分扫描仪)的模型勾选;\n"
                                "GLB/GLTF 规范恒为 Y-up, 无需勾选(自动转换)")
        row_axis.addWidget(self.chk_yup)
        self.chk_sync = QCheckBox("视口相机联动")
        self.chk_sync.setChecked(True)
        form.addWidget(self.btn_load_base)
        form.addWidget(self.lbl_base)
        form.addWidget(self.btn_load_target)
        form.addWidget(self.lbl_target)
        form.addLayout(row_op)
        form.addLayout(row_axis)
        form.addWidget(self.chk_sync)
        vbox.addWidget(g_mesh)

        # ---- 对齐 ----
        g_align = QGroupBox("对齐 (把两个模型摆到一起)")
        al = QVBoxLayout(g_align)
        row_obj = QHBoxLayout()
        row_obj.addWidget(QLabel("要移动的模型:"))
        self.combo_align_target = QComboBox()
        self.combo_align_target.addItems(["基础网格 Base", "扫描网格 Target"])
        row_obj.addWidget(self.combo_align_target)
        al.addLayout(row_obj)
        hint = QLabel("手动微调下方选中模型; 或先打≥3对控制点, "
                      "再点「按控制点对齐」让它自动贴合到另一个模型上")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        al.addWidget(hint)
        row_a1 = QHBoxLayout()
        self.btn_align_center = QPushButton("中心对齐")
        self.btn_align_center.setToolTip("把选中模型的中心平移到另一个模型的中心 (不缩放)")
        self.btn_align = QPushButton("包围盒对齐")
        self.btn_align.setToolTip("按包围盒把选中模型平移+缩放到与另一个模型重合")
        self.btn_align_points = QPushButton("按控制点对齐")
        self.btn_align_points.setToolTip(
            "需先打至少 3 对控制点.\n用这些点计算刚体(含缩放)变换,\n把选中模型贴合到另一个模型上")
        row_a1.addWidget(self.btn_align_center)
        row_a1.addWidget(self.btn_align)
        row_a1.addWidget(self.btn_align_points)
        al.addLayout(row_a1)
        grid = QGridLayout()
        self.spin_step = QDoubleSpinBox(); self.spin_step.setDecimals(3)
        self.spin_step.setRange(0.0001, 1e6); self.spin_step.setValue(0.05)
        self.spin_step.setToolTip("单次平移距离 (默认=目标包围盒的1%)")
        grid.addWidget(QLabel("平移步长"), 0, 0)
        grid.addWidget(self.spin_step, 0, 1)
        self.btn_tx = [QPushButton(s) for s in ("X-", "X+", "Y-", "Y+", "Z-", "Z+")]
        for k, b in enumerate(self.btn_tx):
            b.setToolTip("沿轴平移选中模型")
            grid.addWidget(b, 1 + k // 2, k % 2)
        self.spin_angle = QDoubleSpinBox(); self.spin_angle.setRange(0.1, 180.0)
        self.spin_angle.setValue(5.0)
        self.spin_angle.setToolTip("单次旋转角度")
        grid.addWidget(QLabel("旋转角度°"), 2, 0)
        grid.addWidget(self.spin_angle, 2, 1)
        self.btn_rx = [QPushButton(s) for s in ("Rx-", "Rx+", "Ry-", "Ry+", "Rz-", "Rz+")]
        for k, b in enumerate(self.btn_rx):
            b.setToolTip("绕自身中心旋转选中模型")
            grid.addWidget(b, 3 + k // 2, k % 2)
        self.spin_scale = QDoubleSpinBox(); self.spin_scale.setDecimals(3)
        self.spin_scale.setRange(1.001, 10.0); self.spin_scale.setValue(1.05)
        self.spin_scale.setToolTip("单次缩放倍率")
        grid.addWidget(QLabel("缩放系数"), 4, 0)
        grid.addWidget(self.spin_scale, 4, 1)
        self.btn_scale_up = QPushButton("放大")
        self.btn_scale_down = QPushButton("缩小")
        self.btn_scale_up.setToolTip("绕自身中心放大选中模型")
        self.btn_scale_down.setToolTip("绕自身中心缩小选中模型")
        grid.addWidget(self.btn_scale_up, 5, 0)
        grid.addWidget(self.btn_scale_down, 5, 1)
        al.addLayout(grid)
        vbox.addWidget(g_align)

        # ---- 点对 ----
        g_pts = QGroupBox("控制点对 (SelectPointPairs)")
        pv = QVBoxLayout(g_pts)
        self.btn_pick = QPushButton("进入打点模式")
        self.btn_pick.setCheckable(True)
        self.hint_label = QLabel("")
        self.hint_label.setStyleSheet("color: #1976d2;")
        self.hint_label.setWordWrap(True)
        self.pair_list = QListWidget()
        self.pair_list.setMinimumHeight(130)
        row = QHBoxLayout()
        self.btn_del_pair = QPushButton("删除选中")
        self.btn_clear_pairs = QPushButton("清空")
        self.btn_cancel_pending = QPushButton("取消待定点 (Esc)")
        row.addWidget(self.btn_del_pair)
        row.addWidget(self.btn_clear_pairs)
        row.addWidget(self.btn_cancel_pending)
        row3 = QHBoxLayout()
        self.btn_re_base = QPushButton("重设基础点")
        self.btn_re_target = QPushButton("重设扫描点")
        row3.addWidget(self.btn_re_base)
        row3.addWidget(self.btn_re_target)
        row2 = QHBoxLayout()
        self.btn_save_points = QPushButton("保存点对...")
        self.btn_load_points = QPushButton("加载点对...")
        row2.addWidget(self.btn_save_points)
        row2.addWidget(self.btn_load_points)
        row4 = QHBoxLayout()
        self.btn_export_wrap_pts = QPushButton("导出Wrap格式...")
        self.btn_export_wrap_pts.setToolTip(
            "导出为 Wrap4D 官方点文件格式 (triangleInd+重心坐标, 两个.txt)")
        self.btn_import_wrap_pts = QPushButton("导入Wrap格式...")
        self.btn_import_wrap_pts.setToolTip("从 Wrap4D 导出的点对 .txt 文件导入")
        row4.addWidget(self.btn_export_wrap_pts)
        row4.addWidget(self.btn_import_wrap_pts)
        pv.addWidget(self.btn_pick)
        pv.addWidget(self.hint_label)
        pv.addWidget(self.pair_list)
        pv.addLayout(row)
        pv.addLayout(row3)
        pv.addLayout(row2)
        pv.addLayout(row4)
        vbox.addWidget(g_pts)

        # ---- 包裹 ----
        g_wrap = QGroupBox("包裹 (Wrapping 节点)")
        wf = QFormLayout(g_wrap)
        row_preset = QHBoxLayout()
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(
            ["标准(Wrapping默认)", "快速预览", "高质量(两步法第二步)", "大偏差贴合"])
        self.combo_preset.setToolTip(
            "参数预设(镜像 Wrap Gallery 工程):\n"
            "· 标准: Wrapping 节点官方默认值\n"
            "· 快速预览: 少迭代+采样对应, 几秒看大概\n"
            "· 高质量: 对应 WrapGallery 两步法第二步参数\n"
            "· 大偏差贴合: 初始对得不齐/扫描噪点多时用")
        self.btn_preset_reset = QPushButton("恢复默认")
        self.btn_preset_reset.setToolTip("全部参数恢复为「标准」预设")
        row_preset.addWidget(self.combo_preset)
        row_preset.addWidget(self.btn_preset_reset)
        wf.addRow("参数预设", row_preset)

        self.spin_icp = QSpinBox(); self.spin_icp.setRange(1, 50); self.spin_icp.setValue(5)
        self.spin_icp.setToolTip("nICPIterations: 外层ICP迭代次数(每轮重新搜索对应点)\n"
                                 "Wrap默认5. 对齐差/变形大时加到7~10")
        self.spin_opt = QSpinBox(); self.spin_opt.setRange(1, 100); self.spin_opt.setValue(20)
        self.spin_opt.setToolTip("nOptimizationIterations: 每轮ICP后的内层优化次数\n"
                                 "(对应固定, 平滑权重逐次衰减). Wrap默认20")
        self.spin_smooth_max = QDoubleSpinBox(); self.spin_smooth_max.setDecimals(3)
        self.spin_smooth_max.setRange(0.001, 100.0); self.spin_smooth_max.setValue(1.0)
        self.spin_smooth_max.setToolTip("globalSmoothWeightMax: 初始平滑权重(越大网格越硬)\n"
                                        "Wrap默认1. 两模型形状差很多时调小(0.3~0.6)")
        self.spin_smooth_min = QDoubleSpinBox(); self.spin_smooth_min.setDecimals(3)
        self.spin_smooth_min.setRange(0.001, 10.0); self.spin_smooth_min.setValue(0.05)
        self.spin_smooth_min.setToolTip("globalSmoothWeightMin: 末尾平滑权重(收尾柔软度)\n"
                                        "Wrap第一步0.05/第二步0.07. 贴不紧细节就调小")
        self.spin_p2plane = QDoubleSpinBox(); self.spin_p2plane.setDecimals(2)
        self.spin_p2plane.setRange(0.0, 10.0); self.spin_p2plane.setSingleStep(0.1)
        self.spin_p2plane.setValue(1.0)
        self.spin_p2plane.setToolTip("globalPoint2PlaneFittingWeight: 点对面拟合权重\n"
                                     "Wrap默认1(主导项), 让顶点沿表面滑动贴合")
        self.spin_p2point = QDoubleSpinBox(); self.spin_p2point.setDecimals(2)
        self.spin_p2point.setRange(0.0, 10.0); self.spin_p2point.setSingleStep(0.1)
        self.spin_p2point.setValue(0.1)
        self.spin_p2point.setToolTip("globalPoint2PointFittingWeight: 点对点拟合权重\n"
                                     "Wrap默认0.1(辅助), 调大可拉住顶点防止滑动")
        self.spin_ctrl_weight = QDoubleSpinBox(); self.spin_ctrl_weight.setDecimals(1)
        self.spin_ctrl_weight.setRange(0.0, 1000.0); self.spin_ctrl_weight.setValue(10.0)
        self.spin_ctrl_weight.setToolTip("globalControlPointsWeight: 控制点软权重\n"
                                         "Wrap默认10. 越大控制点钉得越死")
        self.spin_min_cos = QDoubleSpinBox(); self.spin_min_cos.setDecimals(2)
        self.spin_min_cos.setRange(-1.0, 1.0); self.spin_min_cos.setSingleStep(0.05)
        self.spin_min_cos.setValue(0.65)
        self.spin_min_cos.setToolTip("minCosBetweenNormals: 对应点法向兼容阈值(cos值)\n"
                                     "Wrap默认0.65(约49°). 折叠/薄壁处误对应可调低")
        self.spin_samp_min = QDoubleSpinBox(); self.spin_samp_min.setDecimals(2)
        self.spin_samp_min.setRange(0.01, 100.0); self.spin_samp_min.setValue(0.2)
        self.spin_samp_min.setToolTip("samplingMin: 初始对应搜索半径(×基础网格平均边长)\n"
                                      "Wrap默认0.2. 对齐差时调大")
        self.spin_samp_max = QDoubleSpinBox(); self.spin_samp_max.setDecimals(1)
        self.spin_samp_max.setRange(0.1, 200.0); self.spin_samp_max.setValue(5.0)
        self.spin_samp_max.setToolTip("samplingMax: 末尾对应搜索半径(×平均边长)\n"
                                      "Wrap第一步5/第二步10. 偏差大时调大")
        self.spin_min_dp = QDoubleSpinBox(); self.spin_min_dp.setDecimals(4)
        self.spin_min_dp.setRange(0.0001, 1.0); self.spin_min_dp.setValue(0.002)
        self.spin_min_dp.setToolTip("minDp: 收敛阈值(平均位移<该值×包围盒即停)\n"
                                    "Wrap默认0.002")
        self.spin_max_dp = QDoubleSpinBox(); self.spin_max_dp.setDecimals(4)
        self.spin_max_dp.setRange(0.0001, 1.0); self.spin_max_dp.setValue(0.01)
        self.spin_max_dp.setToolTip("maxDp: 单步位移钳制(×包围盒), 防发散. Wrap默认0.01")
        self.combo_corr = QComboBox()
        self.combo_corr.addItems(["精确三角面投影", "表面采样(快)"])
        self.combo_corr.setToolTip("对应搜索实现(本软件):\n· 精确投影: 准, 慢\n"
                                   "· 表面采样: 快6~14倍, 密集扫描几乎无差")
        self.spin_samples = QSpinBox(); self.spin_samples.setRange(0, 2000000)
        self.spin_samples.setSingleStep(10000); self.spin_samples.setValue(80000)
        self.spin_samples.setToolTip("仅'表面采样'模式有效: 采样点数越大越准但越慢")
        self.spin_trim = QDoubleSpinBox(); self.spin_trim.setDecimals(2)
        self.spin_trim.setRange(0.0, 0.5); self.spin_trim.setSingleStep(0.05)
        self.spin_trim.setValue(0.0)
        self.spin_trim.setToolTip("截尾比例: 每轮丢弃距离最远的对应.\n"
                                  "扫描有噪点/飞面/缺损时设 0.05~0.15")
        self.chk_rbf = QCheckBox("控制点 RBF 初对齐"); self.chk_rbf.setChecked(True)
        self.chk_rbf.setToolTip("先用控制点做整体变形初对齐(≥4对点效果最佳)")
        self.chk_lock = QCheckBox("控制点硬锁定"); self.chk_lock.setChecked(False)
        self.chk_lock.setToolTip("开启后控制点顶点被强制钉死(Wrap默认用软权重10, 不硬锁)")
        self.btn_wrap = QPushButton("开始包裹")
        self.btn_wrap.setStyleSheet("font-weight: bold; background: #2e7d32; color: white;")
        self.btn_two_step = QPushButton("两步包裹 (粗包→细分→精包)")
        self.btn_two_step.setToolTip(
            "对标 Wrap 的 WrappingInTwoSteps 流程:\n"
            "① 用当前参数粗包一遍 ② 结果中点细分(UV保留) ③ 用高质量参数精包\n"
            "高模/复杂扫描效果更好, 耗时约为两次包裹之和")
        self.progress = QProgressBar(); self.progress.setValue(0)
        self.lbl_stats = QLabel("")
        self.lbl_stats.setWordWrap(True)
        wf.addRow("ICP迭代", self.spin_icp)
        wf.addRow("优化迭代", self.spin_opt)
        wf.addRow("平滑权重(初)", self.spin_smooth_max)
        wf.addRow("平滑权重(末)", self.spin_smooth_min)
        wf.addRow("点对面权重", self.spin_p2plane)
        wf.addRow("点对点权重", self.spin_p2point)
        wf.addRow("控制点权重", self.spin_ctrl_weight)
        wf.addRow("法向兼容", self.spin_min_cos)
        wf.addRow("搜索半径(初)", self.spin_samp_min)
        wf.addRow("搜索半径(末)", self.spin_samp_max)
        wf.addRow("收敛minDp", self.spin_min_dp)
        wf.addRow("钳制maxDp", self.spin_max_dp)
        wf.addRow("对应方式", self.combo_corr)
        wf.addRow("表面采样数", self.spin_samples)
        wf.addRow("截尾比例", self.spin_trim)
        wf.addRow(self.chk_rbf)
        wf.addRow(self.chk_lock)
        wf.addRow(self.btn_wrap)
        wf.addRow(self.btn_two_step)
        wf.addRow(self.progress)
        wf.addRow(self.lbl_stats)
        vbox.addWidget(g_wrap)

        # ---- 遮罩 ----
        g_mask = QGroupBox("遮罩 (屏蔽口腔/眼球等区域)")
        mk = QVBoxLayout(g_mask)
        self.btn_mask_mode = QPushButton("进入遮罩笔刷")
        self.btn_mask_mode.setCheckable(True)
        self.btn_mask_mode.setToolTip(
            "在【基础网格】上涂抹要屏蔽的区域(红色点).\n"
            "被屏蔽的顶点不参与表面对齐, 只随周围平滑跟随 ——\n"
            "用于口腔内表面/眼球等扫描里没有对应结构、\n"
            "强行对齐会被拉变形的地方")
        row_mk = QHBoxLayout()
        row_mk.addWidget(QLabel("笔刷半径"))
        self.spin_mask_radius = QDoubleSpinBox(); self.spin_mask_radius.setDecimals(3)
        self.spin_mask_radius.setRange(0.001, 1e6); self.spin_mask_radius.setValue(0.05)
        row_mk.addWidget(self.spin_mask_radius)
        row_sem = QHBoxLayout()
        row_sem.addWidget(QLabel("语义"))
        self.combo_mask_sem = QComboBox()
        self.combo_mask_sem.addItems(["黑名单: 屏蔽涂抹区", "白名单: 仅包裹涂抹区"])
        self.combo_mask_sem.setToolTip(
            "黑名单(默认): 涂抹区被屏蔽, 仅平滑跟随(口腔/眼球用)\n"
            "白名单: 只有涂抹区参与包裹, 其余屏蔽 ——\n"
            "对应 Wrap 的 SelectPolygons 节点(选中参与面片)")
        row_sem.addWidget(self.combo_mask_sem)
        hint_mk = QLabel("左键涂抹屏蔽 | Shift+左键恢复 | Esc 退出笔刷")
        hint_mk.setStyleSheet("color: gray; font-size: 11px;")
        hint_mk.setWordWrap(True)
        row_mk2 = QHBoxLayout()
        self.btn_mask_clear = QPushButton("全部恢复")
        self.btn_mask_invert = QPushButton("反选")
        row_mk2.addWidget(self.btn_mask_clear)
        row_mk2.addWidget(self.btn_mask_invert)
        row_mk3 = QHBoxLayout()
        self.btn_mask_save = QPushButton("保存遮罩...")
        self.btn_mask_load = QPushButton("加载遮罩...")
        row_mk3.addWidget(self.btn_mask_save)
        row_mk3.addWidget(self.btn_mask_load)
        self.lbl_mask = QLabel("未设置遮罩")
        self.lbl_mask.setStyleSheet("color: gray; font-size: 11px;")
        mk.addWidget(self.btn_mask_mode)
        mk.addLayout(row_mk)
        mk.addLayout(row_sem)
        mk.addWidget(hint_mk)
        mk.addLayout(row_mk2)
        mk.addLayout(row_mk3)
        mk.addWidget(self.lbl_mask)
        vbox.addWidget(g_mask)

        # ---- 笔刷修整 ----
        g_brush = QGroupBox("笔刷修整 (Brush)")
        br = QVBoxLayout(g_brush)
        self.btn_brush_mode = QPushButton("进入笔刷")
        self.btn_brush_mode.setCheckable(True)
        self.btn_brush_mode.setToolTip(
            "对标 Wrap 的 Brush 节点: 包裹后局部修整.\n"
            "在【结果视口】拖动编辑包裹结果; 在【基础视口】拖动编辑基础网格")
        row_b1 = QHBoxLayout()
        row_b1.addWidget(QLabel("类型"))
        self.combo_brush_type = QComboBox()
        self.combo_brush_type.addItems(["移动", "平滑", "吸附到扫描面"])
        row_b1.addWidget(self.combo_brush_type)
        row_b2 = QHBoxLayout()
        row_b2.addWidget(QLabel("半径"))
        self.spin_brush_radius = QDoubleSpinBox(); self.spin_brush_radius.setDecimals(2)
        self.spin_brush_radius.setRange(0.01, 1e6); self.spin_brush_radius.setValue(14.0)
        row_b2.addWidget(self.spin_brush_radius)
        row_b2.addWidget(QLabel("强度%"))
        self.spin_brush_strength = QSpinBox(); self.spin_brush_strength.setRange(1, 100)
        self.spin_brush_strength.setValue(25)
        row_b2.addWidget(self.spin_brush_strength)
        row_b3 = QHBoxLayout()
        self.chk_brush_geo = QCheckBox("测地距离")
        self.chk_brush_geo.setToolTip("useGeodesicDistance: 沿网格表面计算笔刷范围(不穿透薄壁)")
        self.chk_brush_sym = QCheckBox("X 对称")
        self.chk_brush_sym.setToolTip("symmetry: 以世界 x=0 平面镜像涂抹")
        row_b3.addWidget(self.chk_brush_geo)
        row_b3.addWidget(self.chk_brush_sym)
        hint_b = QLabel("左键拖动涂抹 | Esc 退出 | 半径默认同 Wrap=14")
        hint_b.setStyleSheet("color: gray; font-size: 11px;")
        hint_b.setWordWrap(True)
        br.addWidget(self.btn_brush_mode)
        br.addLayout(row_b1)
        br.addLayout(row_b2)
        br.addLayout(row_b3)
        br.addWidget(hint_b)
        vbox.addWidget(g_brush)

        # ---- Blender 协同 ----
        g_bx = QGroupBox("Blender 协同")
        bx = QVBoxLayout(g_bx)
        self.exchange_dir = DEFAULT_EXCHANGE
        self.lbl_exchange = QLabel(self.exchange_dir)
        self.lbl_exchange.setWordWrap(True)
        self.lbl_exchange.setStyleSheet("color: gray; font-size: 11px;")
        row_bx = QHBoxLayout()
        self.btn_bx_dir = QPushButton("更换目录...")
        self.btn_bx_open_dir = QPushButton("打开目录")
        row_bx.addWidget(self.btn_bx_dir)
        row_bx.addWidget(self.btn_bx_open_dir)
        self.btn_bx_import = QPushButton("从交换目录导入 (base+target+points)")
        self.btn_bx_export = QPushButton("导出结果到交换目录 wrapped.obj")
        self.btn_bx_export.setEnabled(False)
        self.btn_bx_blender = QPushButton("在 Blender 中查看结果")
        self.btn_bx_blender.setEnabled(False)
        self.btn_bx_shapes = QPushButton("迁移形态键序列 shapes→shapes_wrapped")
        bx.addWidget(self.lbl_exchange)
        bx.addLayout(row_bx)
        bx.addWidget(self.btn_bx_import)
        bx.addWidget(self.btn_bx_export)
        bx.addWidget(self.btn_bx_blender)
        bx.addWidget(self.btn_bx_shapes)
        vbox.addWidget(g_bx)

        # ---- 导出 ----
        g_out = QGroupBox("导出")
        ov = QVBoxLayout(g_out)
        self.btn_save_result = QPushButton("保存包裹结果网格...")
        self.btn_save_result.setEnabled(False)
        self.btn_clear_result = QPushButton("清除包裹结果 (退回继续打点)")
        self.btn_clear_result.setEnabled(False)
        self.btn_clear_result.setToolTip("不满意结果时点此退回: 移除叠加的包裹网格,\n"
                                         "然后可以继续补打控制点/调遮罩后重新包裹")
        ov.addWidget(self.btn_save_result)
        ov.addWidget(self.btn_clear_result)
        vbox.addWidget(g_out)
        vbox.addStretch(1)

        # ---- 视口 ----
        views = QSplitter(Qt.Horizontal)
        self.base_view = Viewport("基础网格 Base", mesh_color="#9dc3e6")
        self.target_view = Viewport("扫描网格 Target + 包裹结果", mesh_color="#c8c8c8")
        views.addWidget(self.base_view)
        views.addWidget(self.target_view)

        # ---- 左侧: 可滚动面板 + 底部固定大包裹按钮 (全屏/小屏都不丢功能) ----
        from PyQt5.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        dock = QWidget()
        dock_layout = QVBoxLayout(dock)
        dock_layout.setContentsMargins(2, 2, 2, 2)
        dock_layout.addWidget(scroll)
        self.btn_wrap_bottom = QPushButton("▶ 开始包裹")
        self.btn_wrap_bottom.setMinimumHeight(44)
        self.btn_wrap_bottom.setStyleSheet(
            "font-weight: bold; font-size: 15px; background: #2e7d32; color: white;")
        self.btn_wrap_bottom.clicked.connect(self._start_wrap)
        dock_layout.addWidget(self.btn_wrap_bottom)
        dock.setMinimumWidth(340)
        dock.setMaximumWidth(480)

        splitter.addWidget(dock)
        splitter.addWidget(views)
        splitter.setStretchFactor(1, 1)

        self.statusBar().showMessage(
            "就绪. 导航: 轴标可拖动, X/Y/Z回正 ⌂居中 (Ctrl+1/3/7/0), 相机默认联动.")

        # 防误触: 参数控件未聚焦时屏蔽滚轮 (滚动页面不会误改参数)
        self._nowheel = _NoWheelFilter(self)
        for w in self.findChildren((QSpinBox, QDoubleSpinBox, QComboBox, QSlider)):
            w.installEventFilter(self._nowheel)
            if isinstance(w, (QSpinBox, QDoubleSpinBox, QComboBox)):
                w.setFocusPolicy(Qt.StrongFocus)

    def _connect(self):
        self.btn_load_base.clicked.connect(lambda: self._load_mesh("base"))
        self.btn_load_target.clicked.connect(lambda: self._load_mesh("target"))
        self.btn_align_center.clicked.connect(self._align_center)
        self.btn_align.clicked.connect(self._align_bbox)
        self.btn_align_points.clicked.connect(self._align_by_points)
        self.btn_tx[0].clicked.connect(lambda: self._nudge(0, -1))
        self.btn_tx[1].clicked.connect(lambda: self._nudge(0, +1))
        self.btn_tx[2].clicked.connect(lambda: self._nudge(1, -1))
        self.btn_tx[3].clicked.connect(lambda: self._nudge(1, +1))
        self.btn_tx[4].clicked.connect(lambda: self._nudge(2, -1))
        self.btn_tx[5].clicked.connect(lambda: self._nudge(2, +1))
        self.btn_rx[0].clicked.connect(lambda: self._rotate(0, -1))
        self.btn_rx[1].clicked.connect(lambda: self._rotate(0, +1))
        self.btn_rx[2].clicked.connect(lambda: self._rotate(1, -1))
        self.btn_rx[3].clicked.connect(lambda: self._rotate(1, +1))
        self.btn_rx[4].clicked.connect(lambda: self._rotate(2, -1))
        self.btn_rx[5].clicked.connect(lambda: self._rotate(2, +1))
        self.btn_scale_up.clicked.connect(lambda: self._scale_base(self.spin_scale.value()))
        self.btn_scale_down.clicked.connect(lambda: self._scale_base(1.0 / self.spin_scale.value()))
        self.slider_opacity.valueChanged.connect(
            lambda v: self.target_view.set_opacity(v / 100.0))
        self.btn_pick.toggled.connect(self._toggle_pick)
        self.btn_del_pair.clicked.connect(self._delete_selected_pair)
        self.btn_clear_pairs.clicked.connect(self._clear_pairs)
        self.btn_cancel_pending.clicked.connect(self._cancel_pending)
        self.btn_re_base.clicked.connect(lambda: self._start_reassign("base"))
        self.btn_re_target.clicked.connect(lambda: self._start_reassign("target"))
        self.btn_save_points.clicked.connect(self._save_points)
        self.btn_load_points.clicked.connect(self._load_points)
        self.btn_export_wrap_pts.clicked.connect(self._export_wrap_points)
        self.btn_import_wrap_pts.clicked.connect(self._import_wrap_points)
        self.btn_wrap.clicked.connect(self._start_wrap)
        self.btn_two_step.clicked.connect(self._start_two_step)
        self.btn_save_result.clicked.connect(self._save_result)
        self.btn_clear_result.clicked.connect(self._clear_result)
        self.combo_preset.currentTextChanged.connect(self._apply_preset)
        self.btn_preset_reset.clicked.connect(
            lambda: self.combo_preset.setCurrentText("标准(Wrapping默认)"))
        self.btn_mask_mode.toggled.connect(self._toggle_mask)
        self.btn_mask_clear.clicked.connect(self._mask_clear)
        self.btn_mask_invert.clicked.connect(self._mask_invert)
        self.btn_mask_save.clicked.connect(self._mask_save)
        self.btn_mask_load.clicked.connect(self._mask_load)
        self.btn_brush_mode.toggled.connect(self._toggle_brush)
        self.base_view.brush_started.connect(lambda p, v: self._brush_event("base", "start", p, v))
        self.base_view.brush_moved.connect(lambda p, v: self._brush_event("base", "move", p, v))
        self.base_view.brush_ended.connect(lambda: self._brush_event("base", "end", None, -1))
        self.target_view.brush_started.connect(lambda p, v: self._brush_event("target", "start", p, v))
        self.target_view.brush_moved.connect(lambda p, v: self._brush_event("target", "move", p, v))
        self.target_view.brush_ended.connect(lambda: self._brush_event("target", "end", None, -1))
        self.btn_bx_dir.clicked.connect(self._bx_choose_dir)
        self.btn_bx_open_dir.clicked.connect(self._bx_open_dir)
        self.btn_bx_import.clicked.connect(self._bx_import)
        self.btn_bx_export.clicked.connect(self._bx_export_result)
        self.btn_bx_blender.clicked.connect(self._bx_open_in_blender)
        self.btn_bx_shapes.clicked.connect(self._bx_transfer_shapes)
        self.pair_list.currentRowChanged.connect(self._refresh_markers)
        self.pair_list.itemChanged.connect(self._on_pair_renamed)
        self.base_view.surface_clicked.connect(lambda p, v: self._on_click("base", p, v))
        self.target_view.surface_clicked.connect(lambda p, v: self._on_click("target", p, v))
        self.base_view.camera_changed.connect(lambda: self._sync_camera(self.base_view))
        self.target_view.camera_changed.connect(lambda: self._sync_camera(self.target_view))

    # ================= 网格加载 =================
    def _load_mesh(self, which: str):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择网格文件", "",
            "网格文件 (*.obj *.ply *.stl *.off *.wrl *.glb *.gltf);;所有文件 (*)")
        if path:
            self._set_mesh(which, path)

    def _set_mesh(self, which: str, path: str) -> bool:
        try:
            mesh = load_mesh(path, y_up_to_z_up=self.chk_yup.isChecked())
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))
            return False
        if which == "base":
            self.base_mesh, self.base_path = mesh, path
            self.base_view.set_mesh(mesh, opacity=1.0)
            self.lbl_base.setText(f"{os.path.basename(path)}\n{mesh_stats(mesh)}")
            self._suggest_step()
            # 新基础网格: 遮罩重置, 笔刷半径给推荐值
            self._painted = None
            self.base_view.set_mask_points(None)
            self.lbl_mask.setText("未设置遮罩")
            if mesh.bounds is not None:
                diag = float(np.linalg.norm(mesh.bounds[1] - mesh.bounds[0]))
                if diag > 0:
                    self.spin_mask_radius.setValue(round(diag * 0.03, 4))
        else:
            self.target_mesh, self.target_path = mesh, path
            self.target_view.set_mesh(mesh, opacity=self.slider_opacity.value() / 100.0)
            self.lbl_target.setText(f"{os.path.basename(path)}\n{mesh_stats(mesh)}")
            self._suggest_step()
        self.wrapped_mesh = None
        self.target_view.set_overlay(None)
        self.btn_save_result.setEnabled(False)
        self.btn_bx_export.setEnabled(False)
        self.btn_bx_blender.setEnabled(False)
        self._update_hint()
        return True

    # ================= 参数预设 =================
    PRESETS = {
        "标准(Wrapping默认)": dict(icp=5, opt=20, smax=1.0, smin=0.05, p2plane=1.0,
                                p2point=0.1, ctrl=10.0, mincos=0.65,
                                sampmin=0.2, sampmax=5.0, corr=0, samples=80000, trim=0.0),
        "快速预览": dict(icp=3, opt=8, smax=1.0, smin=0.05, p2plane=1.0,
                      p2point=0.1, ctrl=10.0, mincos=0.65,
                      sampmin=0.3, sampmax=8.0, corr=1, samples=40000, trim=0.0),
        "高质量(两步法第二步)": dict(icp=5, opt=20, smax=1.0, smin=0.07, p2plane=1.0,
                              p2point=0.1, ctrl=10.0, mincos=0.65,
                              sampmin=0.7, sampmax=10.0, corr=0, samples=150000, trim=0.0),
        "大偏差贴合": dict(icp=7, opt=20, smax=0.5, smin=0.03, p2plane=1.0,
                       p2point=0.15, ctrl=10.0, mincos=0.5,
                       sampmin=0.5, sampmax=15.0, corr=0, samples=80000, trim=0.1),
    }

    def _apply_preset(self, name: str):
        p = self.PRESETS.get(name)
        if p is None:
            return
        self.spin_icp.setValue(p["icp"])
        self.spin_opt.setValue(p["opt"])
        self.spin_smooth_max.setValue(p["smax"])
        self.spin_smooth_min.setValue(p["smin"])
        self.spin_p2plane.setValue(p["p2plane"])
        self.spin_p2point.setValue(p["p2point"])
        self.spin_ctrl_weight.setValue(p["ctrl"])
        self.spin_min_cos.setValue(p["mincos"])
        self.spin_samp_min.setValue(p["sampmin"])
        self.spin_samp_max.setValue(p["sampmax"])
        self.combo_corr.setCurrentIndex(p["corr"])
        self.spin_samples.setValue(p["samples"])
        self.spin_trim.setValue(p["trim"])
        self.statusBar().showMessage(f"已应用预设「{name}」(误改可点「恢复默认」)")

    # ================= 笔刷修整 =================
    def _toggle_brush(self, checked: bool):
        self.brush_mode = checked
        if checked:
            if self.pick_mode:
                self.btn_pick.setChecked(False)
            if self.mask_mode:
                self.btn_mask_mode.setChecked(False)
            self.btn_brush_mode.setText("退出笔刷")
            self.base_view.set_brush_enabled(True)
            self.target_view.set_brush_enabled(True)
            self.hint_label.setText("笔刷: 结果视口编辑包裹结果, 基础视口编辑基础网格. Esc 退出")
        else:
            self.btn_brush_mode.setText("进入笔刷")
            self.base_view.set_brush_enabled(False)
            self.target_view.set_brush_enabled(False)
            self._update_hint()

    def _brush_event(self, side: str, phase: str, pos, vid: int):
        from wrapclone.brush import MeshBrush
        if side == "base":
            mesh, view = self.base_mesh, self.base_view
        else:
            mesh, view = self.wrapped_mesh, self.target_view
            if mesh is None:
                if phase == "start":
                    self.hint_label.setText("结果视口需先完成一次包裹; 或到基础视口编辑基础网格")
                return
        if phase == "start":
            self._brush_last = pos.copy()
            self._brush_obj = MeshBrush(mesh)
            self._brush_view = view
            self._brush_side = side
            if self.combo_brush_type.currentIndex() != 0:
                self._brush_apply(pos)      # 平滑/吸附按下即生效
            self._brush_refresh()
        elif phase == "move" and getattr(self, "_brush_obj", None) is not None:
            if self.combo_brush_type.currentIndex() == 0:
                delta = pos - self._brush_last
                if np.linalg.norm(delta) > 1e-9:
                    self._brush_obj.stroke_move(
                        self._brush_last, delta,
                        radius=self.spin_brush_radius.value(),
                        strength=self.spin_brush_strength.value(),
                        geodesic=self.chk_brush_geo.isChecked(),
                        symmetry=self.chk_brush_sym.isChecked())
                    self._brush_last = pos.copy()
                    self._brush_refresh()
            else:
                self._brush_apply(pos)
                self._brush_refresh()

    def _brush_apply(self, pos):
        idx = self.combo_brush_type.currentIndex()
        if idx == 1:
            self._brush_obj.stroke_smooth(
                pos, radius=self.spin_brush_radius.value(),
                strength=self.spin_brush_strength.value(),
                geodesic=self.chk_brush_geo.isChecked(),
                symmetry=self.chk_brush_sym.isChecked())
        elif idx == 2 and self.target_mesh is not None:
            self._brush_obj.stroke_attract(
                pos, self.target_mesh, radius=self.spin_brush_radius.value(),
                strength=self.spin_brush_strength.value(),
                geodesic=self.chk_brush_geo.isChecked(),
                symmetry=self.chk_brush_sym.isChecked())

    def _brush_refresh(self):
        side = getattr(self, "_brush_side", None)
        if side == "base":
            self.base_view.refresh_mesh()
            self._refresh_markers()
        elif side == "target":
            self.target_view.refresh_overlay()

    # ================= 两步包裹 =================
    def _start_two_step(self):
        if self.base_mesh is None or self.target_mesh is None:
            QMessageBox.information(self, "提示", "请先加载基础网格和扫描网格")
            return
        if self._wrap_thread is not None and self._wrap_thread.isRunning():
            return
        use_pairs = list(self.pairs.pairs)
        src_pts = np.array([p.base_pos for p in use_pairs]) if use_pairs else None
        dst_pts = np.array([p.target_pos for p in use_pairs]) if use_pairs else None
        src_ids = np.array([p.base_vid for p in use_pairs], dtype=np.int64) if use_pairs else None
        k1 = self._wrap_kwargs(src_pts, dst_pts, src_ids)
        # 第二步: 高质量参数 (Wrap SecondWrapping: smoothMin 0.07, sampling 0.7/10)
        p2 = self.PRESETS["高质量(两步法第二步)"]
        k2 = self._wrap_kwargs(src_pts, dst_pts, src_ids)
        k2.update(smooth_weight_min=p2["smin"], sampling_min=p2["sampmin"],
                  sampling_max=p2["sampmax"])
        info = dict(mask=self._engine_mask(), src_ctrl_ids=src_ids)
        self.btn_wrap.setEnabled(False)
        self.btn_wrap_bottom.setEnabled(False)
        self.btn_two_step.setEnabled(False)
        self.btn_wrap_bottom.setText("⏳ 两步包裹中...")
        self.progress.setRange(0, 0)
        self.lbl_stats.setText("两步包裹: 第一步粗包...")
        self._first_progress = True
        self._wrap_thread = TwoStepThread(self.base_mesh, self.target_mesh, k1, k2, info, self)
        self._wrap_thread.stage.connect(lambda s: self.lbl_stats.setText(s))
        self._wrap_thread.progressed.connect(self._on_wrap_progress)
        self._wrap_thread.done.connect(self._on_wrap_done)
        self._wrap_thread.failed.connect(self._on_wrap_failed)
        self._wrap_thread.start()

    def _wrap_kwargs(self, src_pts, dst_pts, src_ids) -> dict:
        return dict(
            src_ctrl=src_pts, dst_ctrl=dst_pts, src_ctrl_ids=src_ids,
            mask=self._engine_mask(),
            n_icp_iterations=self.spin_icp.value(),
            n_optimization_iterations=self.spin_opt.value(),
            smooth_weight_max=self.spin_smooth_max.value(),
            smooth_weight_min=self.spin_smooth_min.value(),
            point2plane_weight=self.spin_p2plane.value(),
            point2point_weight=self.spin_p2point.value(),
            control_points_weight=self.spin_ctrl_weight.value(),
            min_cos_normals=self.spin_min_cos.value(),
            sampling_min=self.spin_samp_min.value(),
            sampling_max=self.spin_samp_max.value(),
            min_dp=self.spin_min_dp.value(),
            max_dp=self.spin_max_dp.value(),
            correspondence="surface" if self.combo_corr.currentIndex() == 0 else "samples",
            target_samples=self.spin_samples.value(),
            trim_fraction=self.spin_trim.value(),
            use_rbf_init=self.chk_rbf.isChecked(),
            lock_control_points=self.chk_lock.isChecked(),
        )

    # ================= 遮罩 =================
    def _toggle_mask(self, checked: bool):
        self.mask_mode = checked
        if checked:
            if self.pick_mode:
                self.btn_pick.setChecked(False)
            if self.base_mesh is None:
                QMessageBox.information(self, "提示", "请先加载基础网格")
                self.btn_mask_mode.setChecked(False)
                return
            self._ensure_painted()
            self.btn_mask_mode.setText("退出遮罩笔刷")
            self.base_view.set_pick_enabled(True)   # 借用拾取通道接收点击
            self.hint_label.setText("遮罩笔刷: 在【基础网格】上左键涂抹(红点), "
                                    "Shift+左键擦除, Esc 退出")
        else:
            self.btn_mask_mode.setText("进入遮罩笔刷")
            if not self.pick_mode:
                self.base_view.set_pick_enabled(False)
            self._update_hint()
        self._update_mask_display()

    def _ensure_painted(self):
        if self.base_mesh is not None and (
                self._painted is None or len(self._painted) != len(self.base_mesh.vertices)):
            self._painted = np.zeros(len(self.base_mesh.vertices), dtype=bool)

    def _engine_mask(self):
        """按语义生成引擎遮罩: 黑名单=涂抹区0其余1; 白名单=涂抹区1其余0."""
        if self.base_mesh is None or self._painted is None:
            return None
        if not self._painted.any():
            return None
        if self.combo_mask_sem.currentIndex() == 1:   # 白名单
            return self._painted.astype(float)
        return (~self._painted).astype(float)          # 黑名单

    def _mask_brush(self, pos: np.ndarray, vid: int, restore: bool):
        if self.base_mesh is None:
            return
        self._ensure_painted()
        r = self.spin_mask_radius.value()
        verts = np.asarray(self.base_mesh.vertices)
        d = np.linalg.norm(verts - pos, axis=1)
        sel = d <= r
        self._painted[sel] = not restore
        self._update_mask_display()
        n = int(self._painted.sum())
        self.lbl_mask.setText(f"已涂抹 {n} 顶点 ({100.0*n/len(self._painted):.1f}%)")

    def _update_mask_display(self):
        if self.base_mesh is not None and self._painted is not None:
            pts = np.asarray(self.base_mesh.vertices)[self._painted]
            self.base_view.set_mask_points(pts)
        else:
            self.base_view.set_mask_points(None)

    def _mask_clear(self):
        if self._painted is not None:
            self._painted[:] = False
        self._update_mask_display()
        self.lbl_mask.setText("未设置遮罩")

    def _mask_invert(self):
        if self.base_mesh is None:
            return
        self._ensure_painted()
        self._painted = ~self._painted
        self._update_mask_display()
        n = int(self._painted.sum())
        self.lbl_mask.setText(f"已涂抹 {n} 顶点 ({100.0*n/len(self._painted):.1f}%)")

    def _mask_save(self):
        if self._painted is None or self.base_mesh is None or not self._painted.any():
            QMessageBox.information(self, "提示", "没有遮罩可保存")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存遮罩", "", "遮罩文件 (*.json)")
        if not path:
            return
        import json
        ids = np.where(self._painted)[0].tolist()
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"painted_vertices": ids,
                       "semantic": "white" if self.combo_mask_sem.currentIndex() == 1 else "black",
                       # 兼容旧格式: 黑名单时 masked=painted
                       "masked_vertices": ids}, f)
        self.statusBar().showMessage(f"遮罩已保存: {path}")

    def _mask_load(self):
        if self.base_mesh is None:
            QMessageBox.information(self, "提示", "请先加载基础网格")
            return
        path, _ = QFileDialog.getOpenFileName(self, "加载遮罩", "", "遮罩文件 (*.json)")
        if not path:
            return
        import json
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            ids = data.get("painted_vertices", data.get("masked_vertices", []))
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))
            return
        self._ensure_painted()
        self._painted[:] = False
        ids = np.asarray(ids, dtype=np.int64)
        ids = ids[(ids >= 0) & (ids < len(self._painted))]
        self._painted[ids] = True
        if data.get("semantic") == "white":
            self.combo_mask_sem.setCurrentIndex(1)
        self._update_mask_display()
        self.lbl_mask.setText(f"已涂抹 {len(ids)} 顶点 (加载)")

    # ================= 清除结果 =================
    def _clear_result(self):
        self.wrapped_mesh = None
        self.target_view.set_overlay(None)
        self.btn_save_result.setEnabled(False)
        self.btn_bx_export.setEnabled(False)
        self.btn_bx_blender.setEnabled(False)
        self.btn_clear_result.setEnabled(False)
        self.lbl_stats.setText("结果已清除, 可继续打点后重新包裹")
        self.statusBar().showMessage("已退回, 继续调整")

    # ================= 对齐 =================
    def _align_which(self) -> str:
        return "base" if self.combo_align_target.currentIndex() == 0 else "target"

    def _align_meshes(self):
        """返回 (选中模型, 另一模型, which), 缺一个则 (None, None, which)."""
        which = self._align_which()
        if which == "base":
            return self.base_mesh, self.target_mesh, which
        return self.target_mesh, self.base_mesh, which

    def _suggest_step(self):
        """按目标包围盒的 1% 推荐平移步长."""
        m = self.target_mesh if self.target_mesh is not None else self.base_mesh
        if m is not None and m.bounds is not None:
            diag = float(np.linalg.norm(m.bounds[1] - m.bounds[0]))
            if diag > 0:
                self.spin_step.setValue(round(diag * 0.01, 4))

    def _transform_obj(self, which: str, R, t, s):
        """对指定模型与其控制点侧施加相似变换, 原地刷新显示(不动相机)."""
        mesh = self.base_mesh if which == "base" else self.target_mesh
        view = self.base_view if which == "base" else self.target_view
        mesh.vertices = apply_transform(mesh.vertices, R, t, s)
        for p in self.pairs.pairs:
            key = "base_pos" if which == "base" else "target_pos"
            setattr(p, key, list(apply_transform(np.array([getattr(p, key)]), R, t, s)[0]))
        view.refresh_mesh()
        self._refresh_markers()
        if which == "base":
            self._update_mask_display()
        # 模型变了, 旧包裹结果作废
        self.wrapped_mesh = None
        self.target_view.set_overlay(None)
        self.btn_save_result.setEnabled(False)
        self.btn_bx_export.setEnabled(False)
        self.btn_bx_blender.setEnabled(False)

    def _align_center(self):
        mesh, other, which = self._align_meshes()
        if mesh is None or other is None:
            QMessageBox.information(self, "提示", "请先加载两个网格")
            return
        t = other.bounds.mean(axis=0) - mesh.bounds.mean(axis=0)
        self._transform_obj(which, np.eye(3), t, 1.0)
        self.statusBar().showMessage(f"已中心对齐 ({which}, 仅平移)")

    def _align_bbox(self):
        mesh, other, which = self._align_meshes()
        if mesh is None or other is None:
            QMessageBox.information(self, "提示", "请先加载两个网格")
            return
        mc = mesh.bounds.mean(axis=0)
        oc = other.bounds.mean(axis=0)
        ms = np.linalg.norm(mesh.bounds[1] - mesh.bounds[0])
        os_ = np.linalg.norm(other.bounds[1] - other.bounds[0])
        s = os_ / ms if ms > 0 else 1.0
        self._transform_obj(which, np.eye(3), oc - s * mc, s)
        self.statusBar().showMessage(f"已按包围盒对齐 ({which}, 缩放 {s:.4f})")

    def _align_by_points(self):
        """用当前 ≥3 对控制点把选中模型刚体对齐到另一个模型."""
        mesh, other, which = self._align_meshes()
        if mesh is None or other is None:
            QMessageBox.information(self, "提示", "请先加载两个网格")
            return
        if len(self.pairs) < 3:
            QMessageBox.information(
                self, "控制点不足",
                "需要至少 3 对控制点.\n\n用法: 先进入打点模式, 在两个模型上交替点击\n"
                "标出 3 对以上对应点(如: 鼻尖/左眼角/右眼角),\n再点本按钮, 选中模型会自动贴合过去.")
            return
        if which == "base":
            R, t, s = umeyama(self.pairs.base_points(), self.pairs.target_points(),
                              with_scale=True)
        else:
            R, t, s = umeyama(self.pairs.target_points(), self.pairs.base_points(),
                              with_scale=True)
        self._transform_obj(which, R, t, s)
        self.statusBar().showMessage(f"已用 {len(self.pairs)} 对点对齐 ({which}, 缩放 {s:.4f})")

    def _nudge(self, axis: int, sign: int):
        mesh, _, which = self._align_meshes()
        if mesh is None:
            return
        d = np.zeros(3); d[axis] = sign * self.spin_step.value()
        self._transform_obj(which, np.eye(3), d, 1.0)

    def _rotate(self, axis: int, sign: int):
        mesh, _, which = self._align_meshes()
        if mesh is None:
            return
        ang = np.deg2rad(sign * self.spin_angle.value())
        c, sn = np.cos(ang), np.sin(ang)
        R = np.eye(3)
        if axis == 0:
            R = np.array([[1, 0, 0], [0, c, -sn], [0, sn, c]])
        elif axis == 1:
            R = np.array([[c, 0, sn], [0, 1, 0], [-sn, 0, c]])
        else:
            R = np.array([[c, -sn, 0], [sn, c, 0], [0, 0, 1]])
        center = mesh.bounds.mean(axis=0)
        t = center - R @ center
        self._transform_obj(which, R, t, 1.0)

    def _scale_base(self, factor: float):
        mesh, _, which = self._align_meshes()
        if mesh is None:
            return
        center = mesh.bounds.mean(axis=0)
        self._transform_obj(which, np.eye(3), center - factor * center, factor)

    def _sync_camera(self, src: Viewport):
        """相机联动: 33ms 合并节流, 高模下双视口不掉帧."""
        if not self.chk_sync.isChecked() or self._syncing_camera:
            return
        self._sync_pending = src
        if getattr(self, "_sync_timer_active", False):
            return
        self._sync_timer_active = True
        QTimer.singleShot(33, self._do_sync_camera)

    def _do_sync_camera(self):
        self._sync_timer_active = False
        src = self._sync_pending
        self._sync_pending = None
        if src is None or not self.chk_sync.isChecked():
            return
        self._syncing_camera = True
        try:
            dst = self.target_view if src is self.base_view else self.base_view
            dst.set_camera(src.get_camera())   # 取当前最新状态, 积压自动合并
        finally:
            self._syncing_camera = False

    # ================= 打点 =================
    def _toggle_pick(self, checked: bool):
        self.pick_mode = checked
        if checked and self.mask_mode:
            self.btn_mask_mode.setChecked(False)
        self.btn_pick.setText("退出打点模式" if checked else "进入打点模式")
        self.base_view.set_pick_enabled(checked)
        self.target_view.set_pick_enabled(checked)
        if checked:
            # 打点时: 隐藏包裹结果层(避免遮挡干扰), 强制不透明便于准确落点
            self._saved_opacity = self.slider_opacity.value()
            self.target_view.set_overlay(None)
            self.base_view.set_opacity(1.0)
            self.target_view.set_opacity(1.0)
        else:
            self.base_view.set_opacity(1.0)
            self.target_view.set_opacity(self.slider_opacity.value() / 100.0)
            if self.wrapped_mesh is not None:
                self.target_view.set_overlay(self.wrapped_mesh)   # 恢复结果层
        self._update_hint()

    def _start_reassign(self, side: str):
        row = self.pair_list.currentRow()
        if row < 0 or row >= len(self.pairs):
            QMessageBox.information(self, "提示", "请先在列表中选中要修改的点对")
            return
        if not self.pick_mode:
            self.btn_pick.setChecked(True)
        self._reassign = (side, row)
        mesh_name = "基础网格" if side == "base" else "扫描网格"
        self.hint_label.setText(
            f"重设 {self.pairs.pairs[row].name}: 请在【{mesh_name}】上点击新位置 (Esc 取消)")

    def _on_click(self, side: str, pos: np.ndarray, vid: int):
        # 遮罩笔刷模式: 只作用于基础网格
        if self.mask_mode:
            if side != "base":
                self.hint_label.setText("遮罩只画在【基础网格】上 (蓝色视口)")
                return
            restore = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)
            self._mask_brush(pos, vid, restore)
            return
        if side == "base" and self.base_mesh is None:
            return
        if side == "target" and self.target_mesh is None:
            return
        # 重设模式: 更新已有点对的某一侧
        if self._reassign is not None:
            rside, row = self._reassign
            if side != rside:
                return
            p = self.pairs.pairs[row]
            if side == "base":
                p.base_pos = [float(x) for x in pos]; p.base_vid = int(vid)
            else:
                p.target_pos = [float(x) for x in pos]; p.target_vid = int(vid)
            self._reassign = None
            self._rebuild_pair_list()
            self.pair_list.setCurrentRow(row)
            return
        self.pending[side] = (pos.copy(), vid)
        if "base" in self.pending and "target" in self.pending:
            (bp, bv), (tp, tv) = self.pending["base"], self.pending["target"]
            pair = self.pairs.add(bp, tp, base_vid=bv, target_vid=tv)
            self.pending.clear()
            self._add_pair_item(pair, len(self.pairs) - 1)
        self._refresh_markers()
        self._update_hint()

    def _add_pair_item(self, pair, idx):
        item = QListWidgetItem(self._pair_text(pair, idx))
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        item.setData(Qt.UserRole, idx)
        self.pair_list.addItem(item)

    def _on_pair_renamed(self, item):
        """列表内直接编辑改名 (编辑 '序号. 名字 ...' 中的名字部分)."""
        row = self.pair_list.row(item)
        if not (0 <= row < len(self.pairs)):
            return
        text = item.text()
        try:
            name_part = text.split(".", 1)[1].split()[0]
            if name_part:
                self.pairs.pairs[row].name = name_part
        except Exception:
            pass
        self.pair_list.blockSignals(True)
        item.setText(self._pair_text(self.pairs.pairs[row], row))
        self.pair_list.blockSignals(False)
        self._refresh_markers()

    def _pair_text(self, pair, idx):
        b = np.array2string(np.array(pair.base_pos), precision=2, separator=",")
        t = np.array2string(np.array(pair.target_pos), precision=2, separator=",")
        return f"{idx+1}. {pair.name}  {b} -> {t}"

    def _delete_selected_pair(self):
        row = self.pair_list.currentRow()
        if row < 0:
            return
        self.pairs.remove(row)
        self._rebuild_pair_list()

    def _clear_pairs(self):
        self.pairs.clear()
        self.pending.clear()
        self._rebuild_pair_list()

    def _cancel_pending(self):
        self.pending.clear()
        self._reassign = None
        self._refresh_markers()
        self._update_hint()

    def _rebuild_pair_list(self):
        self.pair_list.blockSignals(True)
        self.pair_list.clear()
        for i, p in enumerate(self.pairs.pairs):
            self._add_pair_item(p, i)
        self.pair_list.blockSignals(False)
        self._refresh_markers()
        self._update_hint()

    def _refresh_markers(self):
        hi = self.pair_list.currentRow()
        self.base_view.set_markers(
            self.pairs.base_points(), [p.name for p in self.pairs.pairs],
            color="#e53935", pending=self.pending.get("base", (None,))[0],
            highlight_index=hi)
        self.target_view.set_markers(
            self.pairs.target_points(), [p.name for p in self.pairs.pairs],
            color="#1e88e5", pending=self.pending.get("target", (None,))[0],
            highlight_index=hi)

    def _update_hint(self):
        if self._reassign is not None:
            return  # 重设提示由 _start_reassign 维护
        if not self.pick_mode:
            self.hint_label.setText(f"共 {len(self.pairs)} 对. 点击「进入打点模式」开始标注.")
            return
        n = len(self.pairs) + 1
        if "base" not in self.pending:
            self.hint_label.setText(f"第 {n} 对: 请在【基础网格】上点击放置点")
        else:
            self.hint_label.setText(f"第 {n} 对: 请在【扫描网格】上点击对应点")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.brush_mode:
                self.btn_brush_mode.setChecked(False)
            elif self.mask_mode:
                self.btn_mask_mode.setChecked(False)
            else:
                self._cancel_pending()
        super().keyPressEvent(event)

    # ================= 点对存取 =================
    def _save_points(self):
        if len(self.pairs) == 0:
            QMessageBox.information(self, "提示", "没有点对可保存")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存点对", "", "点对文件 (*.json)")
        if path:
            self.pairs.save(path)
            self.statusBar().showMessage(f"点对已保存: {path}")

    def _load_points(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载点对", "", "点对文件 (*.json)")
        if not path:
            return
        try:
            self.pairs.load(path)
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))
            return
        if self.pairs.unresolved and self.base_mesh is not None and self.target_mesh is not None:
            self.pairs.resolve_positions(self.base_mesh, self.target_mesh)
        self.pending.clear()
        self._rebuild_pair_list()

    def _export_wrap_points(self):
        if len(self.pairs) == 0:
            QMessageBox.information(self, "提示", "没有点对可导出")
            return
        if self.base_mesh is None or self.target_mesh is None:
            QMessageBox.information(self, "提示", "请先加载两个网格")
            return
        d = QFileDialog.getExistingDirectory(self, "选择导出目录 (生成 base/target 两个 .txt)")
        if not d:
            return
        try:
            self.pairs.save_wrap_format(
                self.base_mesh, self.target_mesh,
                os.path.join(d, "base_points.txt"), os.path.join(d, "target_points.txt"))
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
            return
        self.statusBar().showMessage(f"已导出 Wrap 格式点对到 {d}")

    def _import_wrap_points(self):
        if self.base_mesh is None or self.target_mesh is None:
            QMessageBox.information(self, "提示", "请先加载两个网格")
            return
        pb, _ = QFileDialog.getOpenFileName(self, "选择基础侧点文件", "", "点文件 (*.txt *.json)")
        if not pb:
            return
        pt, _ = QFileDialog.getOpenFileName(self, "选择扫描侧点文件", "", "点文件 (*.txt *.json)")
        if not pt:
            return
        try:
            self.pairs.load_wrap_format(self.base_mesh, self.target_mesh, pb, pt)
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))
            return
        self.pending.clear()
        self._rebuild_pair_list()
        self.statusBar().showMessage(f"已导入 {len(self.pairs)} 对 Wrap 格式点")

    # ================= 包裹 =================
    def _start_wrap(self):
        if self.base_mesh is None or self.target_mesh is None:
            QMessageBox.information(self, "提示", "请先加载基础网格和扫描网格")
            return
        if self._wrap_thread is not None and self._wrap_thread.isRunning():
            return
        if len(self.pairs) < 4 and self.chk_rbf.isChecked():
            ret = QMessageBox.question(
                self, "控制点不足",
                "RBF 初对齐建议至少 4 对控制点, 当前 "
                f"{len(self.pairs)} 对. 仍要继续吗?")
            if ret != QMessageBox.Yes:
                return
        if self.pending:
            QMessageBox.information(self, "提示", "存在未完成的待定点, 请先完成或按 Esc 取消")
            return

        # 去重: 同一基础顶点被多个点对使用会致 RBF 奇异, 保留最后一次并提示
        use_pairs = list(self.pairs.pairs)
        seen, dup = set(), 0
        uniq = []
        for p in reversed(use_pairs):
            if p.base_vid >= 0 and p.base_vid in seen:
                dup += 1
                continue
            seen.add(p.base_vid)
            uniq.append(p)
        uniq.reverse()
        if dup:
            self.statusBar().showMessage(f"提示: {dup} 个重复基础顶点的点对已忽略")
        src_pts = np.array([p.base_pos for p in uniq]) if uniq else None
        dst_pts = np.array([p.target_pos for p in uniq]) if uniq else None
        src_ids = np.array([p.base_vid for p in uniq], dtype=np.int64) if uniq else None

        kwargs = self._wrap_kwargs(src_pts, dst_pts, src_ids)
        # 即时反馈: 按钮置灰+忙碌进度条, 初始化在线程内进行不卡界面
        self.btn_wrap.setEnabled(False)
        self.btn_wrap_bottom.setEnabled(False)
        self.btn_wrap_bottom.setText("⏳ 包裹中...")
        self.progress.setRange(0, 0)          # 忙碌模式(来回滚动)
        self.lbl_stats.setText("正在初始化: 构建表面搜索结构...")
        self._first_progress = True
        self._wrap_thread = WrapThread(self.base_mesh, self.target_mesh, kwargs, self)
        self._wrap_thread.progressed.connect(self._on_wrap_progress)
        self._wrap_thread.done.connect(self._on_wrap_done)
        self._wrap_thread.failed.connect(self._on_wrap_failed)
        self._wrap_thread.start()

    def _restore_wrap_ui(self):
        self.btn_wrap.setEnabled(True)
        self.btn_wrap_bottom.setEnabled(True)
        self.btn_two_step.setEnabled(True)
        self.btn_wrap_bottom.setText("▶ 开始包裹")
        self.progress.setRange(0, 100)

    def _on_wrap_progress(self, i, n, mean_d):
        if self._first_progress:
            self._first_progress = False
            self.progress.setRange(0, 100)    # 初始化完, 切回百分比
        self.progress.setValue(int(100 * i / n))
        self.lbl_stats.setText(f"迭代 {i}/{n}  平均对应距离 {mean_d:.5f}")

    def _on_wrap_done(self, result):
        self._restore_wrap_ui()
        self.wrapped_mesh = result.mesh
        self.target_view.set_overlay(self.wrapped_mesh)
        self.btn_save_result.setEnabled(True)
        self.btn_bx_export.setEnabled(True)
        self.btn_bx_blender.setEnabled(True)
        self.btn_clear_result.setEnabled(True)
        # 自动调低扫描透明度, 透出包裹结果
        if self.slider_opacity.value() > 50:
            self.slider_opacity.setValue(50)
        s = result.stats
        mask_info = f"  屏蔽顶点 {s['masked_vertices']}" if s.get("masked_vertices") else ""
        self.lbl_stats.setText(
            f"完成! 到表面距离: mean={s['mean_dist']:.5f}  "
            f"p95={s['p95_dist']:.5f}{mask_info}")
        self.statusBar().showMessage("包裹完成")

    def _on_wrap_failed(self, msg):
        self._restore_wrap_ui()
        self.lbl_stats.setText("包裹失败")
        QMessageBox.critical(self, "包裹失败", msg)

    # ================= 导出 =================
    def _save_result(self):
        if self.wrapped_mesh is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存包裹结果", "wrapped.obj", "OBJ (*.obj);;PLY (*.ply);;STL (*.stl)")
        if not path:
            return
        try:
            save_mesh(self.wrapped_mesh, path)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return
        self.statusBar().showMessage(f"已保存: {path}")

    # ================= Blender 协同 =================
    def _bx_choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择 Blender 交换目录", self.exchange_dir)
        if d:
            self.exchange_dir = d
            self.lbl_exchange.setText(d)

    def _bx_open_dir(self):
        os.makedirs(self.exchange_dir, exist_ok=True)
        try:
            os.startfile(self.exchange_dir)
        except Exception as e:
            QMessageBox.warning(self, "无法打开", str(e))

    def _bx_import(self):
        d = self.exchange_dir
        ok = True
        bp = os.path.join(d, "base.obj")
        tp = os.path.join(d, "target.obj")
        pp = os.path.join(d, "points.json")
        if os.path.isfile(bp):
            ok = self._set_mesh("base", bp) and ok
        if os.path.isfile(tp):
            ok = self._set_mesh("target", tp) and ok
        if os.path.isfile(pp) and self.base_mesh is not None and self.target_mesh is not None:
            try:
                self.pairs.load(pp)
                if self.pairs.unresolved:
                    self.pairs.resolve_positions(self.base_mesh, self.target_mesh)
                self.pending.clear()
                self._rebuild_pair_list()
            except Exception as e:
                QMessageBox.critical(self, "点对加载失败", str(e))
        if not os.path.isfile(bp) and not os.path.isfile(tp):
            QMessageBox.information(self, "交换目录为空", f"{d} 中没有 base.obj/target.obj")
        self.statusBar().showMessage(f"从交换目录导入完成, 点对 {len(self.pairs)}")

    def _bx_export_result(self):
        if self.wrapped_mesh is None:
            return
        path = os.path.join(self.exchange_dir, "wrapped.obj")
        try:
            save_mesh(self.wrapped_mesh, path)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
            return
        self.statusBar().showMessage(f"已导出到交换目录: {path}")

    def _bx_open_in_blender(self):
        if self.wrapped_mesh is None:
            return
        path = os.path.join(self.exchange_dir, "wrapped.obj")
        if not os.path.isfile(path):
            self._bx_export_result()
        blender = find_blender()
        if blender is None:
            QMessageBox.warning(self, "未找到 Blender", "未检测到 Blender, 请设置环境变量 BLENDER_PATH")
            return
        import subprocess
        expr = ("import bpy; "
                f"bpy.ops.wm.obj_import(filepath=r'{path}', "
                "up_axis='Z', forward_axis='NEGATIVE_Y')")
        try:
            subprocess.Popen([blender, "--python-expr", expr])
        except Exception as e:
            QMessageBox.critical(self, "启动失败", str(e))
        self.statusBar().showMessage("已在 Blender 中打开结果")

    def _bx_transfer_shapes(self):
        d = self.exchange_dir
        shapes_dir = os.path.join(d, "shapes")
        if not os.path.isdir(shapes_dir):
            QMessageBox.information(self, "无形态键序列",
                                    f"未找到 {shapes_dir}\n请先在 Blender 插件中执行「导出形态键序列」")
            return
        bp = os.path.join(d, "base.obj")
        wp = os.path.join(d, "wrapped.obj")
        if not (os.path.isfile(bp) and os.path.isfile(wp)):
            QMessageBox.information(self, "缺少文件", "交换目录需包含 base.obj 与 wrapped.obj")
            return
        out_dir = os.path.join(d, "shapes_wrapped")
        try:
            outs = blendshape.batch_transfer_dir(bp, wp, shapes_dir, out_dir)
        except Exception as e:
            QMessageBox.critical(self, "迁移失败", str(e))
            return
        QMessageBox.information(self, "迁移完成",
                                f"已迁移 {len(outs)} 个形态键到\n{out_dir}")
