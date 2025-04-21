import sys
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from ui.new_interface.manga_browser import MangaBrowser

class MangaBrowserInterface(QWidget):
    """
    新的漫画浏览界面接口，作为主窗口的子界面
    使用模块化设计的MangaBrowser组件
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.manga_browser = MangaBrowser(self)
        self.setup_ui()
    
    def setup_ui(self):
        # 使用 QVBoxLayout 确保 MangaBrowser 可以填充可用空间
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # 通常界面容器不需要边距
        layout.addWidget(self.manga_browser)
        self.setLayout(layout)