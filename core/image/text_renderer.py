# file: core/image/text_renderer.py
"""
智能文本渲染器
===============

本模块提供高级的文本绘制功能，旨在将文本智能地布局在给定的矩形框内。
它支持：
- 水平与垂直排版
- 自动计算最佳字体大小
- 自动换行与换列
- 文本在框内的居中对齐
"""
import logging
from PIL import ImageDraw, ImageFont
from math import floor, ceil

def draw_text_intelligently(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple,
    direction: str,
    font_path: str,
    padding: int = 5
):
    """
    在给定的框内智能地绘制文本。

    Args:
        draw: Pillow ImageDraw 对象。
        text: 要绘制的文本。
        box: 包含 (x_min, y_min, x_max, y_max) 的元组。
        direction: 'horizontal' 或 'vertical'。
        font_path: 字体文件的路径。
        padding: 文本框的内边距。
    """
    if not text:
        return

    # 应用内边距
    box_x_min, box_y_min, box_x_max, box_y_max = box
    box_width = box_x_max - box_x_min - padding * 2
    box_height = box_y_max - box_y_min - padding * 2

    if box_width <= 0 or box_height <= 0:
        return

    # 阶段一: 寻找最佳字号
    best_font_size, best_params = _find_best_font_size(text, box_width, box_height, direction, font_path)

    if not best_font_size:
        logging.warning(f"无法为文本 '{text[:10]}...' 在给定的框内找到合适的字体大小。")
        return

    # 阶段二: 布局与绘制
    _layout_and_draw(
        draw=draw,
        text=text,
        box=(box_x_min + padding, box_y_min + padding, box_x_max - padding, box_y_max - padding),
        direction=direction,
        font_path=font_path,
        font_size=best_font_size,
        params=best_params
    )

def _find_best_font_size(text, box_width, box_height, direction, font_path):
    """使用迭代法寻找最佳字体大小。"""

    # 理论上的最大可能字号
    try:
        initial_font_size = int((box_width * box_height / len(text))**0.5)
    except ZeroDivisionError:
        return None, None

    min_font_size = 8 # 最小字号

    for size in range(initial_font_size, min_font_size - 1, -1):
        try:
            ImageFont.truetype(font_path, size=size)
        except IOError:
            logging.error(f"无法加载字体: {font_path}。将使用默认字体。")
            ImageFont.load_default()

        line_spacing = size * 0.3 # 估算行间距

        if direction == 'horizontal':
            chars_per_line = floor(box_width / size) if size > 0 else 0
            if chars_per_line == 0:
                continue

            num_lines = ceil(len(text) / chars_per_line)
            total_text_height = num_lines * size + (num_lines - 1) * line_spacing

            if total_text_height <= box_height:
                return size, {'lines': num_lines, 'chars_per_line': chars_per_line}

        elif direction == 'vertical':
            chars_per_col = floor(box_height / size) if size > 0 else 0
            if chars_per_col == 0:
                continue

            num_cols = ceil(len(text) / chars_per_col)
            total_text_width = num_cols * size + (num_cols - 1) * line_spacing # 这里用 line_spacing 代表列间距

            if total_text_width <= box_width:
                return size, {'cols': num_cols, 'chars_per_col': chars_per_col}

    return None, None # 未找到合适的尺寸


def _layout_and_draw(draw, text, box, direction, font_path, font_size, params):
    """根据计算好的参数，在框内布局并绘制文本。"""
    try:
        font = ImageFont.truetype(font_path, size=font_size)
    except IOError:
        font = ImageFont.load_default()

    box_x_min, box_y_min, box_x_max, box_y_max = box
    box_width = box_x_max - box_x_min
    box_height = box_y_max - box_y_min

    line_spacing_ratio = 0.3 # 行/列间距是字号的30%

    if direction == 'horizontal':
        lines = []
        chars_per_line = params['chars_per_line']
        for i in range(0, len(text), chars_per_line):
            lines.append(text[i:i+chars_per_line])

        num_lines = len(lines)
        line_height = font_size * (1 + line_spacing_ratio)
        total_text_height = (num_lines - 1) * line_height + font_size

        start_y = box_y_min + (box_height - total_text_height) / 2

        for i, line in enumerate(lines):
            # 使用 getbbox 获取精确的文本宽度以实现更好的居中
            try:
                line_bbox = draw.textbbox((0,0), line, font=font)
                line_width = line_bbox[2] - line_bbox[0]
            except AttributeError: # 兼容旧版 Pillow
                line_width = draw.textlength(line, font=font)

            start_x = box_x_min + (box_width - line_width) / 2
            current_y = start_y + i * line_height
            draw.text((start_x, current_y), line, font=font, fill='black')

    elif direction == 'vertical':
        cols = []
        chars_per_col = params['chars_per_col']
        for i in range(0, len(text), chars_per_col):
            cols.append(text[i:i+chars_per_col])

        num_cols = len(cols)
        col_width = font_size * (1 + line_spacing_ratio)
        total_text_width = (num_cols - 1) * col_width + font_size

        start_x = box_x_max - (box_width - total_text_width) / 2 - font_size # 从右侧开始

        for i, col in enumerate(cols):
            col_height = len(col) * font_size
            start_y = box_y_min + (box_height - col_height) / 2
            current_x = start_x - i * col_width

            for j, char in enumerate(col):
                current_y = start_y + j * font_size
                draw.text((current_x, current_y), char, font=font, fill='black')