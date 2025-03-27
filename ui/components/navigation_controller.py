"""导航控制器模块，提供页面导航和缩放控制功能。"""

from PyQt5 import QtWidgets, QtCore, QtGui
from utils import manga_logger as log
from ui.components.page_slider import PageSlider
from ui.components.zoom_slider import ZoomSlider
from styles.light_style import Win11LightStyle
from styles.dark_style import Win11DarkStyle
from styles.style import Win11Style
from styles.win_theme_color import get_system_theme_colors

class NavigationController:
    """负责页面导航和控制的组件"""

    def __init__(self, parent):
        """初始化导航控制器
        
        Args:
            parent: 父窗口实例
        """
        self.parent = parent
        self.prev_btn = None
        self.next_btn = None
        self.auto_hide_btn = None
        self.page_slider = None
        self.zoom_slider = None
        self.is_updating_slider = False
        self.nav_widget = None

        self.current_style = parent.current_style  # 获取父窗口的当前样式

    def setup_ui(self, zoom_slider):
        """设置导航控制器的UI组件
        
        Args:
            zoom_slider: ZoomSlider实例，用于控制缩放
        
        Returns:
            QHBoxLayout: 包含导航控件的布局
        """
        # 导航按钮布局
        nav_layout = QtWidgets.QHBoxLayout()
        nav_layout.addStretch()

        # 创建导航按钮组（圆角矩形容器）
        self.nav_widget = QtWidgets.QWidget()
        self.nav_widget.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        nav_button_layout = QtWidgets.QHBoxLayout(self.nav_widget)
        nav_button_layout.setContentsMargins(10, 5, 10, 5)
        nav_button_layout.setSpacing(5)

        # 使用传入的 ZoomSlider
        self.zoom_slider = zoom_slider
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)


        if self.auto_hide_btn: # 保留 auto_hide_btn，如果它存在
            nav_button_layout.addWidget(self.auto_hide_btn)

        nav_layout.addWidget(self.nav_widget)
        nav_layout.addStretch()

        return nav_layout


    def update_navigation_buttons(self):
        """更新导航按钮和页面滑动条的状态"""

        has_manga = self.parent.current_manga is not None
        if has_manga:
            prev_enabled = self.parent.current_manga.current_page > 0
            next_enabled = self.parent.current_manga.current_page < self.parent.current_manga.total_pages - 1

            # 更新滑动条
            self.is_updating_slider = True  # 设置标志，防止触发 valueChanged 信号
            self.page_slider.setMaximum(self.parent.current_manga.total_pages - 1)
            self.page_slider.setValue(self.parent.current_manga.current_page)
            self.is_updating_slider = False

            # 更新标题栏中的页码信息
            self.parent.title_bar.update_page_info()
        else:
            self.page_slider.setMaximum(0)
            self.page_slider.setValue(0)

            # 清空标题栏中的页码信息
            self.parent.title_bar.page_info_label.setText('0 / 0')

    def change_page(self, direction):
        """统一处理页面变化
        Args:
            direction: 1 表示向后，-1 表示向前
        """
        if not self.parent.current_manga:
            return

        step = 1 if self.parent.image_viewer.is_single_page_mode else 2
        current_page = self.parent.current_manga.current_page
        total_pages = self.parent.current_manga.total_pages

        if direction > 0:  # 向后翻页
            if current_page < total_pages - step:
                self.parent.current_manga.current_page += step
                self.parent.image_viewer.show_current_page(self.parent.current_manga,
                                                          self.zoom_slider.value())
                self.update_navigation_buttons()
        else:  # 向前翻页
            if current_page >= step:
                self.parent.current_manga.current_page -= step
                self.parent.image_viewer.show_current_page(self.parent.current_manga,
                                                          self.zoom_slider.value())
                self.update_navigation_buttons()

    def prev_page(self):
        """切换到上一页"""
        self.parent.title_bar.change_page(-1)

    def next_page(self):
        """切换到下一页"""
        self.parent.title_bar.change_page(1)

    def on_zoom_changed(self):
        """处理缩放值变化"""
        if self.parent.current_manga:
            self.parent.image_viewer.show_current_page(self.parent.current_manga,
                                                      self.zoom_slider.value())