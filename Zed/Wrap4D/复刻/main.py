"""PyWrap 启动入口."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)   # 高分辨率屏防布局错乱
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("PyWrap")

    from gui.main_window import MainWindow
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
