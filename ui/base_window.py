from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtWidgets import QMainWindow, QWidget, QApplication
from PyQt5.QtGui import QPainter, QPen, QColor, QCursor
from styles.style import Win11Style
from styles.light_style import Win11LightStyle
from styles.dark_style import Win11DarkStyle
from utils import manga_logger as log


class BaseWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 设置无边框窗口
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 初始化窗口属性
        self._border_width = 20

        # 应用Win11样式
        self.current_style = 'default'  # 初始样式，可以根据您的需求修改
        self._apply_style()

    def _apply_style(self):
        if self.current_style == 'default':
            style = Win11Style
        elif self.current_style == 'light':
            style = Win11LightStyle
        else:
            style = Win11DarkStyle
        style.apply_style(self)
        self.update()  # 触发重绘

    def paintEvent(self, event):
        """应用当前主题样式"""
        if self.current_style == 'default':
            style = Win11Style
        elif self.current_style == 'light':
            style = Win11LightStyle
        else:
            style = Win11DarkStyle

        # 绘制窗口阴影和边框
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制背景
        painter.setBrush(QColor(style.BACKGROUND_COLOR))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), style.CORNER_RADIUS, style.CORNER_RADIUS)

        # 绘制边框
        painter.setPen(QPen(QColor(style.HOVER_COLOR), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect(), style.CORNER_RADIUS, style.CORNER_RADIUS)