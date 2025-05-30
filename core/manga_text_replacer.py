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
    padding: int = 2  # 内边距


class MangaTextReplacer:
    """漫画文本替换器 - 专门处理漫画翻译中的文本布局问题"""
    
    def __init__(self):
        """初始化漫画文本替换器"""
        self.default_font_path = self._get_default_font_path()
        self.font_cache = {}  # 字体缓存
        log.info("MangaTextReplacer初始化完成")
    
    def _get_default_font_path(self) -> str:
        """获取默认字体路径"""
        font_paths = [
            # Windows系统字体 - 优先选择适合漫画的字体
            "C:/Windows/Fonts/simkai.ttf",  # 楷体
            "C:/Windows/Fonts/simhei.ttf",    # 黑体
            "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
            "C:/Windows/Fonts/simsun.ttc",    # 宋体
            "C:/Windows/Fonts/arial.ttf",     # Arial
            "C:/Windows/Fonts/calibri.ttf",   # Calibri
            # 项目内置字体
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "OnnxOCR", "onnxocr", "fonts", "simfang.ttf"),
            # Linux系统字体
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            # macOS系统字体
            "/System/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/PingFang.ttc"
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                log.info(f"使用字体: {font_path}")
                return font_path
        
        log.warning("未找到合适的字体文件，将使用PIL默认字体")
        return None
    
    def _get_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """获取字体对象（带缓存）"""
        cache_key = (size, bold)
        if cache_key in self.font_cache:
            return self.font_cache[cache_key]
        
        try:
            if self.default_font_path:
                font = ImageFont.truetype(self.default_font_path, size)
            else:
                font = ImageFont.load_default()
            
            self.font_cache[cache_key] = font
            return font
        except Exception as e:
            log.warning(f"加载字体失败: {e}")
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
            estimated_lines = max(1, math.ceil(chars_per_column / (column_width / font_size)))
            max_font_size_by_height = int(available_height / (estimated_lines * line_spacing))
            
            # 取较小值确保不会溢出
            font_size = min(font_size, max_font_size_by_height)
            
        else:  # 垂直文本
            # 垂直文本：根据列数和总高度计算
            column_width = available_width / column_count
            chars_per_column = math.ceil(len(text) / column_count)  # 向上取整，确保有足够空间
            
            # 先根据高度计算每个字符可用的空间
            font_size = int(available_height / chars_per_column)
            
            # 然后验证列宽是否合适
            max_font_size_by_width = int(column_width * 0.95)  # 留一点边距
            font_size = min(font_size, max_font_size_by_width)
            
            print(f"   📏 垂直文本字体计算:")
            print(f"      总宽度: {width}px, 列数: {column_count}")
            print(f"      每列宽度: {column_width}px")
            print(f"      总字符数: {len(text)}, 每列字符数: {chars_per_column}")
            print(f"      计算字体大小: {font_size}px")
        
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
            ocr_results: OCR识别结果列表
            translations: 翻译结果字典 {原文: 译文}
            target_language: 目标语言代码
            
        Returns:
            漫画文本替换信息列表
        """
        replacements = []
        
        # 1. 收集所有文本框信息
        text_boxes = {}  # 用于存储合并的文本框信息 {box_id: {bbox, texts, results}}
        
        for ocr_result in ocr_results:
            bbox_key = tuple(map(tuple, ocr_result.bbox))  # 将bbox转换为可哈希的类型
            if bbox_key not in text_boxes:
                text_boxes[bbox_key] = {
                    'bbox': ocr_result.bbox,
                    'texts': [ocr_result.text.strip()],
                    'results': [ocr_result],
                    'confidence': [ocr_result.confidence]
                }
            else:
                text_boxes[bbox_key]['texts'].append(ocr_result.text.strip())
                text_boxes[bbox_key]['results'].append(ocr_result)
                text_boxes[bbox_key]['confidence'].append(ocr_result.confidence)
        
        # 2. 为每个文本框创建替换信息
        for box_key, box_info in text_boxes.items():
            # 合并原始文本
            original_text = '\n'.join(box_info['texts'])
            
            # 查找对应的翻译
            translated_text = translations.get(original_text)
            if not translated_text:
                translated_text = self._find_fuzzy_translation(original_text, translations)
            
            # 只要找到了翻译就创建替换，无论是否与原文相同
            if translated_text:
                # 检测原文本方向
                original_direction = self._detect_text_direction(box_info['bbox'])
                
                # 确定目标文本方向
                target_direction = self._determine_target_direction(
                    original_text, translated_text, target_language, original_direction
                )
                
                # 计算边界框尺寸
                points = np.array(box_info['bbox'])
                width = np.max(points[:, 0]) - np.min(points[:, 0])
                height = np.max(points[:, 1]) - np.min(points[:, 1])
                
                # 根据原始OCR结果数量确定列数
                first_result = box_info['results'][0]
                column_count = len(first_result.ocr_results)
                
                # 计算最优字体大小
                font_size = self._calculate_optimal_font_size(
                    translated_text, box_info['bbox'], target_direction,
                    column_count=column_count
                )
                
                # 确定对齐方式
                alignment = self._determine_alignment(target_direction, target_language)
                
                # 计算行间距和字符间距
                line_spacing, char_spacing = self._calculate_spacing(
                    target_direction, target_language, font_size
                )
                
                # 计算平均置信度
                avg_confidence = sum(box_info['confidence']) / len(box_info['confidence'])
                
                replacement = MangaTextReplacement(
                    original_text=original_text,
                    translated_text=translated_text,
                    bbox=box_info['bbox'],
                    confidence=avg_confidence,
                    direction=target_direction,
                    alignment=alignment,
                    font_size=font_size,
                    line_spacing=line_spacing,
                    char_spacing=char_spacing,
                    max_width=int(width * 0.9),
                    max_height=int(height * 0.9),
                    column_count=column_count,  # 使用OCR结果数量作为列数
                    stroke_color=(255, 255, 255),  # 白边
                    stroke_width=2  # 白边宽度
                )
                
                replacements.append(replacement)
                
                # 详细的调试输出
                print(f"\n📝 创建漫画文本替换 #{len(replacements)}")
                print(f"   原文: '{original_text}' ({len(original_text)} 字符)")
                print(f"   译文: '{translated_text}' ({len(translated_text)} 字符)")
                print(f"   文本方向: {original_direction.value} -> {target_direction.value}")
                print(f"   文本框尺寸: {width}x{height} 像素")
                print(f"   列数: {column_count}")
                print(f"   字体大小: {font_size}px")
                print(f"   行间距: {line_spacing}, 字符间距: {char_spacing}px")
                print(f"   对齐方式: {alignment.value}")
                print(f"   最大尺寸: {replacement.max_width}x{replacement.max_height}")
                print(f"   字体颜色: 黑色 {replacement.font_color}")
                print(f"   描边颜色: 白色 {replacement.stroke_color}, 宽度: {replacement.stroke_width}px")
                
                log.debug(f"创建漫画替换: '{original_text}' -> '{translated_text}' "
                         f"({original_direction.value} -> {target_direction.value})")
        
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
        # 漫画文本强制使用垂直排列，这是漫画的传统排版方式
        # 无论原文是什么方向，译文都使用垂直排列
        return TextDirection.VERTICAL
    
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
                line_spacing = 1.3  # 中日韩文字需要更大的行间距
            else:
                line_spacing = 1.2  # 拉丁文字
            char_spacing = 0.0
        else:
            # 垂直文本 - 减少字符间距避免视觉空格
            line_spacing = 1.1
            char_spacing = font_size * 0.05  # 减少字符间距
        
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
            direction = point - center
            length = np.linalg.norm(direction)
            if length > 0:
                direction = direction / length
                expanded_point = point + direction * expand_pixels
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
            points = np.array(bbox)
            x_min, y_min = np.min(points, axis=0)
            x_max, y_max = np.max(points, axis=0)
            
            # 添加额外的边距（根据文本框大小动态调整）
            padding = min((x_max - x_min), (y_max - y_min)) * 0  # 使用10%的边距
            x_min = x_min - padding
            y_min = y_min - padding
            x_max = x_max + padding
            y_max = y_max + padding
            
            # 确保坐标在图像范围内
            x_min = max(0, int(x_min))
            y_min = max(0, int(y_min))
            x_max = min(image.shape[1], int(x_max))
            y_max = min(image.shape[0], int(y_max))
            
            print(f"   🎨 涂白区域: ({x_min}, {y_min}) 到 ({x_max}, {y_max})")
            
            # 直接将文本区域涂白
            result = image.copy()
            result[y_min:y_max, x_min:x_max] = [255, 255, 255]  # 白色
            
            return result
            
        except Exception as e:
            log.warning(f"背景涂白失败: {e}")
            return image.copy()
    
    def _draw_text_with_layout(self, image: np.ndarray, 
                             replacement: MangaTextReplacement) -> np.ndarray:
        """根据布局绘制文本"""
        try:
            # 转换为PIL图像
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(pil_image)
            
            # 获取字体
            font = self._get_font(replacement.font_size)
            
            # 计算文本区域
            points = np.array(replacement.bbox)
            x_min, y_min = np.min(points, axis=0)
            x_max, y_max = np.max(points, axis=0)
            
            available_width = x_max - x_min - 2 * replacement.padding
            available_height = y_max - y_min - 2 * replacement.padding
            
            if replacement.direction == TextDirection.HORIZONTAL:
                self._draw_horizontal_text(
                    draw, replacement, font,
                    x_min + replacement.padding, y_min + replacement.padding,
                    available_width, available_height
                )
            else:
                self._draw_vertical_text(
                    draw, replacement, font,
                    x_min + replacement.padding, y_min + replacement.padding,
                    available_width, available_height
                )
            
            # 转换回OpenCV格式
            result_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            return result_image
            
        except Exception as e:
            log.error(f"绘制文本失败: {e}")
            return image
    
    def _draw_horizontal_text(self, draw: ImageDraw.Draw, 
                            replacement: MangaTextReplacement,
                            font: ImageFont.FreeTypeFont,
                            x: int, y: int, max_width: int, max_height: int) -> None:
        """绘制水平文本"""
        # 分割文本为多行
        lines, line_height = self._wrap_text_for_box(
            replacement.translated_text, max_width, max_height,
            replacement.font_size, replacement.line_spacing
        )
        
        # 计算总文本高度
        total_height = len(lines) * line_height
        
        # 垂直对齐
        if replacement.alignment == TextAlignment.MIDDLE:
            start_y = y + (max_height - total_height) // 2
        elif replacement.alignment == TextAlignment.BOTTOM:
            start_y = y + max_height - total_height
        else: # TOP
            start_y = y
            
        current_y = start_y
        for line in lines:
            # 水平对齐
            bbox = font.getbbox(line)
            text_width = bbox[2] - bbox[0]
            
            if replacement.alignment == TextAlignment.CENTER:
                start_x = x + (max_width - text_width) // 2
            elif replacement.alignment == TextAlignment.RIGHT:
                start_x = x + max_width - text_width
            else: # LEFT
                start_x = x
            
            # 绘制文本描边
            if replacement.stroke_width > 0 and replacement.stroke_color:
                draw.text((start_x, current_y), line, font=font, 
                          fill=replacement.stroke_color, 
                          stroke_width=replacement.stroke_width,
                          stroke_fill=replacement.stroke_color)
            
            # 绘制文本
            draw.text((start_x, current_y), line, font=font, fill=replacement.font_color)
            current_y += line_height

    def _draw_vertical_text(self, draw: ImageDraw.Draw,
                           replacement: MangaTextReplacement,
                           font: ImageFont.FreeTypeFont,
                           x: int, y: int, max_width: int, max_height: int) -> None:
        """绘制垂直文本
        
        支持多列文本绘制，会根据文本框的宽度自动计算每列的宽度，
        并尽可能均匀地将文本分布在各列中。
        """
        # 使用传入的列数
        column_count = replacement.column_count
        # 分割文本到对应的列数（从右到左的顺序）
        text_columns = self._split_text_into_columns(replacement.translated_text, column_count)
        text_columns.reverse()  # 反转列的顺序，使其从右到左
        
        # 计算每列的宽度
        column_width = max_width / column_count
        char_width = font.getbbox("中")[2] - font.getbbox("中")[0]  # 使用中文字符作为基准
        char_height = font.getbbox("中")[3] - font.getbbox("中")[1]
        
        for col_index, column_text in enumerate(text_columns):  # 现在从右到左遍历
            current_x = x + (column_width * col_index) + (column_width - char_width) / 2
            current_y = y
            
            for char in column_text:
                if char == '\n':
                    continue
                
                # 计算字符绘制位置
                char_y_offset = 0
                if replacement.alignment == TextAlignment.MIDDLE:
                    total_height = len(column_text) * (char_height + replacement.char_spacing)
                    char_y_offset = (max_height - total_height) / 2
                elif replacement.alignment == TextAlignment.BOTTOM:
                    total_height = len(column_text) * (char_height + replacement.char_spacing)
                    char_y_offset = max_height - total_height
                
                # 绘制文本描边
                if replacement.stroke_width > 0 and replacement.stroke_color:
                    draw.text(
                        (current_x, current_y + char_y_offset),
                        char, 
                        font=font,
                        fill=replacement.stroke_color,
                        stroke_width=replacement.stroke_width,
                        stroke_fill=replacement.stroke_color
                    )
                
                # 绘制文本
                draw.text(
                    (current_x, current_y + char_y_offset),
                    char,
                    font=font,
                    fill=replacement.font_color
                )
                
                # 移动到下一个字符位置
                current_y += char_height + replacement.char_spacing
                
                # 如果超出最大高度，重置到下一列
                if current_y + char_height > y + max_height:
                    current_x += column_width
                    current_y = y

    def replace_manga_text(self, image: np.ndarray, 
                           replacements: List[MangaTextReplacement],
                           inpaint_background: bool = True) -> np.ndarray:
        """
        在漫画图像上替换文本
        
        Args:
            image: 原始图像数据 (OpenCV格式)
            replacements: 漫画文本替换信息列表
            inpaint_background: 是否修复背景（涂白）
            
        Returns:
            替换文本后的图像
        """
        result_image = image.copy()
        
        for replacement in replacements:
            log.debug(f"处理替换: '{replacement.original_text}' -> '{replacement.translated_text}'")
            
            # 1. 修复背景（涂白）
            if inpaint_background:
                result_image = self._inpaint_background(result_image, replacement.bbox)
            
            # 2. 绘制新文本
            result_image = self._draw_text_with_layout(result_image, replacement)
            
        return result_image

    def process_manga_image(self, image: np.ndarray, 
                            structured_texts: List[Dict[str, Any]],
                            translations: Dict[str, str],
                            target_language: str = "zh",
                            inpaint_background: bool = True) -> np.ndarray:
        """
        处理漫画图像：基于结构化文本的翻译和智能文本替换
        
        Args:
            image: 原始图像数据
            structured_texts: 结构化文本列表，每个元素格式为:
                {
                    'text': str,  # 合并后的完整文本
                    'direction': str,  # 文本方向
                    'ocr_results': List[OCRResult]  # OCR结果列表
                }
            translations: 翻译结果字典
            target_language: 目标语言代码
            inpaint_background: 是否修复背景
            
        Returns:
            处理后的图像
        """
        # 创建漫画替换信息列表
        replacements = []
        
        for item in structured_texts:
            # 获取文本和其翻译
            original_text = item['text']
            translated_text = translations.get(original_text)
            
            if not translated_text:
                translated_text = self._find_fuzzy_translation(original_text, translations)
                
            if not translated_text:
                continue
                
            # 获取所有OCR结果的边界框点
            bbox_points = []
            confidences = []
            for ocr_result in item['ocr_results']:
                bbox_points.extend(ocr_result.bbox)
                confidences.append(ocr_result.confidence)
                
            if not bbox_points:
                continue
                
            # 计算边界框
            points = np.array(bbox_points)
            x_min = min(p[0] for p in bbox_points)
            y_min = min(p[1] for p in bbox_points)
            x_max = max(p[0] for p in bbox_points)
            y_max = max(p[1] for p in bbox_points)
            
            bbox = [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]
            
            # 确定文本方向
            original_direction = self._detect_text_direction(bbox)
            target_direction = self._determine_target_direction(
                original_text, translated_text, target_language, original_direction
            )
            
            # 计算其他布局参数
            width = x_max - x_min
            height = y_max - y_min
            column_count = len(item['ocr_results'])
            font_size = self._calculate_optimal_font_size(
                translated_text, bbox, target_direction,
                column_count=column_count
            )
            alignment = self._determine_alignment(target_direction, target_language)
            line_spacing, char_spacing = self._calculate_spacing(
                target_direction, target_language, font_size
            )
            
            # 创建替换信息
            replacement = MangaTextReplacement(
                original_text=original_text,
                translated_text=translated_text,
                bbox=bbox,
                confidence=sum(confidences) / len(confidences),
                direction=target_direction,
                alignment=alignment,
                font_size=font_size,
                line_spacing=line_spacing,
                char_spacing=char_spacing,
                max_width=int(width * 0.9),
                max_height=int(height * 0.9),
                column_count=column_count,
                stroke_color=(255, 255, 255),
                stroke_width=2
            )
            
            replacements.append(replacement)
        
        if not replacements:
            log.warning("没有找到可替换的漫画文本")
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
            log.info(f"漫画结果图像已保存: {output_path}")
            return True
        except Exception as e:
            log.error(f"保存漫画图像失败: {e}")
            return False


def create_manga_translation_dict(structured_texts: List[Dict[str, Any]], 
                                pure_translated_texts: List[str]) -> Dict[str, str]:
    """
    从结构化文本和纯翻译结果中创建漫画翻译字典 {原文: 译文}
    
    Args:
        structured_texts: 结构化文本列表，每个元素包含 'text' (原文) 和 'ocr_results'
        pure_translated_texts: 纯翻译结果列表，与 structured_texts 一一对应
        
    Returns:
        翻译字典 {原文: 译文}
    """
    translation_dict = {}
    
    if len(structured_texts) != len(pure_translated_texts):
        log.error("结构化文本列表和纯翻译结果列表长度不匹配，无法创建翻译字典。")
        return {}

    for i, item in enumerate(structured_texts):
        original_text = item['text'].strip()
        translated_text = pure_translated_texts[i].strip()
        
        if original_text and translated_text:
            translation_dict[original_text] = translated_text
            
    return translation_dict