from PyQt5.QtCore import Qt, QPoint, QSize, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QVBoxLayout, QFileDialog, QApplication
)
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QIcon, QPixmap
from styles.light_style import Win11LightStyle
from styles.dark_style import Win11DarkStyle
from styles.style import Win11Style
from ui.components.page_slider import PageSlider
from ui.components.slider_controller import SliderController
from utils import manga_logger as log
import os


class TitleBar(QWidget):
    search_results_updated = pyqtSignal(list)

    def __init__(self, parent=None, navigation_controller=None):
        super().__init__(parent)
        self.parent = parent
        self.navigation_controller = navigation_controller
        self.setFixedHeight(48)

        # 页码显示和滑动条
        self.page_info_label = None
        self.page_slider = PageSlider(self)

        # 初始化滑动条控制器
        self.slider_controller = SliderController(self.parent)
        self.slider_controller.setup_slider(self.page_slider)

        # 搜索相关
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)

        # 初始化界面
        self.initUI()

        # 初始化窗口移动相关变量
        self._is_moving = False
        self._drag_position = QPoint()

    def initUI(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)

        # 窗口图标
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(16, 16)

        # 添加文件夹按钮
        self.select_dir_btn = QPushButton('📂')
        self.select_dir_btn.setMaximumWidth(50)
        self.select_dir_btn.clicked.connect(self.select_directory)
        layout.addWidget(self.select_dir_btn)
        layout.addSpacing(5)

        # 添加搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('搜索漫画...')
        self.search_input.setMaximumWidth(200)
        self.search_input.textChanged.connect(self.on_search_text_changed)
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

        layout.addStretch(1)
        layout.addWidget(center_widget)
        layout.addStretch(1)

        # 最小化按钮
        self.min_button = QPushButton()
        self.min_button.setFixedSize(46, 32)
        self.min_button.setStyleSheet(self._get_button_style())
        self.min_button.clicked.connect(self.parent.showMinimized)
        self.update_min_button_icon()
        layout.addWidget(self.min_button)

        # 最大化按钮
        self.max_button = QPushButton()
        self.max_button.setFixedSize(46, 32)
        self.max_button.setStyleSheet(self._get_button_style())
        self.max_button.clicked.connect(self.toggleMaximize)
        self.update_max_button_icon()
        layout.addWidget(self.max_button)

        # 关闭按钮
        self.close_button = QPushButton()
        self.close_button.setFixedSize(46, 32)
        self.close_button.setStyleSheet(self._get_button_style(True))
        self.close_button.clicked.connect(self.parent.close)
        self.update_close_button_icon()
        layout.addWidget(self.close_button)

        self.setLayout(layout)
        self.page_slider.valueChanged.connect(self.on_page_slider_value_changed)

    def on_page_slider_value_changed(self):
        """处理标题栏滑动条值变化"""
        self.slider_controller.on_slider_value_changed()

    def change_page(self, direction):
        """调用导航控制器的change_page方法"""
        if self.navigation_controller:
            self.navigation_controller.change_page(direction)
            self.update_page_info()

    def update_page_info(self):
        """更新页码信息"""
        if self.parent.current_manga:
            current_page = self.parent.current_manga.current_page + 1
            total_pages = self.parent.current_manga.total_pages
            self.page_info_label.setText(f'{current_page} / {total_pages}')
        else:
            self.page_info_label.setText('0 / 0')

    def select_directory(self):
        log.info("打开选择漫画目录对话框")
        dir_path = QFileDialog.getExistingDirectory(self, '选择漫画目录')
        if dir_path:
            log.info(f"用户选择了目录: {dir_path}")
            if self.parent:
                self.parent.manga_manager.set_manga_dir(dir_path)
                self.parent.tag_manager.update_tag_buttons()
                self.parent.manga_list_manager.update_manga_list()
        else:
            log.info("用户取消了目录选择")

    def on_search_text_changed(self, text):
        """当搜索框文本改变时触发"""
        self.search_timer.stop()
        self.search_timer.start(100)

    def perform_search(self):
        """执行搜索"""
        search_text = self.search_input.text().lower()
        log.info(f"执行搜索: {search_text}")

        if not search_text:
            if self.parent:
                self.search_results_updated.emit(self.parent.manga_manager.manga_list)
            return

        if self.parent and self.parent.manga_manager.manga_list:
            filtered_manga = [
                manga for manga in self.parent.manga_manager.manga_list
                if search_text in os.path.basename(manga.file_path).lower()
            ]
            self.search_results_updated.emit(filtered_manga)

    def _get_button_style(self, is_close=False):
        """获取按钮样式"""
        if self.parent.current_style == 'default':
            style = Win11Style
        elif self.parent.current_style == 'light':
            style = Win11LightStyle
        else:
            style = Win11DarkStyle

        hover_color = style.HOVER_COLOR
        active_color = style.SELECTED_COLOR
        hover_PRIMARY_TEXT = style.PRIMARY_TEXT
        PRIMARY_TEXT = style.PRIMARY_TEXT

        return f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 0;
                padding: 0;
                margin: 0;
                color: {PRIMARY_TEXT};
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                color: {hover_PRIMARY_TEXT};
            }}
            QPushButton:pressed {{
                background-color: {active_color};
            }}
        """

    def setTitle(self, title):
        """设置标题文本"""
        pass

    def setIcon(self, icon):
        """设置窗口图标"""
        if isinstance(icon, QIcon):
            pixmap = icon.pixmap(QSize(16, 16))

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
        painter.setPen(QPen(QColor(Win11Style.PRIMARY_TEXT), 1))
        painter.drawLine(4, 8, 12, 8)
        painter.end()
        self.min_button.setIcon(QIcon(pixmap))
        self.min_button.setIconSize(QSize(16, 16))

    def update_max_button_icon(self):
        """更新最大化按钮图标"""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(Win11Style.PRIMARY_TEXT), 1))
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
        style = Win11Style
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(style.PRIMARY_TEXT), 1))
        painter.drawLine(4, 4, 12, 12)
        painter.drawLine(4, 12, 12, 4)
        painter.end()
        self.close_button.setIcon(QIcon(pixmap))
        self.close_button.setIconSize(QSize(16, 16))

    def toggleMaximize(self):
        """切换最大化状态"""
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()
        self.update_max_button_icon()