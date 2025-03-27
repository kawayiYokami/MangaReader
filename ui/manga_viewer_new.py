import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLineEdit,
    QFileDialog, QMessageBox, QPushButton, QLabel
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QSize, QRect
from core.manga_manager import MangaManager
from utils import manga_logger as log
from styles.style import Win11Style

# 导入自定义组件
from ui.components.manga_image_viewer import MangaImageViewer
from ui.components.tag_manager import TagManager
from ui.components.manga_list_manager import MangaListManager
from ui.components.navigation_controller import NavigationController
from ui.components.title_bar import TitleBar
from ui.components.side_navigation import SideNavigation
from ui.base_window import BaseWindow


class MangaViewer(BaseWindow):
    def __init__(self, parent=None):

        super().__init__(parent)



        self.setWindowTitle("漫画查看器")

        self.manga_manager = MangaManager()

        self.current_manga = None

        self.current_style = 'default'  # 当前主题样式



        # 创建中心部件

        self.central_widget = QWidget()

        self.setCentralWidget(self.central_widget)



        self.setMouseTracking(True)

        self.central_widget.setMouseTracking(True)



        # 初始化组件

        self.image_viewer = MangaImageViewer(self)

        self.tag_manager = TagManager(self)

        self.manga_list_manager = MangaListManager(self)

        self.navigation_controller = NavigationController(self)



        # 初始化标题栏

        self.title_bar = TitleBar(self, navigation_controller=self.navigation_controller) # 传递 navigation_controller

        # 不设置标题文本，保持简洁



        # Window dragging variables

        self._is_dragging = False

        self._drag_start_position = None

        self._window_start_position = None



        # Window resizing variables

        self._is_resizing = False

        self._resize_edge = None  # 'left', 'right', 'top', 'bottom', 'top-left', etc.

        self._resize_start_position = None

        self._resize_start_size = None

        self._edge_threshold = 5  # 拖动边缘



        self.setup_ui()



        Win11Style.apply_style(self)

        log.info("MangaViewer初始化完成")
        
    def setup_ui(self):
        log.info("开始设置UI界面")
        self.setGeometry(100, 100, 1200, 800)

        # 创建主窗口部件
        main_widget = self.central_widget
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 设置 main_layout 的外边距 (左, 上, 右, 下)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # 添加标题栏
        main_layout.addWidget(self.title_bar)

        # 创建内容区域容器
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)  # 移除边距

        # 创建水平分割器
        h_splitter = QSplitter(Qt.Horizontal)

        # 左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 创建垂直分割器
        v_splitter = QSplitter(Qt.Vertical)

        # 添加标签滚动区域（标签管理器）
        tag_scroll_area = self.tag_manager.setup_ui(left_layout)

        # 添加漫画列表
        manga_list_view = self.manga_list_manager.setup_ui()

        # 将组件添加到垂直分割器
        v_splitter.addWidget(tag_scroll_area)
        v_splitter.addWidget(manga_list_view)

        # 设置垂直分割器初始大小
        v_splitter.setSizes([200, 400])
        left_layout.addWidget(v_splitter)

        # 右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 添加图像查看器
        zoom_slider = self.image_viewer.setup_ui(right_layout)
        self.side_navigation = SideNavigation(self, zoom_slider) # 只在这里初始化一次
        side_nav = self.side_navigation.setup_ui()

        # 添加导航控制器
        nav_layout = self.navigation_controller.setup_ui(zoom_slider)

        self.navigation_controller.page_slider = self.title_bar.page_slider

        # 将左右面板添加到水平分割器
        h_splitter.addWidget(left_panel)
        h_splitter.addWidget(right_panel)

        # 设置水平分割器初始大小比例
        h_splitter.setSizes([300, 900])

        # 设置拉伸因子，使右侧面板获得所有额外空间
        h_splitter.setStretchFactor(0, 0)  # 左侧面板不拉伸
        h_splitter.setStretchFactor(1, 1)  # 右侧面板获得所有额外空间

        # 设置左侧面板最小宽度
        left_panel.setMinimumWidth(300)  # 防止左侧面板被完全收缩

        # 将水平分割器添加到内容布局
        content_layout.addWidget(h_splitter)

        # 添加侧边导航栏到内容布局
        content_layout.addWidget(side_nav)

        # 将内容区域添加到主布局
        main_layout.addWidget(content_widget)

    def load_manga(self, manga_path):
        super().load_manga(manga_path)
        if self.current_manga:
            self.title_bar.page_slider.setMaximum(self.current_manga.total_pages - 1)
            self.title_bar.page_slider.setValue(self.current_manga.current_page)
            self.title_bar.update_page_info()

    def select_directory(self):
        log.info("打开选择漫画目录对话框")
        dir_path = QFileDialog.getExistingDirectory(self, '选择漫画目录')
        if dir_path:
            log.info(f"用户选择了目录: {dir_path}")
            self.manga_manager.set_manga_dir(dir_path)
            self.tag_manager.update_tag_buttons()
            self.manga_list_manager.update_manga_list()
            if self.manga_list_manager.current_manga_path:
                self.load_manga(self.manga_list_manager.current_manga_path)
        else:
            log.info("用户取消了目录选择")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_manga and self.image_viewer.current_pixmap:
            self.image_viewer._update_zoomed_pixmap(
                self.image_viewer.current_pixmap,
                self.navigation_controller.zoom_slider.value()
            )

    def closeEvent(self, event):
        log.info("程序关闭，保存配置")
        self.manga_manager.save_config()
        log.info("配置保存完成，程序退出")
        super().closeEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            rect = self.rect()
            threshold = self._edge_threshold
            self._window_start_position = self.pos()

            if pos.x() <= threshold and pos.y() <= threshold:
                self._resize_edge = 'top-left'
            elif pos.x() >= rect.width() - threshold and pos.y() <= threshold:
                self._resize_edge = 'top-right'
            elif pos.x() <= threshold and pos.y() >= rect.height() - threshold:
                self._resize_edge = 'bottom-left'
            elif pos.x() >= rect.width() - threshold and pos.y() >= rect.height() - threshold:
                self._resize_edge = 'bottom-right'
            elif pos.x() <= threshold:
                self._resize_edge = 'left'
            elif pos.x() >= rect.width() - threshold:
                self._resize_edge = 'right'
            elif pos.y() <= threshold:
                self._resize_edge = 'top'
            elif pos.y() >= rect.height() - threshold:
                self._resize_edge = 'bottom'
            else:
                self._is_dragging = True
                self._drag_start_position = event.globalPos()
                return

            self._is_resizing = True
            self._resize_start_position = event.globalPos()
            self._resize_start_size = self.size()
            event.accept()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            if self._is_dragging:
                self._is_dragging = False
                self._drag_start_position = None
                self._window_start_position = None
                event.accept()
            elif self._is_resizing:
                self._is_resizing = False
                self._resize_edge = None
                self._resize_start_position = None
                self._resize_start_size = None
                event.accept()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

        if self._is_dragging and event.buttons() == Qt.LeftButton:
            if self._drag_start_position:
                current_pos = event.globalPos()
                offset = current_pos - self._drag_start_position
                new_pos = self._window_start_position + offset
                self.move(new_pos)
                event.accept()
        elif self._is_resizing and self._resize_edge:
            current_pos = event.globalPos()
            delta = current_pos - self._resize_start_position
            new_width = self._resize_start_size.width()
            new_height = self._resize_start_size.height()
            new_x = self.x()
            new_y = self.y()

            if 'left' == self._resize_edge:
                new_width -= delta.x()
                new_x = self._window_start_position.x() + delta.x()
            elif 'right' == self._resize_edge:
                new_width += delta.x()

            if 'top' == self._resize_edge:
                new_height -= delta.y()
                new_y = self._window_start_position.y() + delta.y()
            elif 'bottom' == self._resize_edge:
                new_height += delta.y()

            if 'top-left' == self._resize_edge:
                new_width -= delta.x()
                new_x = self._window_start_position.x() + delta.x()
                new_height -= delta.y()
                new_y = self._window_start_position.y() + delta.y()
            elif 'top-right' == self._resize_edge:
                new_width += delta.x()
                new_height -= delta.y()
                new_y = self._window_start_position.y() + delta.y()
            elif 'bottom-left' == self._resize_edge:
                new_width -= delta.x()
                new_x = self._window_start_position.x() + delta.x()
                new_height += delta.y()
            elif 'bottom-right' == self._resize_edge:
                new_width += delta.x()
                new_height += delta.y()

            self.setGeometry(new_x, new_y, new_width, new_height)
            event.accept()
        elif not self._is_resizing and not self._is_dragging:
            pos = event.pos()
            rect = self.rect()
            threshold = self._edge_threshold
            
            # 检测鼠标位置并设置相应的光标
            if pos.x() <= threshold and pos.y() <= threshold:
                self.setCursor(Qt.SizeFDiagCursor)  # 左上角
            elif pos.x() >= rect.width() - threshold and pos.y() <= threshold:
                self.setCursor(Qt.SizeBDiagCursor)  # 右上角
            elif pos.x() <= threshold and pos.y() >= rect.height() - threshold:
                self.setCursor(Qt.SizeBDiagCursor)  # 左下角
            elif pos.x() >= rect.width() - threshold and pos.y() >= rect.height() - threshold:
                self.setCursor(Qt.SizeFDiagCursor)  # 右下角
            elif pos.x() <= threshold or pos.x() >= rect.width() - threshold:
                self.setCursor(Qt.SizeHorCursor)  # 左右边缘
            elif pos.y() <= threshold or pos.y() >= rect.height() - threshold:
                self.setCursor(Qt.SizeVerCursor)  # 上下边缘
            else:
                self.unsetCursor()  # 恢复默认光标