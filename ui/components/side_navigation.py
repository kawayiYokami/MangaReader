from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from utils import manga_logger as log
from styles.style import Win11Style
from styles.light_style import Win11LightStyle
from styles.dark_style import Win11DarkStyle
class SideNavigation:
    """负责侧边导航栏的组件"""
    
    def __init__(self, parent):
        self.parent = parent
        self.nav_widget = None
        self.manga_btn = None
        self.current_style = parent.current_style
    
    def setup_ui(self):

        # 因为这里的样式要跟默认的标准不一样
        if self.parent.current_style == 'default':
            style = Win11Style
        elif self.parent.current_style == 'light':
            style = Win11LightStyle
        else:
            style = Win11DarkStyle

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
        self.manga_btn.setStyleSheet(f'''
            QPushButton {{
                min-width: 48px;
                background: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {style.SECONDARY_BACKGROUND};
            }}
            QPushButton:pressed {{
                background-color: {style.SECONDARY_BACKGROUND};
            }}
            QPushButton:checked {{
                background-color: {style.SECONDARY_BACKGROUND};
            }}
        ''')
        
        nav_layout.addWidget(self.manga_btn, 0, Qt.AlignCenter)
        nav_layout.addStretch()
        
        # 输出当前应用的样式表内容
        log.info(f"当前按钮样式表: {style.ACCENT_COLOR}")
        
        return self.nav_widget