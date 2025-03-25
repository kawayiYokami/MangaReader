from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import QMainWindow, QWidget, QApplication
from PyQt5.QtGui import QPainter, QPen, QColor
from styles.style import Win11Style

class BaseWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置无边框窗口
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 创建中心部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 初始化窗口属性
        self._is_moving = False
        self._drag_position = QPoint()
        self._border_width = 5
        self._resizing = False
        self._resize_direction = None
        
        # 应用Win11样式
        Win11Style.apply_style(self)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 检查是否在边框区域
            rect = self.rect()
            pos = event.pos()
            
            # 判断鼠标是否在边框区域
            if pos.x() <= self._border_width:
                if pos.y() <= self._border_width:
                    self._resize_direction = 'top_left'
                elif pos.y() >= rect.height() - self._border_width:
                    self._resize_direction = 'bottom_left'
                else:
                    self._resize_direction = 'left'
            elif pos.x() >= rect.width() - self._border_width:
                if pos.y() <= self._border_width:
                    self._resize_direction = 'top_right'
                elif pos.y() >= rect.height() - self._border_width:
                    self._resize_direction = 'bottom_right'
                else:
                    self._resize_direction = 'right'
            elif pos.y() <= self._border_width:
                self._resize_direction = 'top'
            elif pos.y() >= rect.height() - self._border_width:
                self._resize_direction = 'bottom'
            
            if self._resize_direction:
                self._resizing = True
                self._drag_position = pos
                event.accept()
                return
    
    def mouseMoveEvent(self, event):
        if self._resizing and self._resize_direction:
            delta = event.pos() - self._drag_position
            rect = self.geometry()
            
            if self._resize_direction in ['left', 'top_left', 'bottom_left']:
                rect.setLeft(rect.left() + delta.x())
            if self._resize_direction in ['right', 'top_right', 'bottom_right']:
                rect.setRight(rect.right() + delta.x())
            if self._resize_direction in ['top', 'top_left', 'top_right']:
                rect.setTop(rect.top() + delta.y())
            if self._resize_direction in ['bottom', 'bottom_left', 'bottom_right']:
                rect.setBottom(rect.bottom() + delta.y())
            
            # 限制最小尺寸
            if rect.width() >= 200 and rect.height() >= 150:
                # 窗口吸附功能
                desktop = QApplication.desktop().availableGeometry()
                snap_distance = 10  # 吸附距离阈值
                
                # 左边缘吸附
                if abs(rect.left() - desktop.left()) < snap_distance:
                    rect.setLeft(desktop.left())
                # 右边缘吸附
                if abs(rect.right() - desktop.right()) < snap_distance:
                    rect.setRight(desktop.right())
                # 上边缘吸附
                if abs(rect.top() - desktop.top()) < snap_distance:
                    rect.setTop(desktop.top())
                # 下边缘吸附
                if abs(rect.bottom() - desktop.bottom()) < snap_distance:
                    rect.setBottom(desktop.bottom())
                
                self.setGeometry(rect)
                self._drag_position = event.pos()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._resizing = False
            self._resize_direction = None
    
    def paintEvent(self, event):
        # 绘制窗口阴影和边框
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景
        painter.setBrush(QColor(Win11Style.BACKGROUND_COLOR))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), Win11Style.BORDER_RADIUS, Win11Style.BORDER_RADIUS)
        
        # 绘制边框
        painter.setPen(QPen(QColor(Win11Style.BORDER_COLOR), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect(), Win11Style.BORDER_RADIUS, Win11Style.BORDER_RADIUS)