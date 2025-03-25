from PyQt5.QtWidgets import (QHBoxLayout, QWidget, QPushButton)
from PyQt5.QtCore import Qt
from utils import manga_logger as log
from ui.components.page_slider import PageSlider
from ui.components.zoom_slider import ZoomSlider
from styles.light_style import Win11LightStyle
from styles.dark_style import Win11DarkStyle
from styles.style import Win11Style

class NavigationController:
    """负责页面导航和控制的组件"""
    
    def __init__(self, parent):
        self.parent = parent
        self.prev_btn = None
        self.next_btn = None
        self.single_page_btn = None
        self.style_btn = None
        self.page_slider = None
        self.zoom_slider = None
        self.is_updating_slider = False
    
    def setup_ui(self, zoom_slider):
        # 导航按钮布局
        nav_layout = QHBoxLayout()
        nav_layout.addStretch()
        
        # 创建导航按钮组
        nav_button_widget = QWidget()
        nav_button_layout = QHBoxLayout(nav_button_widget)
        nav_button_layout.setContentsMargins(0, 0, 0, 0)
        nav_button_layout.setSpacing(5)
        
        # 使用自定义的 PageSlider
        self.page_slider = PageSlider()
        self.page_slider.valueChanged.connect(self.on_slider_value_changed)
        
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
        
        nav_button_layout.addWidget(self.page_slider)
        nav_button_layout.addWidget(self.prev_btn)
        nav_button_layout.addWidget(self.single_page_btn)
        nav_button_layout.addWidget(self.next_btn)
        nav_button_layout.addWidget(self.zoom_slider)
        
        # 添加风格切换按钮
        self.style_btn = QPushButton('默认')
        self.style_btn.setFixedWidth(50)
        self.style_btn.clicked.connect(self.toggle_style)
        nav_button_layout.addWidget(self.style_btn)
        
        nav_layout.addWidget(nav_button_widget)
        nav_layout.addStretch()
        
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
        else:
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            self.page_slider.setMaximum(0)
            self.page_slider.setValue(0)
    
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