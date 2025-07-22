# file: core/image/contextual_grid.py
"""
上下文校准网格生成器
=====================

本模块负责在给定的图片上绘制一个视觉坐标系，
以便为 AI 模型提供一个清晰、无歧义的坐标参照物。
"""
from PIL import Image, ImageDraw, ImageFont
import logging

def draw_calibration_grid(
    image: Image.Image,
    grid_interval: int = 100,
    line_color: tuple = (0, 0, 255, 128), # 蓝色半透明
    font_color: tuple = (0, 0, 255, 255), # 蓝色不透明
    font_path: str = "font/SourceHanSansCN-Heavy.otf"
) -> Image.Image:
    """
    在图片上绘制一个半透明的校准网格和坐标标签。

    Args:
        image: Pillow Image 对象 (应为 RGBA 模式以支持透明度)。
        grid_interval: 网格线的间距（像素）。
        line_color: 网格线的 RGBA 颜色。
        font_path: 用于绘制坐标标签的字体路径。

    Returns:
        一个新的 Pillow Image 对象，带有绘制好的网格。
    """
    # 创建一个可绘制的副本
    img_with_grid = image.copy()
    draw = ImageDraw.Draw(img_with_grid)
    width, height = img_with_grid.size

    # 加载字体
    try:
        font = ImageFont.truetype(font_path, size=16) # 增大字号
    except IOError:
        logging.warning(f"无法加载字体 {font_path}，将使用默认字体。")
        font = ImageFont.load_default()

    # 绘制垂直线和坐标
    for x in range(0, width, grid_interval):
        # 绘制虚线
        for y in range(0, height, 10):
            if y % 20 < 10:
                draw.line([(x, y), (x, y + 10)], fill=line_color, width=2)
        # 在顶部绘制坐标标签
        draw.text((x + 2, 2), str(x), fill=font_color, font=font)

    # 绘制水平线和坐标
    for y in range(0, height, grid_interval):
        # 绘制虚线
        for x in range(0, width, 10):
            if x % 20 < 10:
                draw.line([(x, y), (x + 10, y)], fill=line_color, width=2)
        # 在左侧绘制坐标标签
        if y > 0: # 避免与 (0,0) 的标签重叠
            draw.text((2, y + 2), str(y), fill=font_color, font=font)
            
    logging.info(f"已在 {width}x{height} 的图片上绘制校准网格。")
    return img_with_grid