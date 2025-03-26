from PyQt5.QtWidgets import QSlider, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen
from styles.style import Win11Style
from styles.win_theme_color import get_system_theme_colors
from utils import manga_logger as log
from utils.color_utils import get_rgba_string

class VerticalZoomSlider(QWidget):
    """垂直缩放滑动条组件，采用Win11 Fluent设计风格"""
    
    valueChanged = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)

        # 获取系统主题色
        self.primary_color, self.accent_color = get_system_theme_colors()
        
        self.setFixedWidth(36)  # 稍微加宽以适应Fluent风格
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        # 创建垂直滑动条
        self.slider = QSlider(Qt.Vertical, self)
        self.slider.setMinimumHeight(300)  # 设置最小高度
        self.slider.setMaximumHeight(900)  # 设置最大高度
        self.slider.setMinimum(1)
        self.slider.setMaximum(200)
        self.slider.setValue(100)
        self.slider.valueChanged.connect(self.on_value_changed)
        
        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 20, 6, 20)  # 增加内边距

        # 创建加号标签
        self.plus_label = QLabel("✚")
        self.plus_label.setAlignment(Qt.AlignCenter) # 可选：设置文本居中

        # 创建减号标签
        self.minus_label = QLabel("−")
        self.minus_label.setAlignment(Qt.AlignCenter) # 可选：设置文本居中

        layout.addWidget(self.plus_label)
        layout.addWidget(self.slider)
        layout.addWidget(self.minus_label)
        
        # 自动隐藏相关
        self.setAutoHide(True)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.fadeOut)
        self.setMouseTracking(True)
        self.is_hidden = False

        # 初始样式 - 完全透明
        self._update_style(opacity=0)

    def _update_style(self, opacity):
        """更新为Win11 Fluent风格样式"""
        # 基础透明度计算 (0-100 => 0.0-1.0)
        alpha = opacity / 100.0
        
        

        # Fluent风格颜色
        bg_color = f"rgba(243, 243, 243, {0.0*alpha})"  # 背景轻微透明
        groove_color = f"rgba(200, 200, 200, {0.6*alpha})"  # 轨道颜色
        handle_color = get_rgba_string(self.primary_color, alpha)
        
        self.setStyleSheet(f"""
            VerticalZoomSlider {{
                background-color: {bg_color};
                border-radius: {Win11Style.CORNER_RADIUS}px;
                border: 1px solid rgba(200, 200, 200, {0.3*alpha});
            }}
            QSlider::groove:vertical {{
                background: {groove_color};
                width: 4px;
                border-radius: 2px;
                margin: 0 12px;  /* 两侧留出空间 */
            }}
            QSlider::handle:vertical {{
                background: {handle_color};
                width: 12px;    /* 宽度 */
                height: 12px;   /* 高度保持与宽度相同 */
                margin: 0 -4px; /* 适当外边距使手柄超出轨道 */
                border-radius: 6px; /* 半径设为宽度/高度的一半 */
                border: none;
            }}
        """)

        # 设置加号和减号标签的颜色，包括透明度
        self.plus_label.setStyleSheet(f"color: {handle_color};")
        self.minus_label.setStyleSheet(f"color: {handle_color};")

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