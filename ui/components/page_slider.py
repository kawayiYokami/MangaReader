from PyQt5.QtWidgets import QSlider
from PyQt5.QtCore import Qt

class PageSlider(QSlider):
    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setMinimum(0)
        self.setMaximum(0)
        self.setFixedWidth(200)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta < 0:  # 向下滚动
            self.setValue(self.value() + 1)
        else:  # 向上滚动
            self.setValue(self.value() - 1)
        event.accept()