from PyQt5.QtCore import Qt, QPoint, QSize
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QLineEdit, QVBoxLayout
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QIcon, QPixmap
from styles.style import Win11Style
from styles.ui_style import UIStyle
from ui.components.page_slider import PageSlider

class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(48)  # 固定标题栏高度
        
        # 页码显示和滑动条
        self.page_info_label = None
        self.page_slider = PageSlider(self)  # 直接初始化PageSlider
        
        # 初始化界面
        self.initUI()
        
        # 初始化窗口移动相关变量
        self._is_moving = False  # 标记窗口是否正在移动
        self._drag_position = QPoint()  # 记录拖动开始时的鼠标位置
        
        # 设置鼠标追踪
        self.setMouseTracking(True)  # 启用鼠标追踪以检测鼠标移动
    
    def initUI(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 0, 10, 0)  # 设置布局的边距
        layout.setSpacing(0)  # 设置控件之间的间距
        
        # 窗口图标
        self.icon_label = QLabel()  # 用于显示窗口图标的标签
        self.icon_label.setFixedSize(16, 16)  # 设置图标大小
        #layout.addWidget(self.icon_label)
        #layout.addSpacing(5)  # 添加间距
        
        # 添加文件夹按钮
        self.select_dir_btn = QPushButton('📂')  # 文件夹选择按钮
        self.select_dir_btn.setMaximumWidth(50)  # 设置按钮最大宽度
        self.select_dir_btn.setStyleSheet(UIStyle.get_title_bar_select_dir_button_style())  # 设置按钮样式
        layout.addWidget(self.select_dir_btn)
        layout.addSpacing(5)
        
        # 添加搜索框
        self.search_input = QLineEdit()  # 搜索输入框
        self.search_input.setPlaceholderText('搜索漫画...')  # 设置占位符文本
        self.search_input.setMaximumWidth(200)  # 设置输入框最大宽度
        self.search_input.setStyleSheet(UIStyle.get_title_bar_search_input_style())  # 设置输入框样式
        layout.addWidget(self.search_input)
        
        # 添加页码信息和滑动条
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(2)
        
        # 页码信息标签
        self.page_info_label = QLabel('0 / 0')
        self.page_info_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.page_info_label)
        
        # 页面滑动条
        center_layout.addWidget(self.page_slider)
        
        layout.addStretch(1)  # 添加弹性空间以调整布局
        layout.addWidget(center_widget)
        layout.addStretch(1)  # 添加弹性空间以调整布局
        
        # 最小化按钮
        self.min_button = QPushButton()  # 最小化按钮
        self.min_button.setFixedSize(46, 32)  # 设置按钮大小
        self.min_button.setStyleSheet(self._get_button_style())  # 设置按钮样式
        self.min_button.clicked.connect(self.parent.showMinimized)  # 连接点击事件
        self.update_min_button_icon()  # 更新按钮图标
        layout.addWidget(self.min_button)
        
        # 最大化按钮
        self.max_button = QPushButton()  # 最大化按钮
        self.max_button.setFixedSize(46, 32)
        self.max_button.setStyleSheet(self._get_button_style())
        self.max_button.clicked.connect(self.toggleMaximize)  # 连接点击事件以切换最大化状态
        self.update_max_button_icon()  # 更新按钮图标
        layout.addWidget(self.max_button)
        
        # 关闭按钮
        self.close_button = QPushButton()  # 关闭按钮
        self.close_button.setFixedSize(46, 32)
        self.close_button.setStyleSheet(self._get_button_style(True))  # 设置关闭按钮样式
        self.close_button.clicked.connect(self.parent.close)  # 连接点击事件以关闭窗口
        self.update_close_button_icon()  # 更新按钮图标
        layout.addWidget(self.close_button)
        
        self.setLayout(layout)  # 设置布局
    
    def _get_button_style(self, is_close=False):
        """获取按钮样式"""
        return UIStyle.get_title_bar_button_style(is_close)
    
    def setTitle(self, title):
        """设置标题文本"""
        self.title_label.setText(title)
    
    def setIcon(self, icon):
        """设置窗口图标"""
        if isinstance(icon, QIcon):
            pixmap = icon.pixmap(QSize(16, 16))
            self.icon_label.setPixmap(pixmap)
    
    def mousePressEvent(self, event):
        """处理鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            self._is_moving = True
            self._drag_position = event.globalPos() - self.parent.pos()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """处理鼠标移动事件"""
        if self._is_moving and event.buttons() == Qt.LeftButton:
            self.parent.move(event.globalPos() - self._drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self._is_moving = False
    
    def mouseDoubleClickEvent(self, event):
        """处理鼠标双击事件"""
        if event.button() == Qt.LeftButton:
            self.toggleMaximize()
    
    def update_min_button_icon(self):
        """更新最小化按钮图标"""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(Win11Style.TEXT_COLOR), 1))
        painter.drawLine(4, 8, 12, 8)
        painter.end()
        self.min_button.setIcon(QIcon(pixmap))
        self.min_button.setIconSize(QSize(16, 16))
    
    def update_max_button_icon(self):
        """更新最大化按钮图标"""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(Win11Style.TEXT_COLOR), 1))
        if self.parent.isMaximized():
            painter.drawRect(4, 4, 8, 8)
            painter.drawLine(6, 4, 6, 2)
            painter.drawLine(6, 2, 12, 2)
            painter.drawLine(12, 2, 12, 8)
            painter.drawLine(12, 8, 10, 8)
        else:
            painter.drawRect(4, 4, 8, 8)
        painter.end()
        self.max_button.setIcon(QIcon(pixmap))
        self.max_button.setIconSize(QSize(16, 16))
    
    def update_close_button_icon(self):
        """更新关闭按钮图标"""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(Win11Style.TEXT_COLOR), 1))
        painter.drawLine(4, 4, 12, 12)
        painter.drawLine(12, 4, 4, 12)
        painter.end()
        self.close_button.setIcon(QIcon(pixmap))
        self.close_button.setIconSize(QSize(16, 16))
    
    def toggleMaximize(self):
        """切换窗口最大化状态"""
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()
        self.update_max_button_icon()
    
    def paintEvent(self, event):
        """绘制标题栏背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(Win11Style.TITLE_BAR_COLOR))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())