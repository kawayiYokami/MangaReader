from PyQt5.QtWidgets import (QHBoxLayout, QWidget, QPushButton, QCheckBox)
from PyQt5.QtCore import Qt, QTimer
from utils import manga_logger as log
from ui.components.page_slider import PageSlider
from ui.components.zoom_slider import ZoomSlider
from styles.light_style import Win11LightStyle
from styles.dark_style import Win11DarkStyle
from styles.style import Win11Style
from styles.ui_style import UIStyle

class NavigationController:
    """负责页面导航和控制的组件"""
    
    def __init__(self, parent):
        self.parent = parent
        self.prev_btn = None
        self.next_btn = None
        self.single_page_btn = None
        self.style_btn = None
        self.auto_hide_btn = None
        self.direction_btn = None
        self.page_slider = None
        self.zoom_slider = None
        self.is_updating_slider = False
        self.nav_widget = None
        
        # 自动隐藏相关
        self.auto_hide = True
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.fade_out_nav)  # 连接到淡出方法
    
    def setup_ui(self, zoom_slider):
        # 导航按钮布局
        nav_layout = QHBoxLayout()
        nav_layout.addStretch()
        
        # 创建导航按钮组（圆角矩形容器）
        self.nav_widget = QWidget()
        self.nav_widget.setAttribute(Qt.WA_StyledBackground, True)
        self._set_nav_opacity(0)  # 初始完全透明
        
        # 设置鼠标追踪
        self.nav_widget.setMouseTracking(True)
        self.nav_widget.enterEvent = self.nav_enter_event
        self.nav_widget.leaveEvent = self.nav_leave_event
        
        nav_button_layout = QHBoxLayout(self.nav_widget)
        nav_button_layout.setContentsMargins(10, 5, 10, 5)
        nav_button_layout.setSpacing(5)
        
        # 使用传入的 ZoomSlider
        self.zoom_slider = zoom_slider
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        
        self.prev_btn = QPushButton('←')
        self.prev_btn.setFixedWidth(30)
        self.prev_btn.clicked.connect(self.prev_page)
        
        self.single_page_btn = QPushButton('双页')
        self.single_page_btn.setFixedWidth(50)
        self.single_page_btn.setCheckable(True)
        self.single_page_btn.clicked.connect(self.toggle_page_mode)
        
        self.next_btn = QPushButton('→')
        self.next_btn.setFixedWidth(30)
        self.next_btn.clicked.connect(self.next_page)
        
        self.direction_btn = QPushButton('→→')
        self.direction_btn.setFixedWidth(30)
        self.direction_btn.setCheckable(True)
        self.direction_btn.setChecked(self.parent.image_viewer.next_page_on_right)
        self.direction_btn.clicked.connect(self.toggle_page_direction)
        
        self.auto_hide_btn = QCheckBox('自动隐藏')
        self.auto_hide_btn.setChecked(True)
        self.auto_hide_btn.stateChanged.connect(self.toggle_auto_hide)
        
        nav_button_layout.addWidget(self.prev_btn)
        nav_button_layout.addWidget(self.single_page_btn)
        nav_button_layout.addWidget(self.next_btn)
        nav_button_layout.addWidget(self.direction_btn)
        nav_button_layout.addWidget(self.zoom_slider)
        
        self.style_btn = QPushButton('默认')
        self.style_btn.setFixedWidth(50)
        self.style_btn.clicked.connect(self.toggle_style)
        nav_button_layout.addWidget(self.style_btn)
        
        nav_button_layout.addWidget(self.auto_hide_btn)
        
        nav_layout.addWidget(self.nav_widget)
        nav_layout.addStretch()

        self._set_nav_opacity(0)
        return nav_layout

    
    def update_navigation_buttons(self):
        has_manga = self.parent.current_manga is not None
        if has_manga:
            prev_enabled = self.parent.current_manga.current_page > 0
            next_enabled = self.parent.current_manga.current_page < self.parent.current_manga.total_pages - 1
            self.prev_btn.setEnabled(prev_enabled)
            self.next_btn.setEnabled(next_enabled)
            
            # 更新滑动条
            self.is_updating_slider = True  # 设置标志，防止触发 valueChanged 信号
            self.page_slider.setMaximum(self.parent.current_manga.total_pages - 1)
            self.page_slider.setValue(self.parent.current_manga.current_page)
            self.is_updating_slider = False
            
            # 更新标题栏中的页码信息
            self.parent.update_page_info()
        else:
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
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
                self.parent.image_viewer.show_current_page(
                    self.parent.current_manga, 
                    self.zoom_slider.value()
                )
                self.update_navigation_buttons()
        else:  # 向前翻页
            if current_page >= step:
                self.parent.current_manga.current_page -= step
                self.parent.image_viewer.show_current_page(
                    self.parent.current_manga, 
                    self.zoom_slider.value()
                )
                self.update_navigation_buttons()

    def prev_page(self):
        self.change_page(-1)
    
    def next_page(self):
        self.change_page(1)
    
    def on_slider_value_changed(self):
        """处理滑动条值变化"""
        if self.parent.current_manga and not self.is_updating_slider:
            self.parent.current_manga.current_page = self.page_slider.value()
            self.parent.image_viewer.show_current_page(
                self.parent.current_manga, 
                self.zoom_slider.value()
            )
            self.update_navigation_buttons()

    def on_zoom_changed(self):
        """处理缩放值变化"""
        if self.parent.current_manga:
            self.parent.image_viewer.show_current_page(
                self.parent.current_manga, 
                self.zoom_slider.value()
            )
    
    def toggle_page_mode(self):
        """切换单页/双页显示模式"""
        is_single_page = self.single_page_btn.isChecked()
        self.single_page_btn.setText('单页' if is_single_page else '双页')
        self.parent.image_viewer.toggle_page_mode(is_single_page)
        if self.parent.current_manga:
            self.parent.image_viewer.show_current_page(
                self.parent.current_manga, 
                self.zoom_slider.value()
            )
            self.update_navigation_buttons()
    
    def toggle_style(self):
        """切换界面风格"""
        styles = {'default': ('light', '亮色'), 'light': ('dark', '暗色'), 'dark': ('default', '默认')}
        next_style, btn_text = styles[self.parent.current_style]
        self.parent.current_style = next_style
        self.style_btn.setText(btn_text)
        
        if next_style == 'default':
            Win11Style.apply_style(self.parent)
        elif next_style == 'light':
            Win11LightStyle.apply_style(self.parent)
        else:
            Win11DarkStyle.apply_style(self.parent)
    
    def toggle_page_direction(self):
        """切换页面显示方向"""
        is_right_to_left = not self.direction_btn.isChecked()
        self.parent.image_viewer.next_page_on_right = not is_right_to_left
        self.direction_btn.setText('→→' if not is_right_to_left else '←←')
        
        # 更新显示
        if self.parent.current_manga:
            self.parent.image_viewer.show_current_page(
                self.parent.current_manga, 
                self.zoom_slider.value()
            )
    
    def nav_leave_event(self, event):
        """鼠标离开导航控件事件"""
        if self.auto_hide:
            self.hide_timer.start(1500)  # 1.5秒后隐藏
    
    def hide_nav_widget(self):
        """隐藏导航控件"""
        if self.auto_hide:
            self._set_nav_opacity(0)  # 改为设置完全透明

    def _set_nav_opacity(self, opacity):
        """设置导航控件的透明度 (0-100)"""
        self.nav_widget.setStyleSheet(UIStyle.get_navigation_widget_style(opacity))

    def fade_in_nav(self):
        """淡入导航控件"""
        self.hide_timer.stop()  # 先停止可能存在的淡出计时器
        for opacity in range(0, 101, 20):  # 加大步长使动画更快
            QTimer.singleShot(opacity * 1, lambda o=opacity: self._set_nav_opacity(o))

    def fade_out_nav(self):
        """淡出导航控件"""
        if self.auto_hide:
            for opacity in range(100, -1, -20):  # 加大步长使动画更快
                QTimer.singleShot((100 - opacity) * 1, lambda o=opacity: self._set_nav_opacity(o))

    def nav_enter_event(self, event):
        """鼠标进入导航控件事件"""
        self.hide_timer.stop()
        self.fade_in_nav()

    def nav_leave_event(self, event):
        """鼠标离开导航控件事件"""
        if self.auto_hide:
            self.hide_timer.start(800)  # 缩短隐藏延迟时间

    def toggle_auto_hide(self, state):
        """切换自动隐藏功能"""
        self.auto_hide = (state == Qt.Checked)
        if not self.auto_hide:
            self.fade_in_nav()
            self.hide_timer.stop()
        else:
            self.fade_out_nav()