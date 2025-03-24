from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt
import manga_logger as log

class ImageLabel(QLabel):
    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        self.setFocus()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Left, Qt.Key_Up):
            self.viewer.show_previous_page()
        elif event.key() in (Qt.Key_Right, Qt.Key_Down):
            self.viewer.show_next_page()
        event.accept()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:  # 滚轮向上
            self.viewer.change_page(-1)
        else:  # 滚轮向下
            self.viewer.change_page(1)
        event.accept()

    def focusInEvent(self, event):
        # 当获得焦点时打印日志，帮助调试
        log.info("Image label got focus")
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        # 当失去焦点时打印日志，帮助调试
        log.info("Image label lost focus")
        super().focusOutEvent(event)