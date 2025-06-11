#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
漫画文本替换模块
专门处理漫画翻译中的文本布局问题，包括垂直到水平的转换、字体适配等
"""

import os
import cv2
import numpy as np
import math
from typing import List, Tuple, Optional, Dict, Any, Union
from PIL import Image, ImageDraw, ImageFont
from dataclasses import dataclass
from enum import Enum

from core.ocr_manager import OCRResult
from core.config import config
from utils import manga_logger as log


class TextDirection(Enum):
    """文本方向枚举"""
    HORIZONTAL = "horizontal"  # 水平排列
    VERTICAL = "vertical"      # 垂直排列
    AUTO = "auto"             # 自动检测


class TextAlignment(Enum):
    """文本对齐方式"""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


@dataclass
class MangaTextReplacement:
    """漫画文本替换信息"""
    original_text: str
    translated_text: str
    bbox: List[List[int]]
    confidence: float
    
    # 文本布局属性
    direction: TextDirection = TextDirection.AUTO
    alignment: TextAlignment = TextAlignment.CENTER
    font_size: int = 20
    line_spacing: float = 1.2  # 行间距倍数
    char_spacing: float = 0.0  # 字符间距（像素）
    column_count: int = 1      # 文本列数
    
    # 视觉属性
    font_color: Tuple[int, int, int] = (0, 0, 0)  # RGB格式，黑字
    background_color: Optional[Tuple[int, int, int]] = None
    stroke_color: Tuple[int, int, int] = (255, 255, 255)  # RGB格式，白边
    stroke_width: int = 2  # 白边宽度
    
    # 适配属性
    max_width: Optional[int] = None
    max_height: Optional[int] = None
    padding: int = 0  # 将内边距改为0


class MangaTextReplacer:
    """漫画文本替换器 - 专门处理漫画翻译中的文本布局问题"""
    
    def __init__(self):
        """初始化漫画文本替换器"""
        self.font_cache = {}  # 字体缓存
        self.font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'font')
        log.info("MangaTextReplacer初始化完成")

    def _get_default_font_path(self) -> str:
        """获取默认字体路径"""
        # 首先尝试从配置获取字体
        font_name = config.font_name.value
        if font_name:
            font_path = os.path.join(self.font_dir, font_name)
            if os.path.exists(font_path):
                log.debug(f"使用配置的字体: {font_path}")
                return font_path
            else:
                log.warning(f"配置的字体不存在: {font_path}")

        # 如果配置的字体不可用，尝试使用系统字体
        # 首先使用项目字体目录中的字体
        system_fonts = []
        if os.path.exists(self.font_dir):
            for f in os.listdir(self.font_dir):
                if f.lower().endswith(('.ttf', '.otf')):
                    system_fonts.append(os.path.join(self.font_dir, f))
        
        # 添加系统字体路径
        system_fonts.extend([
            # Windows系统字体
            "C:/Windows/Fonts/simkai.ttf",    # 楷体
            "C:/Windows/Fonts/simhei.ttf",    # 黑体
            "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
            "C:/Windows/Fonts/simsun.ttc",    # 宋体
            # Linux系统字体
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            # macOS系统字体
            "/System/Library/Fonts/PingFang.ttc"
        ])
        
        for font_path in system_fonts:
            if os.path.exists(font_path):
                log.info(f"使用系统字体: {font_path}")
                return font_path
        
        log.warning("未找到合适的字体文件，将使用PIL默认字体")
        return None
    
    def _get_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """获取字体对象（带缓存）"""
        cache_key = (size, bold)
        if cache_key in self.font_cache:
            return self.font_cache[cache_key]
        
        try:
            font_path = self._get_default_font_path()
            if font_path:
                try:
                    font = ImageFont.truetype(font_path, size)
                    log.debug(f"成功加载字体: {font_path} (大小: {size}px)")
                except Exception as e:
                    log.error(f"加载字体 {font_path} 失败: {e}")
                    font = ImageFont.load_default()
            else:
                font = ImageFont.load_default()
                log.warning("使用PIL默认字体")
            
            self.font_cache[cache_key] = font
            return font
        except Exception as e:
            log.error(f"获取字体时出错: {e}")
            font = ImageFont.load_default()
            self.font_cache[cache_key] = font
            return font
    
    def _detect_text_direction(self, bbox: List[List[int]]) -> TextDirection:
        """检测文本方向"""
        points = np.array(bbox)
        width = np.max(points[:, 0]) - np.min(points[:, 0])
        height = np.max(points[:, 1]) - np.min(points[:, 1])
        
        # 如果高度明显大于宽度，可能是垂直文本
        if height > width * 1.5:
            return TextDirection.VERTICAL
        else:
            return TextDirection.HORIZONTAL
    
    def _is_chinese_text(self, text: str) -> bool:
        """检测是否为中文文本"""
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        return chinese_chars > len(text) * 0.3
    
    def _calculate_optimal_font_size(self, text: str, bbox: List[List[int]], 
                                   direction: TextDirection, 
                                   line_spacing: float = 1.2,
                                   column_count: int = 1) -> int:
        """计算最优字体大小
        
        Args:
            text: 要显示的文本
            bbox: 文本框坐标
            direction: 文本方向
            line_spacing: 行间距倍数
            column_count: 文本框的列数
            
        Returns:
            计算出的最优字体大小
        """
        points = np.array(bbox)
        width = np.max(points[:, 0]) - np.min(points[:, 0])
        height = np.max(points[:, 1]) - np.min(points[:, 1])
        
        # 预留边距
        available_width = width * 0.9
        available_height = height * 0.9
        
        if direction == TextDirection.HORIZONTAL:
            # 水平文本：根据列宽计算
            column_width = available_width / column_count
            # 每列中的平均字符数
            chars_per_column = len(text) / column_count
            # 根据列宽和字符数估算字体大小
            font_size = int(column_width / (chars_per_column * 0.8))  # 0.8是字符宽度比例因子
            
            # 验证高度是否合适
            estimated_lines = max(1, math.ceil(chars_per_column / (column_width / font_size if font_size > 0 else 1)))
            max_font_size_by_height = int(available_height / (estimated_lines * line_spacing))
            
            # 取较小值确保不会溢出
            font_size = min(font_size, max_font_size_by_height)
            
        else:  # 垂直文本
            # 垂直文本：根据列数和总高度计算
            column_width = available_width / column_count
            chars_per_column = math.ceil(len(text) / column_count)  # 向上取整，确保有足够空间
            
            # 先根据高度计算每个字符可用的空间
            font_size = int(available_height / chars_per_column if chars_per_column > 0 else available_height)
            
            # 然后验证列宽是否合适
            max_font_size_by_width = int(column_width * 0.95)  # 留一点边距
            font_size = min(font_size, max_font_size_by_width)
        
        # 确保字体大小在合理范围内
        return max(8, min(font_size, 1000))  # 恢复合理的字体大小范围
    
    def _split_text_to_lines(self, text: str, max_width: int, font_size: int) -> List[str]:
        """将文本分割为多行"""
        if not text.strip():
            return [""]
        
        font = self._get_font(font_size)
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            bbox = font.getbbox(test_line)
            text_width = bbox[2] - bbox[0]
            
            if text_width <= max_width or not current_line:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines if lines else [""]
    
    def _wrap_text_for_box(self, text: str, max_width: int, max_height: int, 
                          font_size: int, line_spacing: float = 1.2) -> Tuple[List[str], int]:
        """为指定区域包装文本"""
        font = self._get_font(font_size)
        
        # 计算行高
        bbox = font.getbbox("测试Ag")
        line_height = int((bbox[3] - bbox[1]) * line_spacing)
        if line_height <= 0: line_height = font_size # Fallback
        max_lines = max(1, max_height // line_height)
        
        # 分割文本
        lines = []
        remaining_text = text
        
        while remaining_text and len(lines) < max_lines:
            # 二分查找最大可容纳的字符数
            left, right = 1, len(remaining_text)
            best_length = 1
            
            while left <= right:
                mid = (left + right) // 2
                test_text = remaining_text[:mid]
                bbox = font.getbbox(test_text)
                text_width = bbox[2] - bbox[0]
                
                if text_width <= max_width:
                    best_length = mid
                    left = mid + 1
                else:
                    right = mid - 1
            
            # 在单词边界处断行（如果可能）
            line_text = remaining_text[:best_length]
            if best_length < len(remaining_text):
                # 尝试在空格处断行
                last_space = line_text.rfind(' ')
                if last_space > best_length * 0.7:  # 如果空格位置合理
                    line_text = remaining_text[:last_space]
                    remaining_text = remaining_text[last_space + 1:]
                else:
                    remaining_text = remaining_text[best_length:]
            else:
                remaining_text = ""
            
            lines.append(line_text.strip())
        
        return lines, line_height
    
    def _split_text_into_columns(self, text: str, column_count: int) -> List[str]:
        """将文本按列数均匀分割
        
        Args:
            text: 要分割的文本
            column_count: 列数
            
        Returns:
            分割后的文本列表
        """
        if column_count <= 1:
            return [text]
            
        # 计算每列的大致字符数
        chars_per_column = math.ceil(len(text) / column_count)
        columns = []
        
        # 分割文本
        for i in range(column_count):
            start = i * chars_per_column
            end = min((i + 1) * chars_per_column, len(text))
            if start < len(text):
                columns.append(text[start:end])
                
        return columns

    def create_manga_replacements(self, ocr_results: List[OCRResult], 
                                translations: Dict[str, str],
                                target_language: str = "zh") -> List[MangaTextReplacement]:
        """
        创建漫画文本替换信息列表
        
        Args:
            ocr_results: OCR识别结果列表 (每个OCRResult代表一个独立的文本块)
            translations: 翻译结果字典 {原文: 译文}
            target_language: 目标语言代码
            
        Returns:
            漫画文本替换信息列表
        """
        replacements = []
        
        for ocr_item in ocr_results:
            original_text = ocr_item.text.strip()
            translated_text = translations.get(original_text)
            
            if not translated_text:
                translated_text = self._find_fuzzy_translation(original_text, translations)
            
            if not translated_text:
                # 如果找不到翻译，可以考虑是否跳过，或者使用原文
                # log.warning(f"未找到原文 '{original_text}' 的翻译，跳过此文本块。")
                continue

            # 确定原始方向
            if ocr_item.direction == 'vertical':
                original_direction = TextDirection.VERTICAL
            elif ocr_item.direction == 'horizontal':
                original_direction = TextDirection.HORIZONTAL
            else: # auto or None
                original_direction = self._detect_text_direction(ocr_item.bbox)

            target_direction = self._determine_target_direction(
                original_text, translated_text, target_language, original_direction
            )
            
            points = np.array(ocr_item.bbox)
            width = np.max(points[:, 0]) - np.min(points[:, 0])
            height = np.max(points[:, 1]) - np.min(points[:, 1])
            
            # column_count 现在基于 ocr_item.ocr_results (如果它是合并的结果)
            column_count = ocr_item.merged_count if ocr_item.merged_count and ocr_item.merged_count > 0 else 1
            
            font_size = self._calculate_optimal_font_size(
                translated_text, ocr_item.bbox, target_direction,
                column_count=column_count
            )
            
            alignment = self._determine_alignment(target_direction, target_language)
            line_spacing, char_spacing = self._calculate_spacing(
                target_direction, target_language, font_size
            )
            
            replacement = MangaTextReplacement(
                original_text=original_text,
                translated_text=translated_text,
                bbox=ocr_item.bbox,
                confidence=ocr_item.confidence,
                direction=target_direction,
                alignment=alignment,
                font_size=font_size,
                line_spacing=line_spacing,
                char_spacing=char_spacing,
                max_width=int(width),
                max_height=int(height),
                column_count=column_count,
                stroke_color=(255, 255, 255),
                stroke_width=2
            )
            replacements.append(replacement)
        
        log.info(f"创建了 {len(replacements)} 个漫画文本替换")
        return replacements
    
    def _find_fuzzy_translation(self, original_text: str, 
                               translations: Dict[str, str]) -> Optional[str]:
        """模糊匹配翻译结果"""
        cleaned_original = ''.join(c for c in original_text if c.isalnum())
        
        for key, value in translations.items():
            cleaned_key = ''.join(c for c in key if c.isalnum())
            if cleaned_original == cleaned_key:
                return value
        
        return None
    
    def _determine_target_direction(self, original_text: str, translated_text: str,
                                  target_language: str,
                                  original_direction: TextDirection) -> TextDirection:
        """确定目标文本方向"""
        # 必须严格保持垂直文本的方向，如果是垂直的就保持垂直
        if original_direction == TextDirection.VERTICAL:
            return TextDirection.VERTICAL
        return TextDirection.HORIZONTAL
    
    def _determine_alignment(self, direction: TextDirection,
                           target_language: str) -> TextAlignment:
        """确定文本对齐方式"""
        if direction == TextDirection.HORIZONTAL:
            # 水平文本通常居中对齐
            return TextAlignment.CENTER
        else:
            # 垂直文本向上对齐
            return TextAlignment.TOP
    
    def _calculate_spacing(self, direction: TextDirection, target_language: str,
                         font_size: int) -> Tuple[float, float]:
        """计算行间距和字符间距"""
        if direction == TextDirection.HORIZONTAL:
            # 水平文本的行间距
            if target_language in ["zh", "zh-cn", "ja", "ko"]:
                line_spacing = 1.2  # 中日韩文字
            else:
                line_spacing = 1.1  # 拉丁文字
            char_spacing = font_size * 0.1  # 字体大小的10%作为字符间距
        else:
            # 垂直文本
            line_spacing = 1.1
            char_spacing = font_size * 0.2  # 字体大小的20%作为字符间距
        
        return line_spacing, char_spacing
    
    def _create_background_mask(self, image: np.ndarray, 
                               bbox: List[List[int]], 
                               expand_pixels: int = 2) -> np.ndarray:
        """创建文本区域的背景遮罩"""
        points = np.array(bbox, dtype=np.int32)
        
        # 扩展遮罩区域
        center = np.mean(points, axis=0)
        expanded_points = []
        for point in points:
            direction_vec = point - center
            length = np.linalg.norm(direction_vec)
            if length > 0:
                direction_vec = direction_vec / length
                expanded_point = point + direction_vec * expand_pixels
                expanded_points.append(expanded_point)
            else:
                expanded_points.append(point)
        
        expanded_points = np.array(expanded_points, dtype=np.int32)
        
        # 创建遮罩
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask, [expanded_points], 255)
        
        return mask
    
    def _inpaint_background(self, image: np.ndarray,
                           bbox: List[List[int]]) -> np.ndarray:
        """直接将文本区域涂白"""
        try:
            # 计算边界框，考虑文本周围留白
            points = np.array(bbox, dtype=np.int32)
            x_coords = points[:, 0]
            y_coords = points[:, 1]
            
            x_min, x_max = np.min(x_coords), np.max(x_coords)
            y_min, y_max = np.min(y_coords), np.max(y_coords)
            
            # 扩展边界以确保完全覆盖
            padding = 2  # 扩展2个像素
            x_min = max(0, x_min - padding)
            y_min = max(0, y_min - padding)
            x_max = min(image.shape[1], x_max + padding)
            y_max = min(image.shape[0], y_max + padding)

            # 创建一个与原始图像相同类型的白色区域
            white_patch = np.full((y_max - y_min, x_max - x_min, image.shape[2]), 
                                  255, dtype=image.dtype)
            
            # 将白色区域复制到图像的指定位置
            inpainted_image = image.copy()
            inpainted_image[y_min:y_max, x_min:x_max] = white_patch
            
            return inpainted_image

        except Exception as e:
            log.error(f"背景涂白失败: {e}", exc_info=True)
            return image.copy() # 返回原始图像副本以避免崩溃

    def _draw_text_with_layout(self, image: np.ndarray, 
                               replacement: MangaTextReplacement) -> np.ndarray:
        """根据布局绘制文本"""
        try:
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(pil_image)
            font = self._get_font(replacement.font_size)
            
            # 文本框的中心点
            points = np.array(replacement.bbox)
            box_center_x = int(np.mean(points[:, 0]))
            box_center_y = int(np.mean(points[:, 1]))
            
            # 文本框的宽度和高度
            box_width = replacement.max_width
            box_height = replacement.max_height

            if replacement.direction == TextDirection.HORIZONTAL:
                self._draw_horizontal_text(
                    draw, replacement, font, 
                    box_center_x, box_center_y, box_width, box_height
                )
            else: # VERTICAL
                self._draw_vertical_text(
                    draw, replacement, font,
                    box_center_x, box_center_y, box_width, box_height
                )

            return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        except Exception as e:
            log.error(f"绘制文本时出错: {e}", exc_info=True)
            return image # 返回原始图像

    def _draw_horizontal_text(self, draw: ImageDraw.Draw, 
                              replacement: MangaTextReplacement, 
                              font: ImageFont.FreeTypeFont,
                              box_center_x: int, box_center_y: int,
                              box_width: int, box_height: int):
        """绘制水平文本"""
        # 分割文本为多行
        lines, line_height = self._wrap_text_for_box(
            replacement.translated_text, 
            box_width - 2 * replacement.padding, 
            box_height - 2 * replacement.padding,
            replacement.font_size, 
            replacement.line_spacing
        )
        
        total_text_height = len(lines) * line_height - (line_height * (1 - replacement.line_spacing) if len(lines) > 1 else 0)
        
        # 计算起始Y坐标
        if replacement.alignment == TextAlignment.TOP:
            current_y = box_center_y - box_height // 2 + replacement.padding
        elif replacement.alignment == TextAlignment.BOTTOM:
            current_y = box_center_y + box_height // 2 - total_text_height - replacement.padding
        else: # CENTER
            current_y = box_center_y - total_text_height // 2
            
        for line in lines:
            bbox = font.getbbox(line)
            text_width = bbox[2] - bbox[0]
            
            # 计算起始X坐标
            if replacement.alignment == TextAlignment.LEFT:
                current_x = box_center_x - box_width // 2 + replacement.padding
            elif replacement.alignment == TextAlignment.RIGHT:
                current_x = box_center_x + box_width // 2 - text_width - replacement.padding
            else: # CENTER
                current_x = box_center_x - text_width // 2
            
            # 绘制描边
            if replacement.stroke_width > 0 and replacement.stroke_color:
                for dx in range(-replacement.stroke_width, replacement.stroke_width + 1):
                    for dy in range(-replacement.stroke_width, replacement.stroke_width + 1):
                        if dx != 0 or dy != 0: # 不在中心点绘制
                            draw.text((current_x + dx, current_y + dy), line, 
                                      font=font, fill=replacement.stroke_color)
            # 绘制文本
            draw.text((current_x, current_y), line, font=font, fill=replacement.font_color)
            current_y += line_height

    def _convert_ellipsis_for_vertical(self, text: str) -> str:
        """将水平省略号转换为垂直省略号"""
        text = text.replace("...", "︙")
        text = text.replace("…", "︙")
        return text

    def _draw_vertical_text(self, draw: ImageDraw.Draw,
                            replacement: MangaTextReplacement,
                            font: ImageFont.FreeTypeFont,
                            box_center_x: int, box_center_y: int,
                            box_width: int, box_height: int):
        """绘制垂直文本"""
        text_to_draw = self._convert_ellipsis_for_vertical(replacement.translated_text)
        
        # 计算每列的宽度
        column_width = (box_width - 2 * replacement.padding) / replacement.column_count
        
        # 分割文本到列
        columns_text = self._split_text_into_columns(text_to_draw, replacement.column_count)
        
        # 计算字符高度和宽度 (估算)
        # 使用 "M" 作为典型字符估算宽度，"中" 作为典型字符估算高度
        char_bbox_m = font.getbbox("M")
        char_width_m = char_bbox_m[2] - char_bbox_m[0]
        char_bbox_zh = font.getbbox("中")
        char_height_zh = char_bbox_zh[3] - char_bbox_zh[1]
        
        # 使用较大的值作为字符尺寸的基准，并考虑行间距
        char_render_height = int(char_height_zh * replacement.line_spacing)
        char_render_width = int(char_width_m * replacement.line_spacing) # 垂直时，列间距也用line_spacing

        # 获取系统默认字体（用于特殊字符）
        default_font = ImageFont.load_default()
        
        # 确定起始X坐标 (最右列的中心)
        start_x = box_center_x + (box_width // 2) - (column_width // 2) - replacement.padding
        
        for i, column_text in enumerate(columns_text):
            # 从右向左计算每列的X坐标
            current_x_col = start_x - i * column_width
            
            # 计算该列文本的总高度
            total_col_height = len(column_text) * char_render_height - char_render_height * (1-replacement.line_spacing) if len(column_text) > 1 else 0

            # 确定起始Y坐标
            if replacement.alignment == TextAlignment.TOP:
                current_y = box_center_y - box_height // 2 + replacement.padding
            elif replacement.alignment == TextAlignment.BOTTOM:
                current_y = box_center_y + box_height // 2 - total_col_height - replacement.padding
            else: # MIDDLE (for vertical, often same as TOP or slightly adjusted)
                current_y = box_center_y - total_col_height // 2
            
            for char_index, char_text in enumerate(column_text):
                # 获取单个字符的边界框以精确居中
                current_font = default_font if char_text == "⋮" else font
                char_bbox = current_font.getbbox(char_text)
                single_char_width = char_bbox[2] - char_bbox[0]
                
                # 计算字符的绘制位置 (X居中于列，Y递增)
                char_x = current_x_col - single_char_width // 2
                char_y = current_y + char_index * char_render_height
                
                # 绘制描边
                if replacement.stroke_width > 0 and replacement.stroke_color:
                    for dx in range(-replacement.stroke_width, replacement.stroke_width + 1):
                        for dy in range(-replacement.stroke_width, replacement.stroke_width + 1):
                            if dx != 0 or dy != 0:
                                draw.text((char_x + dx, char_y + dy), char_text,
                                          font=current_font, fill=replacement.stroke_color)
                # 绘制字符
                draw.text((char_x, char_y), char_text, font=current_font, fill=replacement.font_color)

    def replace_manga_text(self, image: np.ndarray,
                           replacements: List[MangaTextReplacement],
                           inpaint_background: bool = True) -> np.ndarray:
        """
        在图像上执行漫画文本替换
        
        Args:
            image: 原始图像
            replacements: 漫画文本替换信息列表
            inpaint_background: 是否修复背景
            
        Returns:
            处理后的图像
        """
        processed_image = image.copy()
        
        for replacement in replacements:
            if inpaint_background:
                # 修复背景（例如，使用内容感知填充或简单的颜色填充）
                processed_image = self._inpaint_background(processed_image, replacement.bbox)
            
            # 绘制文本
            processed_image = self._draw_text_with_layout(processed_image, replacement)
            
        return processed_image

    def process_manga_image(self, image: np.ndarray, 
                            structured_texts: List[OCRResult], # 修改类型注解
                            translations: Dict[str, str],
                            target_language: str = "zh",
                            inpaint_background: bool = True) -> np.ndarray:
        """
        处理漫画图像：基于结构化文本的翻译和智能文本替换
        
        Args:
            image: 原始图像数据
            structured_texts: OCR识别结果列表 (每个OCRResult代表一个独立的文本块)
            translations: 翻译结果字典 {原文: 译文}
            target_language: 目标语言代码
            inpaint_background: 是否修复背景
            
        Returns:
            处理后的图像
        """
        # 直接使用 create_manga_replacements 来生成替换列表
        replacements = self.create_manga_replacements(
            ocr_results=structured_texts, 
            translations=translations, 
            target_language=target_language
        )
        
        if not replacements:
            log.warning("在 process_manga_image 中没有生成可替换的漫画文本")
            return image.copy()
        
        # 执行漫画文本替换
        result_image = self.replace_manga_text(
            image, replacements, inpaint_background
        )
        
        return result_image

    def save_result_image(self, image: np.ndarray, output_path: str) -> bool:
        """保存处理结果图像"""
        try:
            cv2.imwrite(output_path, image)
            log.info(f"结果图像已保存到: {output_path}")
            return True
        except Exception as e:
            log.error(f"保存图像失败: {e}", exc_info=True)
            return False