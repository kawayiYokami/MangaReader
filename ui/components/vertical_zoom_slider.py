from PyQt5.QtWidgets import QSlider, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen
from styles.style import Win11Style
from styles.ui_style import UIStyle
from styles.win_theme_color import get_system_theme_colors
import manga_logger as log

class VerticalZoomSlider(QWidget):
    """垂直缩放滑动条组件，采用Win11 Fluent设计风格"""
    
    valueChanged = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)

        # 获取系统主题色
        self.primary_color, self.accent_color = get_system_theme_colors()
        
        self.setFixedWidth(36)  # 稍微加宽以适应Fluent风格
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        # 初始样式 - 完全透明
        self._update_style(opacity=0)
        
        # 创建垂直滑动条
        self.slider = QSlider(Qt.Vertical, self)
        self.slider.setMinimum(1)
        self.slider.setMaximum(200)
        self.slider.setValue(100)
        self.slider.valueChanged.connect(self.on_value_changed)
        
        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 12, 6, 12)  # 增加内边距
        layout.addWidget(self.slider)
        
        # 自动隐藏相关
        self.setAutoHide(True)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.fadeOut)
        self.setMouseTracking(True)
        self.is_hidden = False
    
    def _update_style(self, opacity):
        """更新为Win11 Fluent风格样式"""
        self.setStyleSheet(UIStyle.get_vertical_zoom_slider_style(opacity))
    
    def setAutoHide(self, auto_hide):
        self.auto_hide = auto_hide
        if not auto_hide:
            self.fadeIn()
    
    def enterEvent(self, event):
        self.hide_timer.stop()
        self.fadeIn()
        # log.info("鼠标进入了垂直缩放滑动条")
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        if self.auto_hide:
            self.hide_timer.start(200)
        # log.info("鼠标离开了垂直缩放滑动条")
        super().leaveEvent(event)
    
    def fadeIn(self):
        """淡入动画"""
        self.is_hidden = False
        # 使用动画效果逐渐显示
        for opacity in range(0, 101, 10):
            QTimer.singleShot(opacity * 2, lambda o=opacity: self._update_style(o))
    
    def fadeOut(self):
        """淡出动画"""
        self.is_hidden = True
        # 使用动画效果逐渐隐藏
        for opacity in range(100, -1, -10):
            QTimer.singleShot((100 - opacity) * 2, lambda o=opacity: self._update_style(o))
    
    def wheelEvent(self, event):
        if self.is_hidden:
            self.fadeIn()
        
        delta = event.angleDelta().y()
        if delta < 0:
            self.slider.setValue(self.slider.value() - 5)
        else:
            self.slider.setValue(self.slider.value() + 5)
        event.accept()
    
    def on_value_changed(self, value):
        self.valueChanged.emit(value)
    
    def value(self):
        return self.slider.value()
    
    def setValue(self, value):
        self.slider.setValue(value)