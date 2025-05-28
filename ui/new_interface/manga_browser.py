import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSplitter
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
        
        # 启用拖放功能
        self.setAcceptDrops(True)

        # 连接manga_manager的tags_cleared信号到tag_filter的clear_tags槽
        self.manga_manager.tags_cleared.connect(self.tag_filter.clear_tags)

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
            
    def dragEnterEvent(self, event):
        """处理拖拽进入事件"""
        # 检查是否是文件拖拽
        if event.mimeData().hasUrls():
            # 检查是否是支持的文件类型（.zip或.cbz）
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                # 检查是否是支持的文件类型（.zip, .cbz）或目录
                if file_path.lower().endswith(('.zip', '.cbz')) or os.path.isdir(file_path):
                    event.acceptProposedAction()
                    return
                    
    def dropEvent(self, event):
        """处理拖拽释放事件"""
        urls = event.mimeData().urls()
        if not urls:
            return

        # 优先处理拖入的第一个文件夹
        for url in urls:
            file_path = url.toLocalFile()
            if os.path.isdir(file_path):
                # 如果是目录，则调用manga_manager的设置目录并重新扫描功能
                self.manga_manager.set_manga_dir(file_path, force_rescan=True)
                return # 找到第一个目录就处理并返回

        # 如果没有拖入目录，则处理拖入的ZIP/CBZ文件
        files_to_process = []
        for url in urls:
            file_path = url.toLocalFile()
            if file_path.lower().endswith(('.zip', '.cbz')):
                files_to_process.append(file_path)
        
        if not files_to_process:
            return
            
        # 扫描所有拖入的漫画文件
        from core.manga_model import MangaLoader
        manga_list = []
        for file_path in files_to_process:
            manga = MangaLoader.load_manga(file_path)
            if manga and manga.is_valid:
                manga_list.append(manga)
        
        if manga_list:
            # 保存第一个拖入的漫画，稍后打开它
            first_manga = manga_list[0]
            
            # 检查并添加不重复的漫画
            new_manga_list = []
            for manga in manga_list:
                # 检查是否已存在相同路径的漫画（使用规范化路径进行比较）
                manga_path = os.path.normpath(manga.file_path).lower()
                if not any(os.path.normpath(existing.file_path).lower() == manga_path for existing in self.manga_manager.manga_list):
                    new_manga_list.append(manga)
                    self.manga_manager.manga_list.append(manga)
            
            # 如果有新添加的漫画，更新缓存
            if new_manga_list:
                from core.manga_cache import manga_cache
                from core.config import config
                manga_cache.update_manga_list(config.manga_dir.value, self.manga_manager.manga_list)
                # 通知UI更新
                self.manga_manager.manga_list_updated.emit(self.manga_manager.manga_list)
            
            # 无论是否重复，都打开第一个拖入的漫画
            self.manga_manager.set_current_manga(first_manga)
