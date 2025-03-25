from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
from styles.win_theme_color import get_system_theme_colors

class Win11LightStyle:
    # 获取系统主题色，如果获取失败则使用默认的Win11蓝色主题
    PRIMARY_COLOR, ACCENT_COLOR = get_system_theme_colors()
    BACKGROUND_COLOR = "#FFFFFF"  # 背景色
    TEXT_COLOR = "#202020"  # 文本色
    BORDER_COLOR = "#E5E5E5"  # 边框色
    HOVER_COLOR = "#F5F5F5"  # 悬停色
    
    # 标题栏颜色
    TITLE_BAR_COLOR = "#FFFFFF"  # 标题栏背景色
    TITLE_BAR_HOVER_COLOR = "#F5F5F5"  # 标题栏按钮悬停色
    TITLE_BAR_ACTIVE_COLOR = "#E5E5E5"  # 标题栏按钮激活色
    
    # 字体设置
    FONT_FAMILY = "Segoe UI"
    FONT_SIZE = 9
    
    # 圆角半径
    BORDER_RADIUS = 4
    
    # 间距
    SPACING = 8
    MARGIN = 10
    
    @staticmethod
    def get_base_style():
        return f"""
        QMainWindow {{            
            background-color: {Win11LightStyle.BACKGROUND_COLOR};
            border: none;
        }}
        
        QWidget {{            
            background-color: {Win11LightStyle.BACKGROUND_COLOR};
            color: {Win11LightStyle.TEXT_COLOR};
            font-family: "{Win11LightStyle.FONT_FAMILY}";
            font-size: {Win11LightStyle.FONT_SIZE}pt;
        }}
        
        QPushButton {{            
            background-color: {Win11LightStyle.PRIMARY_COLOR};
            color: white;
            border: none;
            border-radius: {Win11LightStyle.BORDER_RADIUS}px;
            padding: 6px 12px;
            min-width: 80px;
        }}
        
        QPushButton:hover {{            
            background-color: {Win11LightStyle.ACCENT_COLOR};
        }}
        
        QLineEdit {{            
            background-color: white;
            border: 1px solid {Win11LightStyle.BORDER_COLOR};
            border-radius: {Win11LightStyle.BORDER_RADIUS}px;
            padding: 4px 8px;
        }}
        
        QScrollArea {{            
            border: none;
            background-color: transparent;
        }}
        
        QScrollBar:vertical {{            
            border: none;
            background-color: #F0F0F0;
            width: 8px;
            border-radius: 4px;
        }}
        
        QScrollBar::handle:vertical {{            
            background-color: #C4C4C4;
            border-radius: 4px;
        }}
        
        QTreeView {{            
            border: 1px solid {Win11LightStyle.BORDER_COLOR};
            border-radius: {Win11LightStyle.BORDER_RADIUS}px;
            background-color: white;
        }}
        
        QTreeView::item {{            
            padding: 4px;
        }}
        
        QTreeView::item:selected {{            
            background-color: {Win11LightStyle.PRIMARY_COLOR};
            color: white;
        }}
        
        QSlider::groove:horizontal {{            
            border: none;
            height: 4px;
            background-color: #D4D4D4;
            border-radius: 2px;
        }}
        
        QSlider::handle:horizontal {{            
            background-color: {Win11LightStyle.PRIMARY_COLOR};
            border: none;
            width: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }}
        """
    
    @staticmethod
    def apply_style(widget):
        widget.setStyleSheet(Win11LightStyle.get_base_style())
        
        # 设置全局调色板
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(Win11LightStyle.BACKGROUND_COLOR))
        palette.setColor(QPalette.WindowText, QColor(Win11LightStyle.TEXT_COLOR))
        palette.setColor(QPalette.Base, QColor("white"))
        palette.setColor(QPalette.AlternateBase, QColor(Win11LightStyle.BACKGROUND_COLOR))
        palette.setColor(QPalette.ToolTipBase, QColor("white"))
        palette.setColor(QPalette.ToolTipText, QColor(Win11LightStyle.TEXT_COLOR))
        palette.setColor(QPalette.Text, QColor(Win11LightStyle.TEXT_COLOR))
        palette.setColor(QPalette.Button, QColor(Win11LightStyle.PRIMARY_COLOR))
        palette.setColor(QPalette.ButtonText, QColor("white"))
        palette.setColor(QPalette.Highlight, QColor(Win11LightStyle.PRIMARY_COLOR))
        palette.setColor(QPalette.HighlightedText, QColor("white"))
        
        widget.setPalette(palette)