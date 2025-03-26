from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
from styles.win_theme_color import get_system_theme_colors
import winreg
from typing import Literal

def get_system_theme() -> Literal['light', 'dark']:
    """获取Windows系统当前的主题模式"""
    try:
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            value = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
            return 'light' if value == 1 else 'dark'
    except Exception:
        return 'light'  # 默认返回浅色主题

class Win11Style:
    """Windows 11 Fluent Design 基础样式配置
    包含字体系统、形状系统、间距系统和动画效果参数等共同部分
    """
    
    # ====================== 字体系统 ======================
    FONT_FAMILY = "Segoe UI Variable"  # Win11新默认字体 (支持动态调整)
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

# 根据系统主题导入对应的样式
if get_system_theme() == 'light':
    from styles.light_style import Win11LightStyle as Win11Style
else:
    from styles.dark_style import Win11DarkStyle as Win11Style