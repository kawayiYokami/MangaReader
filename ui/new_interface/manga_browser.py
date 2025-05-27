from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSplitter
from qfluentwidgets import TitleLabel, InfoBar, InfoBarPosition

from .manga_viewer import MangaViewer
from .manga_list import MangaList
from .tag_filter import TagFilter
from .control_panel import ControlPanel
from core.manga_manager import MangaManager


class MangaBrowser(QWidget):
    """新的漫画浏览界面，采用模块化设计"""

    def __init__(self, parent=None, manga_manager=None):
        super().__init__(parent)
        self.manga_manager = manga_manager or MangaManager(self)  # 使用传入的manager或新建实例
        self.setup_ui()
        self.reading_order = "right_to_left"

    def setup_ui(self):
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 0, 10, 0)

        # 主分割器
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setStyleSheet(
            "QSplitter::handle { background: transparent; }"
        )

        # 左侧垂直分割器
        self.left_splitter = QSplitter(Qt.Vertical)
        self.left_splitter.setStyleSheet(
            "QSplitter::handle { background: transparent; }"
        )

        # 左侧面板（标签过滤和漫画列表）
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 0)

        # 左侧垂直分割器
        self.left_splitter = QSplitter(Qt.Vertical)

        # 标签过滤器
        # 修改组件初始化，传入管理器引用
        self.tag_filter = TagFilter(self, self.manga_manager)
        self.manga_list = MangaList(self, self.manga_manager)
        self.manga_viewer = MangaViewer(self, self.manga_manager)
        self.left_splitter.addWidget(self.tag_filter)

        # 漫画列表
        self.left_splitter.addWidget(self.manga_list)

        # 设置分割比例
        self.left_splitter.setSizes([200, 400])
        self.left_layout.addWidget(self.left_splitter)

        # 右侧面板（漫画查看器）
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(0, 0, 0, 0)

        # 添加漫画查看器
        self.right_layout.addWidget(self.manga_viewer)

        # 添加左右面板到主分割器
        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(self.right_panel)

        # 设置主分割器的拉伸因子，让右侧面板优先拉伸
        self.main_splitter.setStretchFactor(0, 0)  # 左侧面板不拉伸
        self.main_splitter.setStretchFactor(1, 1)  # 右侧面板拉伸
        # self.main_splitter.setSizes([300, 700]) # 使用拉伸因子代替固定尺寸

        # 添加主分割器到主布局
        self.main_layout.addWidget(self.main_splitter)

    def toggle_direction(self):
        """切换阅读方向（从左到右/从右到左）"""
        if hasattr(self.parent, "toggle_reading_order"):
            current_order = self.parent.toggle_reading_order()
            self.direction_button.setChecked(current_order == "right_to_left")
            self.direction_button.setText(
                "从右到左" if current_order == "right_to_left" else "从左到右"
            )

        # 更新显示
        if hasattr(self.parent, "update_display"):
            self.parent.update_display()
