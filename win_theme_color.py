import winreg
from typing import Optional, Tuple

def get_system_accent_color() -> Optional[str]:
    """
    获取Windows系统的主题色
    返回格式为"#RRGGBB"的十六进制颜色字符串，如果获取失败则返回None
    """
    try:
        # 打开注册表键
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Accent"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            # 读取AccentColorMenu值
            accent_color = winreg.QueryValueEx(key, "AccentColorMenu")[0]
            
            # 将ABGR格式转换为RGB格式
            # Windows存储格式为ABGR (Alpha, Blue, Green, Red)
            a = (accent_color >> 24) & 0xFF
            b = (accent_color >> 16) & 0xFF
            g = (accent_color >> 8) & 0xFF
            r = accent_color & 0xFF
            
            # 返回十六进制格式的RGB颜色
            return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return None

def get_system_theme_colors() -> Tuple[str, str]:
    """
    获取系统主题色，返回主色和强调色
    如果无法获取系统主题色，则返回默认的蓝色主题
    返回值: (primary_color, accent_color)
    """
    # 默认的Windows蓝色主题
    DEFAULT_PRIMARY = "#0078D4"
    DEFAULT_ACCENT = "#60CDFF"
    
    # 尝试获取系统主题色
    primary_color = get_system_accent_color()
    if primary_color is None:
        return DEFAULT_PRIMARY, DEFAULT_ACCENT
        
    # 根据主色生成强调色
    # 这里简单处理：将主色调亮40%作为强调色
    def adjust_color(hex_color: str, factor: float) -> str:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    accent_color = adjust_color(primary_color, 0.4)
    return primary_color, accent_color