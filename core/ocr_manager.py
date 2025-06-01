# core/ocr_manager.py

import os
import cv2
import time
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from PySide6.QtCore import QObject, Signal, QThread
from utils import manga_logger as log
from core.config import config
from core.cache_factory import get_cache_factory_instance # Added
from core.cache_interface import CacheInterface # Added
from core.data_models import OCRResult # Import OCRResult from data_models

# 导入OnnxOCR
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'OnnxOCR'))
from onnxocr.onnx_paddleocr import ONNXPaddleOcr

# OCRResult class definition is removed from here


class OCRWorker(QThread): # This worker will now also need file_path and page_num for caching
    """OCR工作线程"""
    ocr_finished = Signal(list, str, int)  #识别完成信号 (results, file_path, page_num)
    ocr_error = Signal(str)      # 识别错误信号
    ocr_progress = Signal(str)   # 进度信号
    
    def __init__(self, ocr_engine, image_data, ocr_options, file_path: str, page_num: int):
        super().__init__()
        self.ocr_engine = ocr_engine
        self.image_data = image_data
        self.ocr_options = ocr_options
        self.file_path = file_path
        self.page_num = page_num
        
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
            ocr_results_list = []
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
                        
                        x_coords = [p[0] for p in bbox]
                        y_coords = [p[1] for p in bbox]
                        min_x, max_x = min(x_coords), max(x_coords)
                        min_y, max_y = min(y_coords), max(y_coords)
                        width = max_x - min_x
                        height = max_y - min_y
                        direction = 'horizontal' if width > height else 'vertical'

                        ocr_result_obj = OCRResult(text, bbox, confidence, direction=direction)
                        ocr_results_list.append(ocr_result_obj)
            
            self.ocr_progress.emit(f"OCR识别完成，耗时 {processing_time:.2f}秒，识别到 {len(ocr_results_list)} 个文本区域")
            self.ocr_finished.emit(ocr_results_list, self.file_path, self.page_num) # Emit with file_path and page_num
            
        except Exception as e:
            error_msg = f"OCR识别过程中发生错误 (文件: {self.file_path}, 页码: {self.page_num}): {str(e)}"
            log.error(error_msg)
            self.ocr_error.emit(error_msg)


class OCRManager(QObject):
    """OCR管理器 - 负责图像文字识别功能"""
    
    # 信号定义
    ocr_started = Signal()                    # OCR开始信号
    ocr_finished = Signal(list)               # OCR完成信号，传递OCRResult列表 (original, for non-cached path or direct calls)
    ocr_cache_loaded = Signal(list)           # OCR结果从缓存加载完成信号
    ocr_error = Signal(str)                   # OCR错误信号
    ocr_progress = Signal(str)                # OCR进度信号
    model_loaded = Signal()                   # 模型加载完成信号
    model_load_error = Signal(str)            # 模型加载错误信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        log.info("OCRManager初始化开始")
        
        self.ocr_cache_manager: CacheInterface = get_cache_factory_instance().get_manager("ocr")
        
        # OCR引擎实例
        self.ocr_engine = None
        self.is_model_loaded = False
        
        # 工作线程
        self.ocr_worker: Optional[OCRWorker] = None # Type hint
        
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
    
    def recognize_image_with_cache(self, file_path: str, page_num: int, image_data: np.ndarray, options: Optional[Dict[str, Any]] = None) -> None:
        """
        识别图像数据中的文字（异步），优先使用缓存。
        Args:
            file_path: 原始漫画文件路径 (用于生成缓存键)
            page_num: 当前页码 (用于生成缓存键)
            image_data: 图像数据 (numpy数组)
            options: OCR选项
        """
        if not self.is_ready():
            error_msg = "OCR引擎未准备就绪，请先加载模型"
            log.error(error_msg)
            self.ocr_error.emit(error_msg)
            return

        try:
            cache_key = self.ocr_cache_manager.generate_key(file_path, page_num)
            cached_results = self.ocr_cache_manager.get(cache_key)

            if cached_results is not None:
                log.info(f"OCR结果从缓存加载: {file_path} (页码 {page_num})")
                self.ocr_cache_loaded.emit(cached_results)
                return
        except Exception as e: # Catch errors during key generation or cache get
            log.error(f"检查或获取OCR缓存时出错 (文件: {file_path}, 页码: {page_num}): {e}")
            # Proceed to OCR without cache if error occurs here

        log.info(f"未找到OCR缓存或缓存无效，开始识别: {file_path} (页码 {page_num})")
        
        # 停止之前的识别任务
        if self.ocr_worker and self.ocr_worker.isRunning():
            log.info("检测到正在运行的OCR任务，正在终止...")
            self.ocr_worker.terminate() # Request termination
            if not self.ocr_worker.wait(3000): # Wait up to 3 seconds
                 log.warning("OCR工作线程未能及时终止。")
                 # Depending on requirements, could force quit or raise error
        
        # 合并选项
        current_ocr_options = self.ocr_options.copy()
        if options:
            current_ocr_options.update(options)
        
        # 创建工作线程
        self.ocr_worker = OCRWorker(self.ocr_engine, image_data, current_ocr_options, file_path, page_num)
        
        # 连接信号
        self.ocr_worker.ocr_finished.connect(self._on_ocr_finished_and_cache) # Connect to new slot
        self.ocr_worker.ocr_error.connect(self._on_ocr_error)
        self.ocr_worker.ocr_progress.connect(self._on_ocr_progress)
        
        # 发送开始信号
        self.ocr_started.emit()
        
        # 启动线程
        self.ocr_worker.start()

    # Keep original recognize_image_data if it's used elsewhere without caching context
    # Or adapt it to call recognize_image_with_cache if file_path and page_num can be provided
    def recognize_image_data(self, image_data: np.ndarray, options: Optional[Dict[str, Any]] = None,
                             file_path_for_cache: Optional[str] = None, page_num_for_cache: Optional[int] = None) -> None:
        """
        识别图像数据中的文字（异步）。
        如果提供了 file_path_for_cache 和 page_num_for_cache，则会尝试使用缓存。
        """
        if file_path_for_cache and page_num_for_cache is not None:
            self.recognize_image_with_cache(file_path_for_cache, page_num_for_cache, image_data, options)
        else:
            # Fallback to non-cached version or simple OCR if no cache info
            log.warning("recognize_image_data 调用时未提供缓存信息，将不使用缓存。")
            if not self.is_ready():
                self.ocr_error.emit("OCR引擎未准备就绪")
                return

            if self.ocr_worker and self.ocr_worker.isRunning():
                self.ocr_worker.terminate()
                self.ocr_worker.wait()
            
            current_ocr_options = self.ocr_options.copy()
            if options:
                current_ocr_options.update(options)
            
            # Create a dummy file_path and page_num if we must use the new OCRWorker signature
            # This path won't be used for caching effectively if it's not the real one.
            # This indicates a need to refactor callers or OCRWorker.
            # For now, let's assume OCRWorker's file_path/page_num are for caching,
            # so if no cache info, they can be dummy values.
            temp_file_path = "unknown_source"
            temp_page_num = -1

            self.ocr_worker = OCRWorker(self.ocr_engine, image_data, current_ocr_options, temp_file_path, temp_page_num)
            self.ocr_worker.ocr_finished.connect(self._on_ocr_finished_simple) # Connect to a slot that doesn't cache
            self.ocr_worker.ocr_error.connect(self._on_ocr_error)
            self.ocr_worker.ocr_progress.connect(self._on_ocr_progress)
            self.ocr_started.emit()
            self.ocr_worker.start()

    def recognize_image(self, image_path: str, page_num: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> None:
        """
        识别图像文件中的文字（异步），如果提供了 page_num，则会尝试使用缓存。
        Args:
            image_path: 图像文件路径
            page_num: 页码 (可选, 用于缓存)
            options: OCR选项
        """
        if not self.is_ready():
            self.ocr_error.emit("OCR引擎未准备就绪")
            return
        
        if not os.path.exists(image_path):
            self.ocr_error.emit(f"图像文件不存在: {image_path}")
            return
        
        try:
            img_data_np = np.fromfile(image_path, dtype=np.uint8)
            image = cv2.imdecode(img_data_np, cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"无法读取图像文件: {image_path}")
            
            if page_num is not None:
                self.recognize_image_with_cache(image_path, page_num, image, options)
            else:
                # Call the version that doesn't use cache or pass None for cache params
                self.recognize_image_data(image, options, file_path_for_cache=None, page_num_for_cache=None)
                
        except Exception as e:
            self.ocr_error.emit(f"读取或处理图像时出错 {image_path}: {str(e)}")


    def recognize_image_sync(self, image_path: str, page_num: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> List[OCRResult]:
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
        
        # 使用imdecode来支持Unicode路径
        try:
            image_data = np.fromfile(image_path, dtype=np.uint8)
            image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"无法读取图像文件: {image_path}")
        except Exception as e:
            raise ValueError(f"读取图像文件失败: {image_path}, 错误: {e}")
        
        return self.recognize_image_data_sync(image, options)
    
    def recognize_image_data_sync(self, image_data: np.ndarray,
                                  file_path_for_cache: Optional[str] = None,
                                  page_num_for_cache: Optional[int] = None,
                                  original_archive_path: Optional[str] = None, # Added
                                  options: Optional[Dict[str, Any]] = None) -> List[OCRResult]:
        """
        同步识别图像数据中的文字，优先使用缓存。
        Args:
            image_data: 图像数据
            file_path_for_cache: 用于缓存的实际图片文件路径 (例如解压后的临时文件路径)
            page_num_for_cache: 页码
            original_archive_path: 原始压缩包路径 (如果适用)，用于生成一致的缓存键和元数据
            options: OCR选项
        """
        if not self.is_ready():
            raise RuntimeError("OCR引擎未准备就绪，请先加载模型")

        if file_path_for_cache and page_num_for_cache is not None:
            try:
                # Generate key using original_archive_path if available, otherwise file_path_for_cache
                key_path = original_archive_path if original_archive_path else file_path_for_cache
                cache_key = self.ocr_cache_manager.generate_key(
                    file_path=key_path, # Use the determined path for key generation
                    page_num=page_num_for_cache,
                    # original_archive_path is implicitly handled by generate_key if key_path is original_archive_path
                )
                cached_results = self.ocr_cache_manager.get(cache_key)
                if cached_results is not None:
                    log_msg_cache = f"同步OCR结果从缓存加载: 键='{cache_key}', 实际文件='{file_path_for_cache}', 页码={page_num_for_cache}"
                    if original_archive_path:
                        log_msg_cache += f", 原始存档='{original_archive_path}'"
                    log.info(log_msg_cache)
                    return cached_results
            except Exception as e:
                log.error(f"同步检查或获取OCR缓存时出错 (实际文件: {file_path_for_cache}, 页码: {page_num_for_cache}, 原始存档: {original_archive_path}): {e}")
        
        current_ocr_options = self.ocr_options.copy()
        if options:
            current_ocr_options.update(options)
        
        try:
            log_msg_ocr = f"开始同步OCR识别 (实际文件: {file_path_for_cache or 'N/A'}, 页码: {page_num_for_cache if page_num_for_cache is not None else 'N/A'}"
            if original_archive_path:
                log_msg_ocr += f", 原始存档: {original_archive_path}"
            log_msg_ocr += ")..."
            log.info(log_msg_ocr)
            start_time = time.time()
            
            result = self.ocr_engine.ocr(
                image_data,
                det=current_ocr_options.get('det', True),
                rec=current_ocr_options.get('rec', True),
                cls=current_ocr_options.get('cls', True)
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            ocr_results_list = []
            if result and len(result) > 0 and result[0]:
                for line in result[0]:
                    if len(line) >= 2:
                        bbox = line[0]
                        text_info = line[1]
                        text = text_info[0] if isinstance(text_info, (list, tuple)) and len(text_info) >= 2 else str(text_info)
                        confidence = text_info[1] if isinstance(text_info, (list, tuple)) and len(text_info) >= 2 else 1.0
                        
                        x_coords = [p[0] for p in bbox]
                        y_coords = [p[1] for p in bbox]
                        min_x, max_x = min(x_coords), max(x_coords)
                        min_y, max_y = min(y_coords), max(y_coords)
                        width = max_x - min_x
                        height = max_y - min_y
                        direction = 'horizontal' if width > height else 'vertical'
                        ocr_results_list.append(OCRResult(text, bbox, confidence, direction=direction))
            
            log.info(f"同步OCR识别完成，耗时 {processing_time:.2f}秒，识别到 {len(ocr_results_list)} 个文本区域")

            if file_path_for_cache and page_num_for_cache is not None and ocr_results_list: # Cache if results found
                try:
                    # Generate key using original_archive_path if available for consistency
                    key_path_for_save = original_archive_path if original_archive_path else file_path_for_cache
                    cache_key_to_save = self.ocr_cache_manager.generate_key(
                        file_path=key_path_for_save,
                        page_num=page_num_for_cache
                        # original_archive_path is implicitly handled by generate_key if key_path_for_save is original_archive_path
                    )
                    self.ocr_cache_manager.set(
                        cache_key_to_save,
                        ocr_results_list,
                        file_path=file_path_for_cache, # Actual image path that was OCR'd
                        page_num=page_num_for_cache,
                        original_archive_path=original_archive_path # For DB metadata consistency
                    )
                    log_msg_set = f"同步OCR结果已缓存: 键='{cache_key_to_save}', 实际文件='{file_path_for_cache}', 页码={page_num_for_cache}"
                    if original_archive_path:
                        log_msg_set += f", 原始存档='{original_archive_path}'"
                    log.info(log_msg_set)
                except Exception as e_cache_set:
                    log.error(f"设置OCR缓存时出错 (实际文件: {file_path_for_cache}, 页码: {page_num_for_cache}, 原始存档: {original_archive_path}): {e_cache_set}")

            return ocr_results_list
            
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

    def _on_ocr_finished_simple(self, results: List[OCRResult], file_path: str, page_num: int):
        """OCR完成回调 - 不进行缓存"""
        # file_path and page_num are from OCRWorker but not used here for caching
        log.debug(f"OCR (simple, no cache) finished for {file_path} page {page_num}")
        self.ocr_finished.emit(results) # Emit original signal

    def _on_ocr_finished_and_cache(self, results: List[OCRResult], file_path: str, page_num: int):
        """OCR完成回调，并将结果存入缓存"""
        try:
            if results: # Only cache if there are results
                cache_key = self.ocr_cache_manager.generate_key(file_path, page_num)
                self.ocr_cache_manager.set(cache_key, results, file_path=file_path, page_num=page_num)
                log.info(f"OCR结果已缓存: {file_path} (页码 {page_num})")
            else:
                log.info(f"未识别到OCR结果，不进行缓存: {file_path} (页码 {page_num})")
        except Exception as e:
            log.error(f"缓存OCR结果时出错 (文件: {file_path}, 页码: {page_num}): {e}")
        
        self.ocr_finished.emit(results) # Emit original signal as well
    
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
            
            # 转换为PIL图像并保存
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
            - direction: 文本方向('horizontal' 或 'vertical')
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
                
                # 计算两个框的边界并放大1.1倍
                # 计算合并框的中心点
                merged_center_x = (min(p[0] for p in bbox) + max(p[0] for p in bbox)) / 2
                merged_center_y = (min(p[1] for p in bbox) + max(p[1] for p in bbox)) / 2
                # 计算合并框的宽度和高度并放大1.1倍
                merged_width = (max(p[0] for p in bbox) - min(p[0] for p in bbox)) * 1.1
                merged_height = (max(p[1] for p in bbox) - min(p[1] for p in bbox)) * 1.1
                # 计算放大后的边界
                merged_left = merged_center_x - merged_width / 2
                merged_right = merged_center_x + merged_width / 2
                merged_top = merged_center_y - merged_height / 2
                merged_bottom = merged_center_y + merged_height / 2
                
                # 对原始框也进行同样的处理
                orig_center_x = (min(p[0] for p in orig_bbox) + max(p[0] for p in orig_bbox)) / 2
                orig_center_y = (min(p[1] for p in orig_bbox) + max(p[1] for p in orig_bbox)) / 2
                orig_width = (max(p[0] for p in orig_bbox) - min(p[0] for p in orig_bbox)) * 1.1
                orig_height = (max(p[1] for p in orig_bbox) - min(p[1] for p in orig_bbox)) * 1.1
                orig_left = orig_center_x - orig_width / 2
                orig_right = orig_center_x + orig_width / 2
                orig_top = orig_center_y - orig_height / 2
                orig_bottom = orig_center_y + orig_height / 2
                
                # 检查重叠
                if not (merged_right < orig_left or 
                       merged_left > orig_right or
                       merged_bottom < orig_top or
                       merged_top > orig_bottom):
                    associated_results.append(orig)
                    used_originals.add(id(orig))
            
            # 确定文本方向
            # 使用合并后的文本框尺寸判断方向
            width = max(p[0] for p in bbox) - min(p[0] for p in bbox)
            height = max(p[1] for p in bbox) - min(p[1] for p in bbox)
            direction = 'horizontal' if width > height else 'vertical'
            
            structure = {
                'text': result.text,
                'direction': direction,  # 添加方向信息
                'ocr_results': associated_results if associated_results else [result]
            }
            structured_texts.append(structure)
        
        # 检查是否有未处理的原始结果
        for orig in ocr_results:
            if id(orig) not in used_originals:
                # 计算单个结果的方向
                bbox = orig.bbox
                width = max(p[0] for p in bbox) - min(p[0] for p in bbox)
                height = max(p[1] for p in bbox) - min(p[1] for p in bbox)
                direction = 'horizontal' if width > height else 'vertical'
                
                structure = {
                    'text': orig.text,
                    'direction': direction,  # 添加方向信息
                    'ocr_results': [orig]
                }
                structured_texts.append(structure)
                used_originals.add(id(orig))
        
        return structured_texts

    def filter_numeric_and_symbols(self, ocr_results: List[OCRResult]) -> List[OCRResult]:
        """
        过滤掉纯数字和符号的OCR结果
        
        Args:
            ocr_results: OCR识别结果列表
            
        Returns:
            过滤后的OCR结果列表
        """
        import re
        
        def is_pure_numeric_or_symbol(text: str) -> bool:
            # 移除所有空白字符
            text = ''.join(text.split())
            # 检查是否只包含数字和常见符号
            pattern = r'^[\d\s,.。:：\-_/\\+=\(\)\[\]【】［］（）\{\}]*$'
            return bool(re.match(pattern, text))
        
        filtered_results = [result for result in ocr_results 
                          if not is_pure_numeric_or_symbol(result.text)]
        
        removed_count = len(ocr_results) - len(filtered_results)
        if removed_count > 0:
            log.info(f"过滤纯数字和符号文本: {len(ocr_results)} -> {len(filtered_results)} "
                    f"(移除了 {removed_count} 个纯数字/符号文本)")
        
        return filtered_results