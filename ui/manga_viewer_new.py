import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QLineEdit, QFileDialog, QMessageBox,
                             QPushButton, QLabel)
from PyQt5.QtCore import Qt, QTimer
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
from ui.components.slider_controller import SliderController
from ui.base_window import BaseWindow

class MangaViewer(BaseWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("漫画查看器")
        self.manga_manager = MangaManager()
        self.current_manga = None
        self.current_style = 'default'  # 当前主题样式
        
        # 初始化组件
        self.image_viewer = MangaImageViewer(self)
        self.tag_manager = TagManager(self)
        self.manga_list_manager = MangaListManager(self)
        self.navigation_controller = NavigationController(self)
        self.side_navigation = SideNavigation(self)
        
        # 初始化标题栏
        self.title_bar = TitleBar(self)
        # 不设置标题文本，保持简洁
        
        # 搜索相关
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)  # 设置为单次触发
        self.search_timer.timeout.connect(self.perform_search)
        
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
        
        # 添加标题栏
        main_layout.addWidget(self.title_bar)
        
        # 创建内容区域容器
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)  # 移除边距
        
        # 添加侧边导航栏
        side_nav = self.side_navigation.setup_ui()
        content_layout.addWidget(side_nav)
        
        # 创建主内容区域
        main_content = QWidget()
        main_content_layout = QHBoxLayout(main_content)
        main_content_layout.setContentsMargins(5, 5, 5, 5)  # 调整边距为5像素
        
        # 创建水平分割器
        h_splitter = QSplitter(Qt.Horizontal)
        
        # 左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 连接标题栏中的文件夹按钮和搜索框
        self.title_bar.select_dir_btn.clicked.connect(self.select_directory)
        self.title_bar.search_input.textChanged.connect(self.on_search_text_changed)
        
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
        
        # 添加导航控制器
        nav_layout = self.navigation_controller.setup_ui(zoom_slider)
        right_layout.addLayout(nav_layout)
        
        # 连接标题栏中的页面滑动条
        self.title_bar.page_slider.valueChanged.connect(self.on_title_slider_value_changed)
        
        # 初始化滑动条控制器
        self.slider_controller = SliderController(self)
        self.slider_controller.setup_slider(self.title_bar.page_slider)
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
        
        main_content_layout.addWidget(h_splitter)
        content_layout.addWidget(main_content)
        main_layout.addWidget(content_widget)
        
        self.navigation_controller.update_navigation_buttons()
    
    def select_directory(self):
        log.info("打开选择漫画目录对话框")
        dir_path = QFileDialog.getExistingDirectory(self, '选择漫画目录')
        if dir_path:
            log.info(f"用户选择了目录: {dir_path}")
            self.manga_manager.set_manga_dir(dir_path)
            self.tag_manager.update_tag_buttons()
            self.manga_list_manager.update_manga_list()
        else:
            log.info("用户取消了目录选择")
    
    def on_search_text_changed(self):
        """当搜索框文本改变时触发"""
        # 重置定时器
        self.search_timer.stop()
        # 0.1秒后执行搜索
        self.search_timer.start(100)
    
    def perform_search(self):
        """执行搜索"""
        search_text = self.title_bar.search_input.text().lower()
        log.info(f"执行搜索: {search_text}")
        
        if not search_text:
            # 如果搜索框为空，显示所有漫画
            self.manga_list_manager.update_manga_list()
            return
        
        # 搜索文件名
        filtered_manga = [
            manga for manga in self.manga_manager.manga_list
            if search_text in os.path.basename(manga.file_path).lower()
        ]
        
        # 更新显示
        self.manga_list_manager.update_manga_list(filtered_manga)
    
    def change_page(self, direction):
        """调用导航控制器的change_page方法
        Args:
            direction: 1 表示向后，-1 表示向前
        """
        self.navigation_controller.change_page(direction)
    
    def on_title_slider_value_changed(self):
        """处理标题栏滑动条值变化"""
        self.slider_controller.on_slider_value_changed()
    
    def update_page_info(self):
        """更新页码信息"""
        if self.current_manga:
            current_page = self.current_manga.current_page + 1  # 显示从1开始
            total_pages = self.current_manga.total_pages
            self.title_bar.page_info_label.setText(f'{current_page} / {total_pages}')
        else:
            self.title_bar.page_info_label.setText('0 / 0')
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 如果当前有显示的图片，重新加载并显示
        if self.current_manga:
            self.image_viewer.show_current_page(
                self.current_manga, 
                self.navigation_controller.zoom_slider.value()
            )
    
    def closeEvent(self, event):
        log.info("程序关闭，保存配置")
        self.manga_manager.save_config()
        log.info("配置保存完成，程序退出")
        super().closeEvent(event)