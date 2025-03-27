from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from utils import manga_logger as log
from styles.style import Win11Style
from styles.light_style import Win11LightStyle
from styles.dark_style import Win11DarkStyle

class SideNavigation:
    """负责侧边导航栏的组件"""

    def __init__(self, parent, zoom_slider): # 添加 zoom_slider 参数
        self.parent = parent
        self.zoom_slider = zoom_slider # 保存 zoom_slider
        self.nav_widget = None
        self.manga_btn = None
        self.style_btn = None
        self.single_page_btn = None
        self.direction_btn = None
        self.current_style = parent.current_style
        self.style = None
        self.next_page_on_right = True  # 确保初始值为 True
        
    def setup_ui(self):
        # 因为这里的样式要跟默认的标准不一样
        if self.parent.current_style == 'default':
            self.style = Win11Style
        elif self.parent.current_style == 'light':
            self.style = Win11LightStyle
        else:
            self.style = Win11DarkStyle

        # 创建导航栏容器
        self.nav_widget = QWidget()
        self.nav_widget.setFixedWidth(88)  # 设置固定宽度

        # 创建垂直布局
        nav_layout = QVBoxLayout(self.nav_widget)
        nav_layout.setContentsMargins(8, 8, 8, 8)  # 只保留上下边距
        nav_layout.setSpacing(8)  # 设置合适的间距
        nav_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)  # 水平居中并靠上对齐

        # 创建漫画按钮
        self.manga_btn = QPushButton('📖')
        self.manga_btn.setCheckable(True)  # 使按钮可选中
        self.manga_btn.setFixedSize(48, 48)  # 增加按钮大小
        self.manga_btn.setToolTip('漫画阅读')
        self._update_button_style(self.manga_btn) # 使用单独的方法设置样式
        nav_layout.addWidget(self.manga_btn, 0, Qt.AlignCenter)

        # 添加一个伸缩项
        nav_layout.addStretch(1)

        # 创建单双页切换按钮
        self.single_page_btn = QPushButton('双页')
        self.single_page_btn.setFixedSize(48, 48)
        self.single_page_btn.setCheckable(True)
        self._update_button_style(self.single_page_btn)
        self.single_page_btn.clicked.connect(self.toggle_page_mode)
        nav_layout.addWidget(self.single_page_btn, 0, Qt.AlignCenter)

        # 创建阅读方向切换按钮
        self.direction_btn = QPushButton('📖→')
        self.direction_btn.setFixedSize(48, 48)
        self.direction_btn.setChecked(self.parent.image_viewer.next_page_on_right)
        self._update_button_style(self.direction_btn)
        self.direction_btn.clicked.connect(self.toggle_page_direction)
        nav_layout.addWidget(self.direction_btn, 0, Qt.AlignCenter)

        # 创建主题切换按钮
        self.style_btn = QPushButton('🌓')
        self.style_btn.setFixedSize(48, 48)
        self.style_btn.setToolTip('切换主题')
        self._update_button_style(self.style_btn) # 使用单独的方法设置样式
        self.style_btn.clicked.connect(self.toggle_style)
        nav_layout.addWidget(self.style_btn, 0, Qt.AlignCenter)

        # 输出当前应用的样式表内容
        log.info(f"当前按钮样式表: {self.style.ACCENT_COLOR}")

        return self.nav_widget

    def toggle_style(self):
        """切换界面风格"""
        styles = {'default': ('light', '🌓'), 'light': ('dark', '🌓'), 'dark': ('default', '🌓')}
        next_style, _ = styles[self.parent.current_style]
        self.parent.current_style = next_style

        # 重新应用父窗口样式
        if next_style == 'default':
            self.style = Win11Style
            Win11Style.apply_style(self.parent)
        elif next_style == 'light':
            self.style = Win11LightStyle
            Win11LightStyle.apply_style(self.parent)
        else:
            self.style = Win11DarkStyle
            Win11DarkStyle.apply_style(self.parent)

        # 更新按钮样式
        self._update_button_style(self.manga_btn)
        self._update_button_style(self.style_btn)
        self._update_button_style(self.single_page_btn)
        self._update_button_style(self.direction_btn)

    def _update_button_style(self, button):
        """更新按钮的样式"""
        if self.style:
            button.setStyleSheet(f'''
                QPushButton {{
                    min-width: 48px;
                    background: transparent;
                    border: none;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {self.style.SECONDARY_BACKGROUND};
                }}
                QPushButton:pressed {{
                    background-color: {self.style.SECONDARY_BACKGROUND};
                }}
                QPushButton:checked {{
                    background-color: {self.style.SECONDARY_BACKGROUND};
                }}
            ''')

    def toggle_page_mode(self):
        is_single_page = self.single_page_btn.isChecked()
        self.single_page_btn.setText('单页' if is_single_page else '双页')
        self.parent.image_viewer.toggle_page_mode(is_single_page)


    def toggle_page_direction(self):
        # 根据当前的阅读方向更新按钮的文本
        if self.parent.image_viewer.next_page_on_right:
            self.direction_btn.setText('📖→')  # 右往左

        else:
            self.direction_btn.setText('📖←')  # 左往右
        self.parent.image_viewer.toggle_page_direction()  # 调用 MangaImageViewer 中的方法