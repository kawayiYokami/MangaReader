from PyQt5.QtCore import Qt, QPoint, QSize
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QIcon
from style import Win11Style

class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(32)  # 固定标题栏高度
        
        # 初始化界面
        self.initUI()
        
        # 初始化窗口移动相关变量
        self._is_moving = False
        self._drag_position = QPoint()
        
        # 设置鼠标追踪
        self.setMouseTracking(True)
    
    def initUI(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)
        
        # 窗口图标
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(16, 16)
        layout.addWidget(self.icon_label)
        layout.addSpacing(5)
        
        # 窗口标题
        self.title_label = QLabel("")
        self.title_label.setStyleSheet(f"color: {Win11Style.TEXT_COLOR};")
        layout.addWidget(self.title_label)
        
        # 最小化按钮
        self.min_button = QPushButton()
        self.min_button.setFixedSize(46, 32)
        self.min_button.setStyleSheet(self._get_button_style())
        self.min_button.clicked.connect(self.parent.showMinimized)
        layout.addWidget(self.min_button)
        
        # 最大化按钮
        self.max_button = QPushButton()
        self.max_button.setFixedSize(46, 32)
        self.max_button.setStyleSheet(self._get_button_style())
        self.max_button.clicked.connect(self.toggleMaximize)
        layout.addWidget(self.max_button)
        
        # 关闭按钮
        self.close_button = QPushButton()
        self.close_button.setFixedSize(46, 32)
        self.close_button.setStyleSheet(self._get_button_style(True))
        self.close_button.clicked.connect(self.parent.close)
        layout.addWidget(self.close_button)
        
        self.setLayout(layout)
    
    def _get_button_style(self, is_close=False):
        hover_color = "#C42B1C" if is_close else Win11Style.TITLE_BAR_HOVER_COLOR
        active_color = "#C42B1C" if is_close else Win11Style.TITLE_BAR_ACTIVE_COLOR
        hover_text_color = "white" if is_close else Win11Style.TEXT_COLOR
        
        return f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 0;
                padding: 0;
                margin: 0;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                color: {hover_text_color};
            }}
            QPushButton:pressed {{
                background-color: {active_color};
            }}
        """
    
    def setTitle(self, title):
        self.title_label.setText(title)
    
    def setIcon(self, icon):
        if isinstance(icon, QIcon):
            pixmap = icon.pixmap(QSize(16, 16))
            self.icon_label.setPixmap(pixmap)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_moving = True
            self._drag_position = event.globalPos() - self.parent.pos()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if self._is_moving and event.buttons() == Qt.LeftButton:
            self.parent.move(event.globalPos() - self._drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_moving = False
    
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggleMaximize()
    
    def toggleMaximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制标题栏背景
        painter.setBrush(QColor(Win11Style.TITLE_BAR_COLOR))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())