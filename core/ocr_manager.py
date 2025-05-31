# core/ocr_manager.py

import os
import cv2
import time
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from PySide6.QtCore import QObject, Signal, QThread
from utils import manga_logger as log
from core.config import config

# 导入OnnxOCR
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'OnnxOCR'))
from onnxocr.onnx_paddleocr import ONNXPaddleOcr


class OCRResult:
    """OCR识别结果数据类"""
    def __init__(self, text: str, bbox: List[List[int]], confidence: float,
                 direction: Optional[str] = None, column: Optional[int] = None, row: Optional[int] = None,
                 merged_count: int = 1, ocr_results: Optional[List[Any]] = None):
        self.text = text  # 识别的文本
        self.translated_texts = []  # 翻译后的文本列表
        self.bbox = bbox  # 文本框坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        self.confidence = confidence  # 置信度
        self.direction = direction  # 文本方向，例如 'horizontal' 或 'vertical'
        self.column = column  # 文本所属的列
        self.row = row  # 文本所属的行
        self.merged_count = merged_count  # 合并计数，表示由多少个文本框合并而来
        self.ocr_results = ocr_results if ocr_results is not None else []  # 原始OCR结果列表
        
    def __str__(self):
        return f"OCRResult(text='{self.text}', confidence={self.confidence:.3f}, direction='{self.direction}', column={self.column}, row={self.row}, merged_count={self.merged_count})"
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'text': self.text,
            'bbox': self.bbox,
            'confidence': self.confidence,
            'direction': self.direction,
            'column': self.column,
            'row': self.row,
            'merged_count': self.merged_count
        }


class OCRWorker(QThread):
    """OCR工作线程"""
    ocr_finished = Signal(list)  # 识别完成信号
    ocr_error = Signal(str)      # 识别错误信号
    ocr_progress = Signal(str)   # 进度信号
    
    def __init__(self, ocr_engine, image_data, ocr_options):
        super().__init__()
        self.ocr_engine = ocr_engine
        self.image_data = image_data
        self.ocr_options = ocr_options
        
    def run(self):
        """执行OCR识别"""
        try:
            self.ocr_progress.emit("开始OCR识别...")
            
            # 执行OCR识别
            start_time = time.time()
            result = self.ocr_engine.ocr(
                self.image_data,
                det=self.ocr_options.get('det', True),
                rec=self.ocr_options.get('rec', True),
                cls=self.ocr_options.get('cls', True)
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # 解析结果
            ocr_results = []
            if result and len(result) > 0 and result[0]:
                for line in result[0]:
                    if len(line) >= 2:
                        bbox = line[0]
                        text_info = line[1]
                        if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                            text = text_info[0]
                            confidence = text_info[1]
                        else:
                            text = str(text_info)
                            confidence = 1.0
                        
                        # 尝试判断文本方向 (横向或竖向)
                        # 假设 bbox 是 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                        # 计算文本框的宽度和高度
                        # 找到最小/最大 x, y 坐标
                        x_coords = [p[0] for p in bbox]
                        y_coords = [p[1] for p in bbox]

                        min_x = min(x_coords)
                        min_y = min(y_coords)
                        max_x = max(x_coords)
                        max_y = max(y_coords)

                        width = max_x - min_x
                        height = max_y - min_y

                        direction = None
                        if width > 0 and height > 0:
                            # 简单的判断：如果宽度远大于高度，认为是横向；反之认为是竖向
                            # 可以根据实际情况调整阈值
                            if width / height > 1.5:  # 经验值，可调整
                                direction = 'horizontal'
                            elif height / width > 1.5: # 经验值，可调整
                                direction = 'vertical'
                            else:
                                direction = 'unknown' # 或根据需要设置为默认方向

                        ocr_result = OCRResult(text, bbox, confidence, direction=direction)
                        ocr_results.append(ocr_result)
            
            self.ocr_progress.emit(f"OCR识别完成，耗时 {processing_time:.2f}秒，识别到 {len(ocr_results)} 个文本区域")
            self.ocr_finished.emit(ocr_results)
            
        except Exception as e:
            error_msg = f"OCR识别过程中发生错误: {str(e)}"
            log.error(error_msg)
            self.ocr_error.emit(error_msg)


class OCRManager(QObject):
    """OCR管理器 - 负责图像文字识别功能"""
    
    # 信号定义
    ocr_started = Signal()                    # OCR开始信号
    ocr_finished = Signal(list)               # OCR完成信号，传递OCRResult列表
    ocr_error = Signal(str)                   # OCR错误信号
    ocr_progress = Signal(str)                # OCR进度信号
    model_loaded = Signal()                   # 模型加载完成信号
    model_load_error = Signal(str)            # 模型加载错误信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        log.info("OCRManager初始化开始")
        
        # OCR引擎实例
        self.ocr_engine = None
        self.is_model_loaded = False
        
        # 工作线程
        self.ocr_worker = None
        
        # OCR配置选项
        self.ocr_options = {
            'use_angle_cls': True,  # 是否使用角度分类器
            'use_gpu': False,       # 是否使用GPU
            'det': True,            # 是否进行文本检测
            'rec': True,            # 是否进行文本识别
            'cls': False             # 是否进行角度分类
        }
        
        log.info("OCRManager初始化完成")
    
    def load_model(self, model_options: Optional[Dict[str, Any]] = None):
        """加载OCR模型"""
        try:
            log.info("开始加载OCR模型...")
            
            # 合并配置选项
            options = self.ocr_options.copy()
            if model_options:
                options.update(model_options)
            
            # 创建OCR引擎实例
            self.ocr_engine = ONNXPaddleOcr(**options)
            self.is_model_loaded = True
            
            log.info(f"OCR模型加载成功，配置: {options}")
            self.model_loaded.emit()
            
        except Exception as e:
            error_msg = f"加载OCR模型时发生错误: {str(e)}"
            log.error(error_msg)
            self.is_model_loaded = False
            self.model_load_error.emit(error_msg)
    
    def is_ready(self) -> bool:
        """检查OCR引擎是否准备就绪"""
        return self.is_model_loaded and self.ocr_engine is not None
    
    def recognize_image(self, image_path: str, options: Optional[Dict[str, Any]] = None) -> None:
        """
        识别图像中的文字（异步）
        
        Args:
            image_path: 图像文件路径
            options: OCR选项，如 {'det': True, 'rec': True, 'cls': True}
        """
        if not self.is_ready():
            error_msg = "OCR引擎未准备就绪，请先加载模型"
            log.error(error_msg)
            self.ocr_error.emit(error_msg)
            return
        
        if not os.path.exists(image_path):
            error_msg = f"图像文件不存在: {image_path}"
            log.error(error_msg)
            self.ocr_error.emit(error_msg)
            return
        
        try:
            # 读取图像
            image = cv2.imread(image_path)
            if image is None:
                error_msg = f"无法读取图像文件: {image_path}"
                log.error(error_msg)
                self.ocr_error.emit(error_msg)
                return
            
            self.recognize_image_data(image, options)
            
        except Exception as e:
            error_msg = f"读取图像文件时发生错误: {str(e)}"
            log.error(error_msg)
            self.ocr_error.emit(error_msg)
    
    def recognize_image_data(self, image_data: np.ndarray, options: Optional[Dict[str, Any]] = None) -> None:
        """
        识别图像数据中的文字（异步）
        
        Args:
            image_data: 图像数据（numpy数组）
            options: OCR选项
        """
        if not self.is_ready():
            error_msg = "OCR引擎未准备就绪，请先加载模型"
            log.error(error_msg)
            self.ocr_error.emit(error_msg)
            return
        
        # 停止之前的识别任务
        if self.ocr_worker and self.ocr_worker.isRunning():
            self.ocr_worker.terminate()
            self.ocr_worker.wait()
        
        # 合并选项
        ocr_options = self.ocr_options.copy()
        if options:
            ocr_options.update(options)
        
        # 创建工作线程
        self.ocr_worker = OCRWorker(self.ocr_engine, image_data, ocr_options)
        
        # 连接信号
        self.ocr_worker.ocr_finished.connect(self._on_ocr_finished)
        self.ocr_worker.ocr_error.connect(self._on_ocr_error)
        self.ocr_worker.ocr_progress.connect(self._on_ocr_progress)
        
        # 发送开始信号
        self.ocr_started.emit()
        
        # 启动线程
        self.ocr_worker.start()
    
    def recognize_image_sync(self, image_path: str, options: Optional[Dict[str, Any]] = None) -> List[OCRResult]:
        """
        同步识别图像中的文字
        
        Args:
            image_path: 图像文件路径
            options: OCR选项
            
        Returns:
            OCRResult列表
        """
        if not self.is_ready():
            raise RuntimeError("OCR引擎未准备就绪，请先加载模型")
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图像文件不存在: {image_path}")
        
        # 读取图像
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"无法读取图像文件: {image_path}")
        
        return self.recognize_image_data_sync(image, options)
    
    def recognize_image_data_sync(self, image_data: np.ndarray, options: Optional[Dict[str, Any]] = None) -> List[OCRResult]:
        """
        同步识别图像数据中的文字
        
        Args:
            image_data: 图像数据（numpy数组）
            options: OCR选项
            
        Returns:
            OCRResult列表
        """
        if not self.is_ready():
            raise RuntimeError("OCR引擎未准备就绪，请先加载模型")
        
        # 合并选项
        ocr_options = self.ocr_options.copy()
        if options:
            ocr_options.update(options)
        
        try:
            log.info("开始同步OCR识别...")
            start_time = time.time()
            
            # 执行OCR识别
            result = self.ocr_engine.ocr(
                image_data,
                det=ocr_options.get('det', True),
                rec=ocr_options.get('rec', True),
                cls=ocr_options.get('cls', True)
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # 解析结果
            ocr_results = []
            if result and len(result) > 0 and result[0]:
                for line in result[0]:
                    if len(line) >= 2:
                        bbox = line[0]
                        text_info = line[1]
                        if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                            text = text_info[0]
                            confidence = text_info[1]
                        else:
                            text = str(text_info)
                            confidence = 1.0
                        
                        ocr_result = OCRResult(text, bbox, confidence)
                        ocr_results.append(ocr_result)
            
            log.info(f"同步OCR识别完成，耗时 {processing_time:.2f}秒，识别到 {len(ocr_results)} 个文本区域")
            return ocr_results
            
        except Exception as e:
            error_msg = f"同步OCR识别过程中发生错误: {str(e)}"
            log.error(error_msg)
            raise RuntimeError(error_msg)
    
    def set_ocr_options(self, options: Dict[str, Any]):
        """设置OCR选项"""
        self.ocr_options.update(options)
        log.info(f"OCR选项已更新: {self.ocr_options}")
    
    def get_ocr_options(self) -> Dict[str, Any]:
        """获取当前OCR选项"""
        return self.ocr_options.copy()
    
    def stop_recognition(self):
        """停止当前的识别任务"""
        if self.ocr_worker and self.ocr_worker.isRunning():
            log.info("停止OCR识别任务")
            self.ocr_worker.terminate()
            self.ocr_worker.wait()
    
    def _on_ocr_finished(self, results: List[OCRResult]):
        """OCR完成回调"""
        self.ocr_finished.emit(results)
    
    def _on_ocr_error(self, error_msg: str):
        """OCR错误回调"""
        self.ocr_error.emit(error_msg)
    
    def _on_ocr_progress(self, progress_msg: str):
        """OCR进度回调"""
        self.ocr_progress.emit(progress_msg)
    
    def save_ocr_result_image(self, image_data: np.ndarray, ocr_results: List[OCRResult], 
                             output_path: str) -> bool:
        """
        保存带有OCR结果标注的图像
        
        Args:
            image_data: 原始图像数据
            ocr_results: OCR识别结果
            output_path: 输出图像路径
            
        Returns:
            是否保存成功
        """
        try:
            from PIL import Image
            from onnxocr.utils import draw_ocr
            
            # 转换图像格式 BGR -> RGB
            image_rgb = image_data[:, :, ::-1]
            
            # 提取文本框、文本和置信度
            boxes = [result.bbox for result in ocr_results]
            texts = [result.text for result in ocr_results]
            scores = [result.confidence for result in ocr_results]
            
            # 绘制OCR结果
            result_image = draw_ocr(image_rgb, boxes, texts, scores)
            
            # 保存图像
            pil_image = Image.fromarray(result_image)
            pil_image.save(output_path)
            
            log.info(f"OCR结果图像已保存: {output_path}")
            return True
            
        except Exception as e:
            error_msg = f"保存OCR结果图像时发生错误: {str(e)}"
            log.error(error_msg)
            return False
    
    def get_text_only(self, ocr_results: List[OCRResult]) -> str:
        """
        从OCR结果中提取纯文本，并尝试合并多列文本。
        
        Args:
            ocr_results: OCR识别结果列表
            
        Returns:
            合并的文本字符串
        """
        structured_texts = self.get_structured_text(ocr_results)
        return '\n'.join([item['text'] for item in structured_texts])
    
    def filter_by_confidence(self, ocr_results: List[OCRResult], 
                           min_confidence: float = 0.8) -> List[OCRResult]:
        """
        根据置信度过滤OCR结果
        
        Args:
            ocr_results: OCR识别结果列表
            min_confidence: 最小置信度阈值
            
        Returns:
            过滤后的OCR结果列表
        """
        # 输出过滤前的结果
        print("OCR结果:")
        for result in ocr_results:
            print(f"文本: {result.text}, 置信度: {result.confidence}")
        filtered_results = [result for result in ocr_results 
                          if result.confidence >= min_confidence]
        
        # 输出过滤后的结果
        print("\n过滤后的OCR结果:")
        for result in filtered_results:
            print(f"文本: {result.text}, 置信度: {result.confidence}")

        print(f"置信度过滤: {len(ocr_results)} -> {len(filtered_results)} "
                f"(阈值: {min_confidence})")
        
        return filtered_results
    
    def __del__(self):
        """析构函数"""
        self.stop_recognition()

    def _merge_bboxes(self, bbox1: List[List[int]], bbox2: List[List[int]]) -> List[List[int]]:
        """
        合并两个边界框，返回一个包含所有点的最小外接矩形。
        bbox 格式: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        """
        all_x = [p[0] for p in bbox1] + [p[0] for p in bbox2]
        all_y = [p[1] for p in bbox1] + [p[1] for p in bbox2]

        min_x = min(all_x)
        min_y = min(all_y)
        max_x = max(all_x)
        max_y = max(all_y)

        # 返回一个表示合并后矩形的新 bbox (左上，右上，右下，左下)
        return [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]]

    def _sort_and_group_ocr_results(self, ocr_results: List[OCRResult],
                                     line_threshold_ratio: float = 0.05,
                                     column_threshold_ratio: float = 0.05) -> List[OCRResult]:
        """
        合并OCR识别结果中存在重叠的文本框
        步骤：
        1. 按方向分组
        2. 对每组检测重叠的文本框
        3. 合并重叠的文本框
        4. 按阅读顺序排序文本（先列后行，从右到左，从上到下）
        """
        if not ocr_results:
            return []

        ocr_results = self.filter_by_confidence(ocr_results, min_confidence=0.8)
        
        # 1. 按方向分组
        direction_groups = {}
        for result in ocr_results:
            direction = result.direction or "unknown"
            if direction not in direction_groups:
                direction_groups[direction] = []
            direction_groups[direction].append(result)
        
        merged_results = []
        
        # 2. 对每个方向组处理
        for direction, group in direction_groups.items():
            # 计算每个框的边界矩形
            rects = []
            for result in group:
                x_coords = [p[0] for p in result.bbox]
                y_coords = [p[1] for p in result.bbox]
                min_x, max_x = min(x_coords), max(x_coords)
                min_y, max_y = min(y_coords), max(y_coords)
                rects.append((min_x, min_y, max_x, max_y))
            
            # 使用并查集合并重叠的框
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
            
            # 检测重叠
            for i in range(n):
                for j in range(i+1, n):
                    rect1 = rects[i]
                    rect2 = rects[j]
                    # 检查矩形是否重叠
                    if (rect1[0] < rect2[2] and rect1[2] > rect2[0] and
                        rect1[1] < rect2[3] and rect1[3] > rect2[1]):
                        union(i, j)
            
            # 收集合并组
            components = {}
            for i in range(n):
                root = find(i)
                if root not in components:
                    components[root] = []
                components[root].append(group[i])
            
            # 3. 合并重叠的框
            for comp in components.values():
                if len(comp) == 1:
                    # 未合并，直接添加
                    merged_results.append(comp[0])
                else:
                    # 合并文本、边界框和置信度
                    # 按阅读顺序排序：先列（从右到左）后行（从上到下）
                    comp_sorted = sorted(
                        comp,
                        key=lambda r: (-min(p[0] for p in r.bbox), min(p[1] for p in r.bbox))
                    )
                    merged_text = ''.join(r.text for r in comp_sorted)
                    
                    # 合并边界框
                    merged_bbox = comp[0].bbox
                    for i in range(1, len(comp)):
                        merged_bbox = self._merge_bboxes(merged_bbox, comp[i].bbox)
                    
                    # 计算平均置信度
                    avg_confidence = sum(r.confidence for r in comp) / len(comp)
                    
                    # 创建合并后的结果
                    merged_result = OCRResult(
                        text=merged_text,
                        bbox=merged_bbox,
                        confidence=avg_confidence,
                        direction=direction,
                        merged_count=len(comp)
                    )
                    merged_results.append(merged_result)
        
        return merged_results
 
    def get_structured_text(self, ocr_results: List[OCRResult]) -> List[Dict[str, Any]]:
        """
        从OCR结果中提取结构化文本，并尝试合并多列文本。
        
        Args:
            ocr_results: 原始OCR结果列表。
            
        Returns:
            结构化文本字典列表，每个字典包含：
            - text: 合并后的文本
            - ocr_results: 相关的OCR结果对象列表（包含所有原始OCR结果）
        """
        if not ocr_results:
            return []

        # 进行结果合并
        processed_groups = self._sort_and_group_ocr_results(ocr_results)
        
        # 构建新格式的结构化文本列表
        structured_texts = []
        used_originals = set()  # 用于跟踪已处理的原始OCR结果的id
        
        # 为每个合并后的结果找到对应的原始OCR结果
        for result in processed_groups:
            bbox = result.bbox
            
            # 查找与当前merged bbox重叠的所有原始OCR结果
            associated_results = []
            for orig in ocr_results:
                if id(orig) in used_originals:
                    continue
                    
                # 检查边界框是否重叠
                orig_bbox = orig.bbox
                
                # 计算两个框的边界
                merged_left = min(p[0] for p in bbox)
                merged_right = max(p[0] for p in bbox)
                merged_top = min(p[1] for p in bbox)
                merged_bottom = max(p[1] for p in bbox)
                
                orig_left = min(p[0] for p in orig_bbox)
                orig_right = max(p[0] for p in orig_bbox)
                orig_top = min(p[1] for p in orig_bbox)
                orig_bottom = max(p[1] for p in orig_bbox)
                
                # 检查重叠
                if not (merged_right < orig_left or 
                       merged_left > orig_right or
                       merged_bottom < orig_top or
                       merged_top > orig_bottom):
                    associated_results.append(orig)
                    used_originals.add(id(orig))
            
            structure = {
                'text': result.text,
                'ocr_results': associated_results if associated_results else [result]
            }
            structured_texts.append(structure)
        
        # 检查是否有未处理的原始结果
        for orig in ocr_results:
            if id(orig) not in used_originals:
                structure = {
                    'text': orig.text,
                    'ocr_results': [orig]
                }
                structured_texts.append(structure)
                used_originals.add(id(orig))
        
        return structured_texts