import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSplitter
from qfluentwidgets import TitleLabel, InfoBar, InfoBarPosition

from .manga_viewer import MangaViewer
from .manga_list import MangaList
from .tag_filter import TagFilter
from .control_panel import ControlPanel
from core.manga_manager import MangaManager
from core.cache_factory import get_cache_factory_instance # 添加 CacheFactory 导入
from core.config import config # 添加 config 导入


class MangaBrowser(QWidget):
    """新的漫画浏览界面，采用模块化设计"""

    def __init__(self, parent=None, manga_manager=None):
        super().__init__(parent)
        self.manga_manager = manga_manager or MangaManager(self)  # 使用传入的manager或新建实例
        self.manga_list_cache = get_cache_factory_instance().get_manager("manga_list") # 获取漫画列表缓存实例
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
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.zip', '.cbz')) or os.path.isdir(file_path):
                    event.acceptProposedAction()
                    return
                    
    def dropEvent(self, event):
        """处理拖拽释放事件"""
        urls = event.mimeData().urls()
        if not urls:
            return

        for url in urls:
            file_path = url.toLocalFile()
            if os.path.isdir(file_path):
                self.manga_manager.set_manga_dir(file_path, force_rescan=True)
                return 

        files_to_process = []
        for url in urls:
            file_path = url.toLocalFile()
            if file_path.lower().endswith(('.zip', '.cbz')):
                files_to_process.append(file_path)
        
        if not files_to_process:
            return
            
        from core.manga_model import MangaLoader
        manga_list_from_drop = [] # 重命名以避免与 self.manga_list 冲突
        for file_path in files_to_process:
            manga = MangaLoader.load_manga(file_path)
            if manga and manga.is_valid:
                manga_list_from_drop.append(manga)
        
        if manga_list_from_drop:
            first_manga = manga_list_from_drop[0]
            
            new_manga_added_to_manager = []
            for manga_item in manga_list_from_drop:
                manga_path_norm = os.path.normpath(manga_item.file_path).lower()
                if not any(os.path.normpath(existing.file_path).lower() == manga_path_norm for existing in self.manga_manager.manga_list):
                    new_manga_added_to_manager.append(manga_item)
                    self.manga_manager.manga_list.append(manga_item) # 添加到 MangaManager 的列表
            
            if new_manga_added_to_manager:
                # 使用 MangaListCacheManager 实例的 set 方法更新缓存
                # 假设拖入的文件应该被添加到当前 manga_dir 的缓存中
                # 如果 manga_dir 未设置，则可能需要一个默认行为或提示用户
                current_manga_dir = config.manga_dir.value
                if current_manga_dir:
                    # MangaListCacheManager.set 需要一个包含所有漫画信息的列表
                    # 我们需要传递 MangaManager 中完整的漫画列表给它
                    self.manga_list_cache.set(current_manga_dir, self.manga_manager.manga_list)
                else:
                    InfoBar.warning(
                        title="提示",
                        content="未设置漫画目录，拖入的漫画未被缓存。",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                self.manga_manager.manga_list_updated.emit(self.manga_manager.manga_list)
            
            self.manga_manager.set_current_manga(first_manga)
