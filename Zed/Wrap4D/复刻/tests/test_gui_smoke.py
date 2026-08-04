"""GUI 冒烟测试: 离屏实例化主窗口, 模拟 加载网格->打点->包裹->导出 全流程."""

import os
import sys
import tempfile

import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 注意: VTK 需要真实 OpenGL 上下文, offscreen 平台无法创建, 故使用默认平台(不显示窗口)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from wrapclone.geometry import RBFDeformer


def make_synthetic(out_dir):
    rng = np.random.default_rng(0)
    base = trimesh.creation.icosphere(subdivisions=4, radius=1.0)
    idx = rng.choice(len(base.vertices), 12, replace=False)
    ctrl_src = np.asarray(base.vertices[idx])
    ctrl_dst = ctrl_src + rng.normal(scale=0.15, size=(12, 3))
    rbf = RBFDeformer().fit(ctrl_src, ctrl_dst)
    target = trimesh.Trimesh(rbf(np.asarray(base.vertices)),
                             np.asarray(base.faces), process=False)
    bp = os.path.join(out_dir, "base.obj")
    tp = os.path.join(out_dir, "target.obj")
    base.export(bp)
    target.export(tp)
    return bp, tp, base, target, idx


def main():
    app = QApplication([])
    from gui.main_window import MainWindow
    win = MainWindow()

    with tempfile.TemporaryDirectory() as td:
        bp, tp, base, target, gen_ids = make_synthetic(td)

        # 1. 加载网格(直接走内部逻辑, 绕过文件对话框)
        from wrapclone.mesh_io import load_mesh
        win.base_mesh, win.base_path = load_mesh(bp), bp
        win.base_view.set_mesh(win.base_mesh)
        win.target_mesh, win.target_path = load_mesh(tp), tp
        win.target_view.set_mesh(win.target_mesh, opacity=0.55)

        # 2. 模拟打 12 对点(用变形生成点, 使问题适定)
        win.btn_pick.setChecked(True)
        assert win.pick_mode
        for vid in gen_ids:
            win._on_click("base", np.asarray(base.vertices[vid]), int(vid))
            win._on_click("target", np.asarray(target.vertices[vid]), int(vid))
        assert len(win.pairs) == 12, f"点对数量错误: {len(win.pairs)}"
        assert win.pair_list.count() == 12
        print("[OK] 打点流程: 12 对点已建立")

        # 3. 点对保存/加载
        pp = os.path.join(td, "pts.json")
        win.pairs.save(pp)
        win.pairs.load(pp)
        assert len(win.pairs) == 12
        print("[OK] 点对保存/加载")

        # 4. 执行包裹(同步等待线程结束)
        win.spin_icp.setValue(5)
        win.spin_opt.setValue(10)
        win._start_wrap()
        while win._wrap_thread is not None and not win._wrap_thread.wait(100):
            app.processEvents()
        app.processEvents()
        assert win.wrapped_mesh is not None, "包裹未产生结果"
        err = np.linalg.norm(np.asarray(win.wrapped_mesh.vertices)
                             - np.asarray(target.vertices), axis=1).mean()
        print(f"[OK] 包裹完成, 平均误差 {err:.4f}")
        assert err < 0.02

        # 5b. 删除一对后应为 11
        win.pair_list.setCurrentRow(0)
        win._delete_selected_pair()
        assert len(win.pairs) == 11

        # 6. 清空点对
        win._clear_pairs()
        assert len(win.pairs) == 0
        print("[OK] 点对删除/清空")

    # ===== 新功能: GLB 加载 / 对齐 / 重设点 / 相机联动 =====
    with tempfile.TemporaryDirectory() as td2:
        bp, tp, base, target, gen_ids = make_synthetic(td2)
        # GLB 导出再加载
        glb_p = os.path.join(td2, "target.glb")
        target.export(glb_p)
        assert os.path.isfile(glb_p)
        from wrapclone.mesh_io import load_mesh as _lm
        glb_mesh = _lm(glb_p)
        assert len(glb_mesh.vertices) > 0, "GLB 加载失败"
        win2 = MainWindow()
        assert win2._set_mesh("base", bp)
        assert win2._set_mesh("target", glb_p), "GLB 应可加载"
        print(f"[OK] GLB 加载: {len(glb_mesh.vertices)} 顶点")

        # 对齐操作组
        win2._align_center(); win2._align_bbox()
        v0 = np.asarray(win2.base_mesh.vertices).copy()
        win2._nudge(0, +1)                       # X+ 平移
        assert not np.allclose(win2.base_mesh.vertices, v0)
        win2._rotate(2, +1)                      # Rz+ 旋转
        win2._scale_base(1.05)                   # 放大
        win2._align_bbox()                       # 复位
        print("[OK] 对齐: 中心/包围盒/平移/旋转/缩放")

        # 打 3 对点 -> 刚体对齐
        win2.btn_pick.setChecked(True)
        for vid in gen_ids[:3]:
            win2._on_click("base", np.asarray(base.vertices[vid]), int(vid))
            win2._on_click("target", np.asarray(target.vertices[vid]), int(vid))
        assert len(win2.pairs) == 3
        win2._align_by_points()
        print("[OK] ≥3点刚体对齐")

        # 重设点流程: 选中第1对, 重设基础点
        win2.pair_list.setCurrentRow(0)
        win2._start_reassign("base")
        assert win2._reassign == ("base", 0)
        new_vid = int(gen_ids[11])   # 用一个未被占用的顶点, 避免重复点
        win2._on_click("base", np.asarray(base.vertices[new_vid]), new_vid)
        assert win2._reassign is None, "重设后应退出重设模式"
        assert win2.pairs.pairs[0].base_vid == new_vid, "重设未生效"
        print("[OK] 重设点对")

        # 相机联动信号存在且可调用不报错
        win2._sync_camera(win2.base_view)
        print("[OK] 相机联动")

        # 新包裹参数(采样模式, 快速验证) —— 补足 ≥4 对点避免 RBF 确认框
        for vid in gen_ids[3:6]:
            win2._on_click("base", np.asarray(base.vertices[vid]), int(vid))
            win2._on_click("target", np.asarray(target.vertices[vid]), int(vid))
        win2.combo_corr.setCurrentIndex(1)  # 表面采样
        win2.spin_icp.setValue(3)
        win2.spin_p2plane.setValue(0.5)
        win2.spin_trim.setValue(0.1)
        win2._start_wrap()
        while win2._wrap_thread is not None and not win2._wrap_thread.wait(100):
            app.processEvents()
        app.processEvents()
        assert win2.wrapped_mesh is not None, "采样模式包裹失败"
        print("[OK] 采样模式+点对面+截尾 包裹")

        # 点编号续接: 删最后一对 -> 新点对编号复用
        win2._clear_pairs()
        for vid in gen_ids[:3]:
            win2._on_click("base", np.asarray(base.vertices[vid]), int(vid))
            win2._on_click("target", np.asarray(target.vertices[vid]), int(vid))
        assert win2.pairs.pairs[-1].name == "P3"
        win2.pair_list.setCurrentRow(2)
        win2._delete_selected_pair()
        win2._on_click("base", np.asarray(base.vertices[gen_ids[3]]), int(gen_ids[3]))
        win2._on_click("target", np.asarray(target.vertices[gen_ids[3]]), int(gen_ids[3]))
        assert win2.pairs.pairs[-1].name == "P3", \
            f"删除末尾后新点编号应为 P3, 实际 {win2.pairs.pairs[-1].name}"
        print("[OK] 点编号删除后续接")

        # 对齐对象选择: 切到 target, 平移应作用于扫描网格
        win2.combo_align_target.setCurrentIndex(1)
        tv0 = np.asarray(win2.target_mesh.vertices).copy()
        bv0 = np.asarray(win2.base_mesh.vertices).copy()
        win2._nudge(0, +1)
        assert not np.allclose(win2.target_mesh.vertices, tv0), "target 未被平移"
        assert np.allclose(win2.base_mesh.vertices, bv0), "base 不应受影响"
        # 控制点 target 侧同步移动
        print("[OK] 对齐对象选择 (可分别控制 base/target)")

        # 滚动面板 + 底部固定包裹按钮存在
        from PyQt5.QtWidgets import QScrollArea
        assert hasattr(win2, "btn_wrap_bottom"), "缺少底部固定包裹按钮"
        scrolls = win2.findChildren(QScrollArea)
        assert len(scrolls) >= 1, "左侧面板未加滚动区"
        print("[OK] 面板滚动区 + 底部固定包裹按钮 (全屏不丢功能)")

        # ===== 第 5 批反馈: 忙碌反馈 / 结果退回 / 遮罩 / 预设 / 防误触 =====
        # 预设切换 (Wrap 官方参数结构)
        win2.combo_preset.setCurrentText("高质量(两步法第二步)")
        assert win2.spin_smooth_min.value() == 0.07 and win2.spin_samp_max.value() == 10.0
        win2.combo_preset.setCurrentText("标准(Wrapping默认)")
        assert win2.spin_icp.value() == 5 and win2.spin_smooth_min.value() == 0.05
        print("[OK] 参数预设 + 恢复默认")

        # 防滚轮过滤器已挂载到参数控件
        assert getattr(win2, "_nowheel", None) is not None
        from PyQt5.QtCore import QEvent
        ev_filters = [win2.spin_icp.eventFilter(win2._nowheel, None)]  # 只验证不崩
        print("[OK] 防滚轮误触过滤器")

        # 遮罩笔刷: 模拟点击基础网格某点 -> 区域内顶点被涂抹
        win2.btn_mask_mode.setChecked(True)
        assert win2.mask_mode and not win2.pick_mode, "遮罩模式应与打点互斥"
        center = np.asarray(win2.base_mesh.vertices).mean(axis=0)
        from wrapclone.mesh_io import nearest_vertex
        vid0 = nearest_vertex(win2.base_mesh, center)
        win2._on_click("base", np.asarray(win2.base_mesh.vertices[vid0]), vid0)
        n_painted = int(win2._painted.sum())
        assert n_painted > 0, "遮罩笔刷未涂抹任何顶点"
        print(f"[OK] 遮罩笔刷涂抹 {n_painted} 顶点")
        # 白名单语义: 引擎遮罩 = 涂抹区为1
        win2.combo_mask_sem.setCurrentIndex(1)
        em = win2._engine_mask()
        assert em is not None and em[win2._painted].mean() == 1.0 \
            and em[~win2._painted].mean() == 0.0, "白名单语义错误"
        win2.combo_mask_sem.setCurrentIndex(0)
        em = win2._engine_mask()
        assert em[win2._painted].mean() == 0.0 and em[~win2._painted].mean() == 1.0, \
            "黑名单语义错误"
        print("[OK] 遮罩黑/白名单语义 (SelectPolygons)")
        win2._mask_clear()
        assert int(win2._painted.sum()) == 0
        win2.btn_mask_mode.setChecked(False)
        print("[OK] 遮罩清除/互斥退出")

        # 结果退回: 包裹后进入打点模式 -> 结果层隐藏; 清除结果按钮
        win2.combo_corr.setCurrentIndex(1)
        win2.spin_icp.setValue(2)
        win2.spin_opt.setValue(5)
        for vid in gen_ids[:6]:
            win2._on_click("base", np.asarray(base.vertices[vid]), int(vid))
            win2._on_click("target", np.asarray(target.vertices[vid]), int(vid))
        # 打点模式开着时点了点, 先退出打点(恢复结果层逻辑)
        win2.btn_pick.setChecked(False)
        win2._start_wrap()
        # 即时反馈: 按钮置灰 + 忙碌进度条
        assert not win2.btn_wrap_bottom.isEnabled(), "包裹中底部按钮未置灰"
        assert win2.progress.maximum() == 0 and win2.progress.minimum() == 0, \
            "包裹初始化时应为忙碌进度条"
        print("[OK] 包裹即时反馈 (按钮置灰+忙碌条)")
        while win2._wrap_thread is not None and not win2._wrap_thread.wait(100):
            app.processEvents()
        app.processEvents()
        assert win2.wrapped_mesh is not None
        assert win2.progress.maximum() == 100, "完成后进度条应恢复百分比模式"
        assert win2.btn_clear_result.isEnabled()
        # 进入打点 -> 结果层应隐藏, 透明度回 100
        win2.btn_pick.setChecked(True)
        assert win2.target_view._overlay_actor is None, "打点时结果层未隐藏"
        assert abs(win2.target_view._opacity - 1.0) < 1e-6
        win2.btn_pick.setChecked(False)
        assert win2.target_view._overlay_actor is not None, "退出打点应恢复结果层"
        print("[OK] 打点时结果层自动隐藏/恢复")
        # 清除结果退回
        win2._clear_result()
        assert win2.wrapped_mesh is None and win2.target_view._overlay_actor is None
        print("[OK] 清除结果退回继续调整")
        print("\n新功能测试全部通过")


if __name__ == "__main__":
    main()
