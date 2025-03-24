from PyQt5.QtWidgets import QSlider
from PyQt5.QtCore import Qt

class ZoomSlider(QSlider):
    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setMinimum(50)  # 最小50%
        self.setMaximum(150)  # 最大150%
        self.setValue(100)  # 默认100%
        self.setFixedWidth(100)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta < 0:  # 向下滚动
            self.setValue(self.value() - 5)  # 每次缩小5%
        else:  # 向上滚动
            self.setValue(self.value() + 5)  # 每次放大5%
        event.accept()