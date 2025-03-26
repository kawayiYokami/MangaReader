from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
from styles.win_theme_color import get_system_theme_colors

class Win11DarkStyle:
    """
    Windows 11 Fluent Design 夜间模式风格配置
    包含完整的颜色系统、控件样式和动画效果参数
    """
    
    # ====================== 颜色系统 ======================
    PRIMARY_COLOR, ACCENT_COLOR = get_system_theme_colors()  # 从系统获取的主题色和强调色
    
    # 基础颜色
    BACKGROUND_COLOR = "#202020"  # 主背景色 (深灰)
    SECONDARY_BACKGROUND = "#2D2D2D"  # 次级背景色 (用于卡片、面板等)
    TERTIARY_BACKGROUND = "#252525"  # 第三背景色 (用于悬停状态)
    
    # 文本颜色
    PRIMARY_TEXT = "#FFFFFF"  # 主要文本颜色 (90%不透明度)
    SECONDARY_TEXT = "#A0A0A0"  # 次要文本颜色 (60%不透明度)
    DISABLED_TEXT = "#606060"  # 禁用状态文本颜色 (40%不透明度)
    
    # 边框和分隔线
    DIVIDER_COLOR = "#404040"  # 分隔线颜色 (12%不透明度白色)
    CARD_BORDER = "#383838"  # 卡片边框颜色 (8%不透明度白色)
    FOCUS_BORDER = ACCENT_COLOR  # 焦点边框颜色 (使用系统强调色)
    
    # 交互状态
    HOVER_COLOR = "#3A3A3A"  # 悬停状态颜色 (使用图层叠加效果)
    PRESSED_COLOR = "#4D4D4D"  # 按下状态颜色
    SELECTED_COLOR = ACCENT_COLOR  # 选中状态颜色 (使用系统强调色)
    SELECTED_TEXT = "#FFFFFF"  # 选中状态的文本颜色
    
    # ====================== 字体系统 ======================
    FONT_FAMILY = "Microsoft YaHei"  # 替换为微软雅黑字体
    FONT_SIZE = 9  # 基础字号 (单位: pt)
    HEADER1_SIZE = 20  # 一级标题
    HEADER2_SIZE = 16  # 二级标题
    SUBHEADER_SIZE = 12  # 副标题
    
    # ====================== 形状系统 ======================
    CORNER_RADIUS = 4  # 基础圆角大小 (单位: px)
    SMALL_CORNER = 2  # 小型控件圆角 (如复选框)
    LARGE_CORNER = 8  # 大型容器圆角 (如卡片)
    
    # ====================== 间距系统 ======================
    CONTENT_MARGIN = 12  # 内容边距
    ITEM_SPACING = 8  # 项间距
    GROUP_SPACING = 16  # 组间距
    
    # ====================== 动画参数 ======================
    HOVER_ANIM_DURATION = 150  # 悬停动画时长 (ms)
    FOCUS_ANIM_DURATION = 100  # 焦点动画时长
    PRESS_ANIM_DURATION = 50  # 按下动画时长
    
    # ====================== 阴影效果 ======================
    CARD_SHADOW = "0 2px 8px 0 rgba(0, 0, 0, 0.3)"  # 卡片阴影 (16dp elevation)
    TOOLTIP_SHADOW = "0 4px 12px 0 rgba(0, 0, 0, 0.4)"  # 工具提示阴影 (24dp)
    
    @staticmethod
    def get_base_style():
        """
        生成基础Fluent风格样式表
        包含所有核心控件的Fluent设计规范
        """
        return f"""
        /* ================= 基础容器样式 ================= */
        QMainWindow {{
            background-color: {Win11DarkStyle.BACKGROUND_COLOR};
            border: none;
        }}
        
        QWidget {{
            background-color: transparent;
            color: {Win11DarkStyle.PRIMARY_TEXT};
            font-family: "{Win11DarkStyle.FONT_FAMILY}";
            font-size: {Win11DarkStyle.FONT_SIZE}pt;
            selection-background-color: {Win11DarkStyle.SELECTED_COLOR};
            selection-color: {Win11DarkStyle.SELECTED_TEXT};
        }}
        
        /* ================= 卡片式容器 ================= */
        QFrame[frameShape="1"],  /* QFrame.StyledPanel */
        QGroupBox {{
            background-color: {Win11DarkStyle.SECONDARY_BACKGROUND};
            border: 1px solid {Win11DarkStyle.CARD_BORDER};
            border-radius: {Win11DarkStyle.LARGE_CORNER}px;
            padding: {Win11DarkStyle.CONTENT_MARGIN}px;
            margin: {Win11DarkStyle.GROUP_SPACING/2}px;
        }}
        
        /* ================= 按钮样式 ================= */
        QPushButton {{
            background-color: {Win11DarkStyle.SECONDARY_BACKGROUND};
            border: none;
            border-radius: {Win11DarkStyle.CORNER_RADIUS}px;
            padding: 6px 12px;
            min-width: 80px;
        }}
        
        QPushButton:hover {{
            background-color: {Win11DarkStyle.PRIMARY_COLOR};
        }}
        
        QPushButton:pressed {{
            background-color: {Win11DarkStyle.ACCENT_COLOR};
        }}
        
        QPushButton:disabled {{
            background-color: {Win11DarkStyle.DIVIDER_COLOR};
            color: {Win11DarkStyle.DISABLED_TEXT};
        }}
        
        /* ================= 输入控件 ================= */
        QLineEdit,
        QTextEdit,
        QPlainTextEdit,
        QComboBox {{
            background-color: {Win11DarkStyle.SECONDARY_BACKGROUND};
            border: 1px solid {Win11DarkStyle.DIVIDER_COLOR};
            border-radius: {Win11DarkStyle.CORNER_RADIUS}px;
            padding: 6px 8px;
            selection-background-color: {Win11DarkStyle.ACCENT_COLOR};
            selection-color: white;
        }}
        
        QLineEdit:focus,
        QTextEdit:focus,
        QPlainTextEdit:focus {{
            border: 1px solid {Win11DarkStyle.FOCUS_BORDER};
        }}
        
        /* ================= 滑动条 ================= */
        QSlider::groove:horizontal {{
            border: none;
            height: 4px;
            background-color: {Win11DarkStyle.DIVIDER_COLOR};
            border-radius: 2px;
        }}
        
        QSlider::handle:horizontal {{
            background-color: {Win11DarkStyle.ACCENT_COLOR};
            border: none;
            width: 16px;
            height: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }}
        
        /* ================= 复选框/单选按钮 ================= */
        QCheckBox,
        QRadioButton {{
            spacing: 8px;
        }}
        
        QCheckBox::indicator,
        QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border-radius: {Win11DarkStyle.SMALL_CORNER}px;
            border: 1px solid {Win11DarkStyle.DIVIDER_COLOR};
        }}
        
        QCheckBox::indicator:checked,
        QRadioButton::indicator:checked {{
            background-color: {Win11DarkStyle.ACCENT_COLOR};
            border-color: {Win11DarkStyle.ACCENT_COLOR};
        }}
        
        /* ================= 滚动条 ================= */
        QScrollBar:vertical {{
            border: none;
            background-color: transparent;
            width: 8px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: #606060;
            border-radius: 4px;
            min-height: 30px;
        }}
        
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            background: none;
        }}
        
        /* ================= 树形视图 ================= */
        QTreeView {{
            border: 1px solid {Win11DarkStyle.DIVIDER_COLOR};
            border-radius: {Win11DarkStyle.CORNER_RADIUS}px;
            background-color: {Win11DarkStyle.SECONDARY_BACKGROUND};
            alternate-background-color: {Win11DarkStyle.TERTIARY_BACKGROUND};
        }}
        
        QTreeView::item {{
            padding: 4px;
            border: none;
        }}
        
        QTreeView::item:hover {{
            background-color: {Win11DarkStyle.HOVER_COLOR};
        }}
        
        QTreeView::item:selected {{
            background-color: {Win11DarkStyle.SELECTED_COLOR};
            color: {Win11DarkStyle.SELECTED_TEXT};
        }}
        
        /* ================= 标签页 ================= */
        QTabWidget::pane {{
            border: none;
            border-top: 1px solid {Win11DarkStyle.DIVIDER_COLOR};
        }}
        
        QTabBar::tab {{
            background-color: transparent;
            padding: 8px 12px;
            border-bottom: 2px solid transparent;
        }}
        
        QTabBar::tab:hover {{
            background-color: {Win11DarkStyle.HOVER_COLOR};
        }}
        
        QTabBar::tab:selected {{
            border-bottom: 2px solid {Win11DarkStyle.ACCENT_COLOR};
            color: {Win11DarkStyle.PRIMARY_TEXT};
        }}
        """
    
    @staticmethod
    def apply_style(widget):
        """
        应用Fluent风格到指定widget及其子widget
        包含样式表和调色板设置
        """
        # 应用样式表
        widget.setStyleSheet(Win11DarkStyle.get_base_style())
        
        # 设置全局调色板 (确保系统原生控件也遵循Fluent风格)
        palette = QPalette()
        
        # 基础颜色
        palette.setColor(QPalette.Window, QColor(Win11DarkStyle.BACKGROUND_COLOR))
        palette.setColor(QPalette.WindowText, QColor(Win11DarkStyle.PRIMARY_TEXT))
        palette.setColor(QPalette.Base, QColor(Win11DarkStyle.SECONDARY_BACKGROUND))
        palette.setColor(QPalette.AlternateBase, QColor(Win11DarkStyle.TERTIARY_BACKGROUND))
        
        # 文本颜色
        palette.setColor(QPalette.Text, QColor(Win11DarkStyle.PRIMARY_TEXT))
        palette.setColor(QPalette.PlaceholderText, QColor(Win11DarkStyle.SECONDARY_TEXT))
        palette.setColor(QPalette.BrightText, Qt.white)
        palette.setColor(QPalette.Link, QColor(Win11DarkStyle.ACCENT_COLOR))
        
        # 交互状态
        palette.setColor(QPalette.Highlight, QColor(Win11DarkStyle.ACCENT_COLOR))
        palette.setColor(QPalette.HighlightedText, Qt.white)
        palette.setColor(QPalette.Button, QColor(Win11DarkStyle.PRIMARY_COLOR))
        palette.setColor(QPalette.ButtonText, Qt.white)
        
        # 禁用状态
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(Win11DarkStyle.DISABLED_TEXT))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(Win11DarkStyle.DISABLED_TEXT))
        
        widget.setPalette(palette)