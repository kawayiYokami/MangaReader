from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from styles.style import Win11Style
from styles.light_style import Win11LightStyle
from styles.dark_style import Win11DarkStyle

class UIStyle:
    """
    UI组件样式管理类
    用于集中管理所有UI组件的样式，避免在各个组件中硬编码样式
    支持动态切换主题
    """
    
    @staticmethod
    def get_title_bar_button_style(is_close=False, style_class=Win11Style):
        """
        获取标题栏按钮样式
        Args:
            is_close: 是否为关闭按钮
            style_class: 样式类，默认为Win11Style
        """
        hover_color = "#C42B1C" if is_close else style_class.TITLE_BAR_HOVER_COLOR
        active_color = "#C42B1C" if is_close else style_class.TITLE_BAR_ACTIVE_COLOR
        hover_text_color = "white" if is_close else style_class.TEXT_COLOR
        text_color = style_class.TEXT_COLOR
        
        return f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 0;
                padding: 0;
                margin: 0;
                color: {text_color};
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                color: {hover_text_color};
            }}
            QPushButton:pressed {{
                background-color: {active_color};
            }}
        """
    
    @staticmethod
    def get_title_bar_select_dir_button_style(style_class=Win11Style):
        """
        获取标题栏文件夹选择按钮样式
        Args:
            style_class: 样式类，默认为Win11Style
        """
        return f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: {style_class.BORDER_RADIUS}px;
                padding: 4px;
                color: {style_class.TEXT_COLOR};
            }}
            QPushButton:hover {{
                background-color: {style_class.TITLE_BAR_HOVER_COLOR};
            }}
            QPushButton:pressed {{
                background-color: {style_class.TITLE_BAR_ACTIVE_COLOR};
            }}
        """
    
    @staticmethod
    def get_title_bar_search_input_style(style_class=Win11Style):
        """
        获取标题栏搜索输入框样式
        Args:
            style_class: 样式类，默认为Win11Style
        """
        return f"""
            QLineEdit {{
                background-color: {style_class.BACKGROUND_COLOR};
                border: 1px solid {style_class.BORDER_COLOR};
                border-radius: {style_class.BORDER_RADIUS}px;
                padding: 4px 8px;
                color: {style_class.TEXT_COLOR};
            }}
        """
    
    @staticmethod
    def get_navigation_widget_style(opacity=100, style_class=Win11Style):
        """
        获取导航控件样式
        Args:
            opacity: 透明度 (0-100)
            style_class: 样式类，默认为Win11Style
        """
        return f"""
            QWidget {{
                background-color: rgba(200, 200, 200, {opacity/100*0.6});
                border-radius: {style_class.BORDER_RADIUS}px;
            }}
            QPushButton, QCheckBox {{
                opacity: {opacity/100};
            }}
        """
    
    @staticmethod
    def get_vertical_zoom_slider_style(opacity=100, style_class=Win11Style):
        """
        获取垂直缩放滑动条样式
        Args:
            opacity: 透明度 (0-100)
            style_class: 样式类，默认为Win11Style
        """
        # 基础透明度计算 (0-100 => 0.0-1.0)
        alpha = opacity / 100.0
        
        # Fluent风格颜色
        bg_color = f"rgba(243, 243, 243, {0.0*alpha})"  # 背景轻微透明
        groove_color = f"rgba(200, 200, 200, {0.6*alpha})"  # 轨道颜色
        handle_color = f"rgba(0, 120, 215, {alpha})"  # Win11蓝色手柄
        
        return f"""
            VerticalZoomSlider {{
                background-color: {bg_color};
                border-radius: {style_class.BORDER_RADIUS}px;
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
        """