# core/ocr/ocr_manager.py

import os
import cv2
import time
import yaml
import numpy as np
import asyncio
from typing import List, Tuple, Optional, Dict, Any
from utils import manga_logger as log
from core.config import config
from core.core_cache.cache_factory import get_cache_factory_instance
from core.core_cache.cache_interface import CacheInterface
from core.data_models import OCRResult
from OnnxOCR.onnxocr.onnx_paddleocr import ONNXPaddleOcr


class OCRManager:
    """OCR管理器 - 负责图像文字识别功能 (Async Version)"""

    def __init__(self):
        log.info("OCRManager (Async) 初始化开始")
        self.ocr_cache_manager: CacheInterface = get_cache_factory_instance().get_manager("ocr")
        self.ocr_engine = None
        self.is_model_loaded = False
        self.ocr_options = self._load_config_from_yaml()
        log.info("OCRManager (Async) 初始化完成")

    def _get_default_options(self) -> Dict[str, Any]:
        """返回一个安全的默认OCR配置"""
        log.warning("无法加载或解析 ocr_config.yaml，将使用默认安全配置。")
        return {
            'use_angle_cls': True,
            'use_gpu': False,
            'det': True,
            'rec': True,
            'cls': False,
            'det_model_dir': None,
            'rec_model_dir': None,
            'cls_model_dir': None,
            'rec_char_dict_path': None
        }

    def _load_config_from_yaml(self) -> Dict[str, Any]:
        """从YAML文件加载OCR配置"""
        config_path = os.path.join(os.path.dirname(__file__), 'ocr_config.yaml')
        if not os.path.exists(config_path):
            return self._get_default_options()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_from_yaml = yaml.safe_load(f)
            
            flat_options = {}
            for category, settings in config_from_yaml.items():
                if isinstance(settings, dict):
                    flat_options.update(settings)
            
            log.info(f"从 {config_path} 加载OCR配置成功。")
            return flat_options
        except (yaml.YAMLError, IOError) as e:
            log.error(f"加载或解析YAML配置文件 {config_path} 时出错: {e}")
            return self._get_default_options()
    
    def load_model(self, model_options: Optional[Dict[str, Any]] = None):
        """加载OCR模型"""
        try:
            log.info("开始加载OCR模型...")
            
            options = self.ocr_options.copy()
            if model_options:
                options.update(model_options)
            
            self.ocr_engine = ONNXPaddleOcr(**options)
            self.is_model_loaded = True
            log.info(f"OCR模型加载成功，配置: {options}")
        except Exception as e:
            error_msg = f"加载OCR模型时发生错误: {str(e)}"
            log.error(error_msg)
            self.is_model_loaded = False
            raise RuntimeError(error_msg) from e

    def is_ready(self) -> bool:
        """检查OCR引擎是否准备就绪"""
        return self.is_model_loaded and self.ocr_engine is not None

    async def recognize_image_data(self, image_data: np.ndarray,
                                   file_path_for_cache: Optional[str] = None,
                                   page_num_for_cache: Optional[int] = None,
                                   original_archive_path: Optional[str] = None,
                                   options: Optional[Dict[str, Any]] = None) -> List[OCRResult]:
        """
        Asynchronously recognizes text from image data, using cache if available.
        This is the primary method for OCR recognition.
        """
        if not self.is_ready():
            raise RuntimeError("OCR engine is not ready. Please load a model first.")

        if file_path_for_cache and page_num_for_cache is not None:
            try:
                key_path = original_archive_path or file_path_for_cache
                cache_key = self.ocr_cache_manager.generate_key(image_path=key_path, page_index=page_num_for_cache)
                cached_results = self.ocr_cache_manager.get(cache_key)
                if cached_results is not None:
                    log.info(f"OCR result loaded from cache for {key_path} page {page_num_for_cache}")
                    return cached_results
            except Exception as e:
                log.error(f"Error checking or getting OCR cache for {file_path_for_cache} page {page_num_for_cache}: {e}")

        current_ocr_options = self.ocr_options.copy()
        if options:
            current_ocr_options.update(options)

        try:
            log.info(f"No cache found. Starting async OCR for {file_path_for_cache or 'in-memory data'}...")
            
            def do_ocr():
                return self.ocr_engine.ocr(
                    image_data,
                    det=current_ocr_options.get('det', True),
                    rec=current_ocr_options.get('rec', True),
                    cls=current_ocr_options.get('cls', True)
                )

            result = await asyncio.to_thread(do_ocr)
            
            ocr_results_list = []
            img_height, img_width = image_data.shape[:2]
            if result and result[0]:
                for line in result[0]:
                    if len(line) >= 2:
                        bbox, text_info = line[0], line[1]
                        text = text_info[0] if isinstance(text_info, (list, tuple)) and len(text_info) >= 2 else str(text_info)
                        confidence = text_info[1] if isinstance(text_info, (list, tuple)) and len(text_info) >= 2 else 1.0
                        
                        x_coords = [p[0] for p in bbox]
                        y_coords = [p[1] for p in bbox]
                        width = max(x_coords) - min(x_coords)
                        height = max(y_coords) - min(y_coords)
                        direction = 'horizontal' if width > height else 'vertical'
                        
                        ocr_results_list.append(OCRResult(text, bbox, confidence, direction=direction, image_width=img_width, image_height=img_height))
            
            log.info(f"Async OCR completed. Found {len(ocr_results_list)} text regions.")

            if file_path_for_cache and page_num_for_cache is not None and ocr_results_list:
                try:
                    key_path_to_save = original_archive_path or file_path_for_cache
                    cache_key_to_save = self.ocr_cache_manager.generate_key(image_path=key_path_to_save, page_index=page_num_for_cache)
                    self.ocr_cache_manager.set(
                        cache_key_to_save, ocr_results_list,
                        file_path=file_path_for_cache, page_num=page_num_for_cache,
                        original_archive_path=original_archive_path
                    )
                    log.info(f"OCR result cached for {key_path_to_save} page {page_num_for_cache}")
                except Exception as e_cache_set:
                    log.error(f"Failed to cache OCR result for {file_path_for_cache}: {e_cache_set}")

            return ocr_results_list

        except Exception as e:
            log.error(f"An error occurred during async OCR processing: {e}", exc_info=True)
            raise RuntimeError(f"Async OCR recognition failed: {e}") from e

    def get_text_only(self, ocr_results: List[OCRResult]) -> str:
        """
        从OCR结果中提取纯文本，并尝试合并多列文本。
        """
        structured_texts = self.get_structured_text(ocr_results)
        return '\n'.join([item.text for item in structured_texts])

    def filter_by_confidence(self, ocr_results: List[OCRResult], 
                           min_confidence: float = 0.8) -> List[OCRResult]:
        """
        根据置信度过滤OCR结果
        """
        log.debug(f"Filtering {len(ocr_results)} OCR results with threshold {min_confidence}")
        filtered = [result for result in ocr_results if result.confidence >= min_confidence]
        log.debug(f"Confidence filtering: {len(ocr_results)} -> {len(filtered)}")
        return filtered

    def _merge_bboxes(self, bbox1: List[List[int]], bbox2: List[List[int]]) -> List[List[int]]:
        """
        合并两个边界框，返回一个包含所有点的最小外接矩形。
        """
        all_x = [p[0] for p in bbox1] + [p[0] for p in bbox2]
        all_y = [p[1] for p in bbox1] + [p[1] for p in bbox2]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        return [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]]

    def _sort_and_group_ocr_results(self, ocr_results: List[OCRResult]) -> List[OCRResult]:
        """
        合并OCR识别结果中存在重叠的文本框
        """
        if not ocr_results:
            return []
        
        direction_groups = {}
        for result in ocr_results:
            direction = result.direction or "unknown"
            if direction not in direction_groups:
                direction_groups[direction] = []
            direction_groups[direction].append(result)
        
        merged_results = []
        
        for direction, group in direction_groups.items():
            rects = []
            for result in group:
                x_coords = [p[0] for p in result.bbox]
                y_coords = [p[1] for p in result.bbox]
                rects.append((min(x_coords), min(y_coords), max(x_coords), max(y_coords)))
            
            n = len(group)
            parent = list(range(n))
            
            def find(x):
                if parent[x] != x:
                    parent[x] = find(parent[x])
                return parent[x]
            
            def union(x, y):
                root_x = find(x)
                root_y = find(y)
                if root_x != root_y:
                    parent[root_y] = root_x
            
            for i in range(n):
                for j in range(i + 1, n):
                    rect1, rect2 = rects[i], rects[j]
                    if (rect1[0] < rect2[2] and rect1[2] > rect2[0] and
                        rect1[1] < rect2[3] and rect1[3] > rect2[1]):
                        union(i, j)
            
            components = {}
            for i in range(n):
                root = find(i)
                if root not in components:
                    components[root] = []
                components[root].append(group[i])
            
            for comp in components.values():
                if len(comp) == 1:
                    merged_results.append(comp[0])
                else:
                    comp_sorted = sorted(comp, key=lambda r: (-min(p[0] for p in r.bbox), min(p[1] for p in r.bbox)))
                    merged_text = ''.join(r.text for r in comp_sorted)
                    merged_bbox = comp[0].bbox
                    for i in range(1, len(comp)):
                        merged_bbox = self._merge_bboxes(merged_bbox, comp[i].bbox)
                    
                    avg_confidence = sum(r.confidence for r in comp) / len(comp)
                    
                    merged_results.append(OCRResult(
                        text=merged_text,
                        bbox=merged_bbox,
                        confidence=avg_confidence,
                        direction=direction,
                        merged_count=len(comp)
                    ))
        
        return merged_results
 
    def get_structured_text(self, ocr_results: List[OCRResult]) -> List[OCRResult]:
        """
        从OCR结果中提取结构化文本，并尝试合并多列文本。
        """
        if not ocr_results:
            return []

        processed_groups = self._sort_and_group_ocr_results(ocr_results)

        log.info(f"结构化文本识别完成，共识别到 {len(processed_groups)} 个文本区域。")
        return processed_groups

    def filter_numeric_and_symbols(self, ocr_results: List[OCRResult]) -> List[OCRResult]:
        """
        过滤掉纯数字和符号的OCR结果
        """
        import re
        
        def is_pure_numeric_or_symbol(text: str) -> bool:
            text = ''.join(text.split())
            pattern = r'^[\d\s,.。:：\-_/\\+=\(\)\[\]【】［］（）\{\}]*$'
            return bool(re.match(pattern, text))
        
        filtered_results = [result for result in ocr_results if not is_pure_numeric_or_symbol(result.text)]
        
        removed_count = len(ocr_results) - len(filtered_results)
        if removed_count > 0:
            log.info(f"过滤纯数字和符号文本: {len(ocr_results)} -> {len(filtered_results)} (移除了 {removed_count} 个纯数字/符号文本)")
        
        return filtered_results