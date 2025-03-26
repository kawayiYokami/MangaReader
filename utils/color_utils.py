from typing import Optional
import re

def get_rgba_string(color_string: str, alpha: float) -> str:
    """
    将颜色字符串和透明度转换为 rgba 字符串。

    Args:
        color_string (str): 可以是十六进制颜色码 (如 "#RRGGBB") 或 RGB 字符串 (如 "rgb(r, g, b)")。
        alpha (float): 透明度值，范围为 0.0 到 1.0。

    Returns:
        str: rgba 格式的颜色字符串。如果解析失败，则返回默认的蓝色 rgba 字符串。
    """
    alpha_int = int(alpha * 255)

    if color_string.startswith("#"):
        hex_color = color_string.lstrip("#")
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"rgba({r}, {g}, {b}, {alpha_int})"
    elif color_string.startswith("rgb("):
        match = re.search(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", color_string)
        if match:
            r, g, b = map(int, match.groups())
            return f"rgba({r}, {g}, {b}, {alpha_int})"

    # 默认返回蓝色
    return f"rgba(0, 120, 215, {alpha_int})"