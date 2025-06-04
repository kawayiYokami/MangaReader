# core/image_translator.py
import os
import cv2
import numpy as np
from typing import Optional, Dict, Any, Union, List
from pathlib import Path

from core.ocr_manager import OCRManager, OCRResult
from core.translator import TranslatorFactory, ZhipuTranslator, GoogleDeepTranslator
from core.manga_text_replacer import MangaTextReplacer
from core.config import config
from utils import manga_logger as log
from core.harmonization_map_manager import get_harmonization_map_manager_instance


class ImageTranslator:
    """图片翻译器 - 提供完整的图片翻译功能"""
    
    def __init__(self, translator_type: Optional[str] = None, **translator_kwargs):
        """
        初始化图片翻译器
        
        Args:
            translator_type: 翻译器类型 ("智谱", "Google"). 如果为 None, 则从全局配置加载。
            **translator_kwargs: 翻译器相关参数
                - 智谱: api_key, model
                - Google: api_key (可选)
        """
        self.ocr_manager = None
        self.translator = None 
        self.harmonization_manager = None
        self.manga_text_replacer = None
        
        self._init_ocr_manager()
        self._init_translator(translator_type if translator_type is not None else config.translator_type.value, **translator_kwargs)
        self._init_manga_text_replacer()
        self._init_harmonization_manager()
        
        log.info(f"ImageTranslator 初始化完成，尝试使用翻译器: {self.translator.__class__.__name__ if self.translator else 'None'}")
    
    def _init_ocr_manager(self):
        """初始化OCR管理器"""
        try:
            self.ocr_manager = OCRManager()
            self.ocr_manager.load_model()
            log.info("OCR管理器初始化成功")
        except Exception as e:
            log.error(f"OCR管理器初始化失败: {e}")
            raise RuntimeError(f"OCR管理器初始化失败: {e}")
    
    def _init_translator(self, translator_type_to_init: str, **kwargs):
        """
        初始化翻译器。
        Args:
            translator_type_to_init: 要初始化的翻译器类型。
            **kwargs: 传递给 TranslatorFactory 的参数。
        """
        try:
            log.info(f"尝试初始化翻译器类型: {translator_type_to_init}，参数: {kwargs}")
            if translator_type_to_init == "智谱":
                api_key = kwargs.get('api_key', config.zhipu_api_key.value)
                model = kwargs.get('model', config.zhipu_model.value)
                if not api_key:
                    log.warning("智谱翻译器 API Key 未在配置中找到。如果这是预期的翻译器，翻译将会失败。")
                self.translator = TranslatorFactory.create_translator(
                    translator_type="智谱",
                    api_key=api_key,
                    model=model
                )
            elif translator_type_to_init == "Google":
                api_key = kwargs.get('api_key', config.google_api_key.value)
                self.translator = TranslatorFactory.create_translator(
                    translator_type="Google",
                    api_key=api_key
                )

            else:
                log.error(f"不支持的翻译器类型: {translator_type_to_init}。将尝试使用默认Google翻译器。")
                self.translator = TranslatorFactory.create_translator(translator_type="Google")

            log.info(f"翻译器实际初始化为: {self.translator.__class__.__name__ if self.translator else 'None'}")

        except Exception as e:
            log.error(f"初始化翻译器 '{translator_type_to_init}' 失败: {e}")
            if self.translator is None and translator_type_to_init != "Google": 
                try:
                    log.warning("尝试回退到 Google 翻译器...")
                    self.translator = TranslatorFactory.create_translator(translator_type="Google")
                    log.info(f"已成功回退到 Google 翻译器: {self.translator.__class__.__name__}")
                except Exception as fallback_e:
                    log.error(f"回退到 Google 翻译器失败: {fallback_e}")
                    self.translator = None 
                    raise RuntimeError(f"翻译器初始化失败 ({translator_type_to_init}) 且无法回退: {e}")
            elif self.translator is None: 
                 self.translator = None
                 raise RuntimeError(f"翻译器初始化失败 ({translator_type_to_init}): {e}")
    
    def _init_manga_text_replacer(self):
        """初始化漫画文本替换器"""
        try:
            self.manga_text_replacer = MangaTextReplacer()
            log.info("漫画文本替换器初始化成功")
        except Exception as e:
            log.error(f"漫画文本替换器初始化失败: {e}")
            raise RuntimeError(f"漫画文本替换器初始化失败: {e}")

    def _init_harmonization_manager(self):
        """初始化和谐映射管理器"""
        try:
            self.harmonization_manager = get_harmonization_map_manager_instance()
            log.info("和谐映射管理器初始化成功")
        except Exception as e:
            log.error(f"和谐映射管理器初始化失败: {e}")
            self.harmonization_manager = None # Ensure it's None on failure
    
    def is_ready(self) -> bool:
        """检查翻译器是否准备就绪"""
        return (self.ocr_manager and self.ocr_manager.is_ready() and 
                self.translator and 
                self.manga_text_replacer and
                self.harmonization_manager)
    
    def translate_image(self,
                       image_input: Union[str, np.ndarray],
                       target_language: str = "zh",
                       output_path: Optional[str] = None,
                       save_original: bool = False,
                       ocr_options: Optional[Dict[str, Any]] = None,
                       file_path_for_cache: Optional[str] = None,
                       page_num_for_cache: Optional[int] = None,
                       original_archive_path_for_cache: Optional[str] = None) -> np.ndarray:
        """
        翻译图片中的文字
        """
        if not self.is_ready():
            log.warning("ImageTranslator 未准备就绪，尝试根据当前配置重新初始化翻译器...")
            try:
                self._init_translator(config.translator_type.value) 
                if not self.is_ready(): # Re-check after attempting re-init
                     raise RuntimeError("图片翻译器仍未准备就绪，请检查各组件初始化状态和配置。")
            except Exception as reinit_e:
                 raise RuntimeError(f"图片翻译器未准备就绪，重新初始化翻译器失败: {reinit_e}")

        current_file_path_for_cache = file_path_for_cache
        image_data: Optional[np.ndarray] = None 
        
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"图片文件不存在: {image_input}")
            try:
                image_data = cv2.imdecode(np.fromfile(image_input, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image_data is None:
                    raise ValueError(f"无法读取图片文件: {image_input}")
                log.info(f"已加载图片: {image_input}")
                if current_file_path_for_cache is None:
                    current_file_path_for_cache = image_input
            except Exception as e:
                raise ValueError(f"读取图片文件失败: {image_input}, 错误: {e}")
        elif isinstance(image_input, np.ndarray):
            image_data = image_input.copy()
            log.info("已加载图片数据")
        else:
            raise ValueError("image_input必须是文件路径或numpy数组")
        
        if image_data is None: 
            raise RuntimeError("无法加载图片数据，image_data 为 None")
            
        if save_original and output_path:
            original_path = self._get_original_path(output_path)
            original_path_webp = str(Path(original_path).with_suffix('.webp'))
            if self._save_image(image_data, original_path_webp):
                log.info(f"原图已保存: {original_path_webp}")
            else:
                log.warning(f"原图保存失败: {original_path_webp}")
        
        try:
            log.info("开始OCR识别...")
            ocr_results: List[OCRResult]
            if ocr_options and ocr_options.get("reuse_results") and "results" in ocr_options:
                ocr_results = ocr_options["results"]
                log.info(f"复用提供的 {len(ocr_results)} 个OCR结果")
            else:
                ocr_results = self.ocr_manager.recognize_image_data_sync(
                    image_data,
                    file_path_for_cache=current_file_path_for_cache,
                    page_num_for_cache=page_num_for_cache,
                    original_archive_path=original_archive_path_for_cache,
                    options=ocr_options
                )

            if not ocr_results:
                log.warning("未识别到任何文本")
                return image_data 
            
            log.info(f"OCR识别完成，识别到 {len(ocr_results)} 个原始文本区域")
            
            ocr_results = self.ocr_manager.filter_numeric_and_symbols(ocr_results)
            
            filtered_ocr_results = self.ocr_manager.filter_by_confidence(ocr_results, config.ocr_confidence_threshold.value)

            structured_texts: List[OCRResult] = self.ocr_manager.get_structured_text(filtered_ocr_results)

            log.info(f"获取到 {len(structured_texts)} 个结构化文本块 (OCRResult)")
            
            # Apply harmonization before translation
            texts_to_translate_mapping = {} # Stores original_text -> text_for_translation
            actual_texts_for_api = []

            if self.harmonization_manager:
                log.info("应用和谐化规则...")
                for item_ocr_result in structured_texts: 
                    original_text = item_ocr_result.text.strip()
                    if not original_text:
                        continue
                    harmonized_text = self.harmonization_manager.apply_mapping_to_text(original_text)
                    texts_to_translate_mapping[original_text] = harmonized_text
                    actual_texts_for_api.append(harmonized_text)
                    if original_text != harmonized_text:
                        log.debug(f"和谐化: '{original_text}' -> '{harmonized_text}'")
            else: # Fallback if harmonization_manager is None (e.g. init failed)
                log.warning("和谐化管理器未初始化，跳过和谐化步骤。")
                for item_ocr_result in structured_texts:
                    original_text = item_ocr_result.text.strip()
                    if not original_text:
                        continue
                    texts_to_translate_mapping[original_text] = original_text
                    actual_texts_for_api.append(original_text)

            if not actual_texts_for_api: 
                log.info("和谐化后没有需要翻译的文本块。")
                return image_data 

            log.info(f"开始翻译 (使用 {self.translator.__class__.__name__ if self.translator else '未知翻译器'})...")
            api_translations: List[str] = []
            
            if isinstance(self.translator, ZhipuTranslator):
                log.info(f"使用智谱翻译器批量翻译 {len(actual_texts_for_api)} 个文本块...")
                if not self.translator.api_key: 
                    log.error("智谱翻译器 API Key 未配置，无法进行翻译。将返回原文。")
                    api_translations = actual_texts_for_api # Use harmonized (or original if no harmonization)
                else:
                    api_translations = self.translator.translate_batch(actual_texts_for_api, target_lang=target_language)
            else: 
                log.info(f"使用 {self.translator.__class__.__name__ if self.translator else '未知翻译器'} 翻译器逐个翻译 {len(actual_texts_for_api)} 个文本块...")
                for text_for_api in actual_texts_for_api:
                    try:
                        translated = self.translator.translate(text_for_api, target_lang=target_language)
                        api_translations.append(translated)
                        log.debug(f"翻译API输入: '{text_for_api}' -> '{translated}'")
                    except Exception as e:
                        log.error(f"翻译失败: {text_for_api}, 错误: {e}")
                        api_translations.append(text_for_api) # Return text_for_api (harmonized or original) on error
            
            # Map translations back to original OCR texts
            final_translations_map: Dict[str, str] = {}
            original_texts_ordered = [ot for ot in texts_to_translate_mapping.keys()] # Maintain order

            if len(original_texts_ordered) != len(api_translations):
                log.error(f"翻译结果数量 ({len(api_translations)}) 与原始文本数量 ({len(original_texts_ordered)}) 不匹配。将尝试部分匹配或返回原文。")
                # Fallback: try to map what we can, or use original (harmonized) text
                for i, original_key in enumerate(original_texts_ordered):
                    final_translations_map[original_key] = api_translations[i] if i < len(api_translations) else texts_to_translate_mapping[original_key]
            else:
                for original_key, translated_text in zip(original_texts_ordered, api_translations):
                    final_translations_map[original_key] = translated_text
            
            log.info(f"翻译完成，共处理 {len(final_translations_map)} 个文本块的映射")
            
            log.info("开始文本替换...")
            result_image = self.manga_text_replacer.process_manga_image(
                image_data,
                structured_texts, 
                final_translations_map, 
                target_language=target_language,
                inpaint_background=True 
            )
            
            log.info("文本替换完成")
            
            if output_path:
                output_path_webp = str(Path(output_path).with_suffix('.webp'))
                if self._save_image(result_image, output_path_webp):
                    log.info(f"翻译结果已保存: {output_path_webp}")
                else:
                    log.error(f"保存翻译结果失败: {output_path_webp}")
            
            return result_image
            
        except Exception as e:
            log.error(f"图片翻译过程中发生错误: {e}")
            import traceback
            log.error(traceback.format_exc()) 
            raise RuntimeError(f"图片翻译失败: {e}")
    
    def translate_image_simple(self, 
                              image_path: str,
                              output_dir: str = "output",
                              target_language: str = "zh") -> str:
        """
        简化的图片翻译接口
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        input_path = Path(image_path)
        output_filename = f"{input_path.stem}_translated_{target_language}.webp"
        output_path = os.path.join(output_dir, output_filename)
        
        translated_image_data = self.translate_image( 
            image_input=image_path,
            target_language=target_language,
            output_path=output_path, 
            save_original=True
        )
        return output_path
    
    def batch_translate_images(self,
                              input_dir: str,
                              output_dir: str = "output",
                              target_language: str = "zh",
                              image_extensions: List[str] = None) -> List[str]:
        """
        批量翻译图片
        """
        if image_extensions is None:
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
        
        if not os.path.exists(input_dir):
            raise FileNotFoundError(f"输入目录不存在: {input_dir}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        image_files = []
        for ext in image_extensions:
            pattern = f"*{ext}"
            image_files.extend(Path(input_dir).glob(pattern))
            image_files.extend(Path(input_dir).glob(pattern.upper()))
        
        if not image_files:
            log.warning(f"在目录 {input_dir} 中未找到图片文件")
            return []
        
        log.info(f"找到 {len(image_files)} 个图片文件，开始批量翻译...")
        
        output_paths = []
        for i, image_file_path_obj in enumerate(image_files, 1): 
            try:
                log.info(f"处理第 {i}/{len(image_files)} 个文件: {image_file_path_obj.name}")
                output_path = self.translate_image_simple(
                    str(image_file_path_obj), 
                    output_dir,
                    target_language
                )
                output_paths.append(output_path)
                log.info(f"完成: {image_file_path_obj.name} -> {os.path.basename(output_path)}")
            except Exception as e:
                log.error(f"处理文件 {image_file_path_obj.name} 时发生错误: {e}")
                continue 
        
        log.info(f"批量翻译完成，成功处理 {len(output_paths)}/{len(image_files)} 个文件")
        return output_paths
    
    def batch_translate_images_optimized(self,
                                 image_inputs: List[Union[str, np.ndarray]],
                                 output_paths: Optional[List[str]] = None,
                                 target_language: str = "zh",
                                 file_paths_for_cache: Optional[List[str]] = None,
                                 page_nums_for_cache: Optional[List[int]] = None,
                                 original_archive_paths_for_cache: Optional[List[Optional[str]]] = None) -> List[np.ndarray]:
        """
        优化的批量翻译功能，一次性处理所有图片的 OCR 和翻译
        """
        if not self.is_ready():
            log.warning("ImageTranslator 未准备就绪 (optimized)，尝试根据当前配置重新初始化翻译器...")
            try:
                self._init_translator(config.translator_type.value)
                if not self.is_ready():
                     raise RuntimeError("图片翻译器仍未准备就绪 (optimized)，请检查各组件初始化状态和配置。")
            except Exception as reinit_e:
                 raise RuntimeError(f"图片翻译器未准备就绪 (optimized)，重新初始化翻译器失败: {reinit_e}")

        images_data: List[np.ndarray] = [] 
        actual_file_paths_for_cache: List[Optional[str]] = [] 

        for i, img_input in enumerate(image_inputs):
            current_file_path: Optional[str] = None 
            img_data_single: Optional[np.ndarray] = None 

            if isinstance(img_input, str):
                if not os.path.exists(img_input):
                    raise FileNotFoundError(f"图片文件不存在: {img_input}")
                img_data_single = cv2.imdecode(np.fromfile(img_input, dtype=np.uint8), cv2.IMREAD_COLOR)
                if img_data_single is None:
                    raise ValueError(f"无法读取图片文件: {img_input}")
                current_file_path = img_input
            elif isinstance(img_input, np.ndarray):
                img_data_single = img_input.copy()
                if file_paths_for_cache and i < len(file_paths_for_cache):
                    current_file_path = file_paths_for_cache[i]
            else:
                raise ValueError("image_input必须是文件路径或numpy数组")
            
            if img_data_single is None: 
                raise RuntimeError(f"无法加载第 {i+1} 张图片数据")

            images_data.append(img_data_single)
            actual_file_paths_for_cache.append(current_file_path)
        
        log.info(f"已加载 {len(images_data)} 张图片 (optimized)")
        
        final_file_paths_for_cache = actual_file_paths_for_cache
        if file_paths_for_cache and len(file_paths_for_cache) == len(images_data):
            final_file_paths_for_cache = file_paths_for_cache
        elif file_paths_for_cache: 
             log.warning("提供的 file_paths_for_cache 长度与 image_inputs 不匹配，将使用从 image_inputs 推断的路径。")

        final_page_nums_for_cache = [None] * len(images_data)
        if page_nums_for_cache and len(page_nums_for_cache) == len(images_data):
            final_page_nums_for_cache = page_nums_for_cache
        elif page_nums_for_cache:
            log.warning("提供的 page_nums_for_cache 长度与 image_inputs 不匹配，将不使用页码缓存。")

        final_original_archive_paths_for_cache = [None] * len(images_data)
        if original_archive_paths_for_cache and len(original_archive_paths_for_cache) == len(images_data):
            final_original_archive_paths_for_cache = original_archive_paths_for_cache
        elif original_archive_paths_for_cache:
            log.warning("提供的 original_archive_paths_for_cache 长度与 image_inputs 不匹配，将不使用原始存档路径缓存。")


        try:
            log.info("开始批量 OCR 识别 (optimized)...")
            all_ocr_results_per_page: List[List[OCRResult]] = [] 
            all_structured_texts_per_page: List[List[OCRResult]] = [] 
            
            for i, img_data_item in enumerate(images_data):
                current_fp_cache = final_file_paths_for_cache[i]
                current_pn_cache = final_page_nums_for_cache[i]
                current_oa_cache = final_original_archive_paths_for_cache[i]

                ocr_results_page = self.ocr_manager.recognize_image_data_sync(
                    img_data_item,
                    file_path_for_cache=current_fp_cache,
                    page_num_for_cache=current_pn_cache,
                    original_archive_path=current_oa_cache
                )
                if not ocr_results_page:
                    log_message = f"图片 {i+1} (optimized) 未识别到任何文本 (文件: {current_fp_cache or 'N/A'}, 页码: {current_pn_cache if current_pn_cache is not None else 'N/A'}"
                    if current_oa_cache: log_message += f", 原始存档: {current_oa_cache}"
                    log_message += ")"
                    log.warning(log_message)
                    all_ocr_results_per_page.append([])
                    all_structured_texts_per_page.append([])
                    continue
                
                filtered_results_page = self.ocr_manager.filter_numeric_and_symbols(ocr_results_page)
                filtered_results_page = [r for r in filtered_results_page if r.confidence >= config.ocr_confidence_threshold.value]
                
                structured_texts_page: List[OCRResult] = self.ocr_manager.get_structured_text(filtered_results_page)
                
                all_ocr_results_per_page.append(filtered_results_page) 
                all_structured_texts_per_page.append(structured_texts_page)
                log.info(f"图片 {i+1} (optimized) OCR 识别完成，识别到 {len(structured_texts_page)} 个结构化文本块 (OCRResult)")
            
            # Apply harmonization before bulk translation
            unique_original_texts = set()
            for structured_texts_page_item in all_structured_texts_per_page: 
                for item_ocr_result in structured_texts_page_item: 
                    text = item_ocr_result.text.strip() 
                    if text:
                        unique_original_texts.add(text)
            
            texts_to_translate_mapping_optimized = {} # original_text -> harmonized_text
            actual_texts_for_api_optimized = []

            if self.harmonization_manager:
                log.info("应用和谐化规则 (optimized)...")
                for original_text in unique_original_texts:
                    harmonized_text = self.harmonization_manager.apply_mapping_to_text(original_text)
                    texts_to_translate_mapping_optimized[original_text] = harmonized_text
                    actual_texts_for_api_optimized.append(harmonized_text)
                    if original_text != harmonized_text:
                        log.debug(f"和谐化 (optimized): '{original_text}' -> '{harmonized_text}'")
            else:
                log.warning("和谐化管理器未初始化 (optimized)，跳过和谐化步骤。")
                for original_text in unique_original_texts:
                    texts_to_translate_mapping_optimized[original_text] = original_text
                    actual_texts_for_api_optimized.append(original_text)

            log.info(f"开始批量翻译 {len(actual_texts_for_api_optimized)} 个唯一（可能已和谐化）文本 (使用 {self.translator.__class__.__name__ if self.translator else '未知翻译器'} optimized)...")
            
            api_translations_optimized: List[str] = []
            if actual_texts_for_api_optimized: 
                if isinstance(self.translator, ZhipuTranslator):
                    if not self.translator.api_key:
                        log.error("智谱翻译器 API Key 未配置 (optimized)，无法进行翻译。将返回原文。")
                        api_translations_optimized = actual_texts_for_api_optimized
                    else:
                        translated_results = self.translator.translate_batch(actual_texts_for_api_optimized, target_lang=target_language)
                        api_translations_optimized = translated_results if translated_results else actual_texts_for_api_optimized
                else: 
                    for text_for_api in actual_texts_for_api_optimized:
                        try:
                            translated = self.translator.translate(text_for_api, target_lang=target_language)
                            api_translations_optimized.append(translated)
                        except Exception as e_trans:
                            log.error(f"翻译失败 (optimized): {text_for_api}, 错误: {e_trans}")
                            api_translations_optimized.append(text_for_api) 
            
            # Map translations back to original unique OCR texts
            bulk_translations_map: Dict[str, str] = {} 
            unique_original_texts_list = list(unique_original_texts) # Keep order for zipping if needed

            if len(unique_original_texts_list) != len(api_translations_optimized):
                log.error(f"优化批量翻译结果数量 ({len(api_translations_optimized)}) 与唯一原始文本数量 ({len(unique_original_texts_list)}) 不匹配。")
                # Fallback: try to map what we can
                for i, original_key in enumerate(unique_original_texts_list):
                    bulk_translations_map[original_key] = api_translations_optimized[i] if i < len(api_translations_optimized) else texts_to_translate_mapping_optimized.get(original_key, original_key)
            else:
                for i, original_key in enumerate(unique_original_texts_list):
                    # The key for bulk_translations_map should be the *original* unique text
                    # The value is the translation of its (potentially) harmonized version
                    bulk_translations_map[original_key] = api_translations_optimized[i]

            log.info("批量翻译完成 (optimized)")
            
            final_result_images: List[np.ndarray] = [] 
            for page_idx, (img_data_item, structured_texts_page_item) in enumerate(zip(images_data, all_structured_texts_per_page)):
                
                page_specific_translations: Dict[str, str] = {}
                for ocr_item in structured_texts_page_item:
                    original_ocr_text = ocr_item.text.strip()
                    if original_ocr_text:
                        # Get the translation from the bulk map, using original_ocr_text as key
                        page_specific_translations[original_ocr_text] = bulk_translations_map.get(original_ocr_text, original_ocr_text)

                if not structured_texts_page_item: # or not page_specific_translations if only considering translated items
                    log.info(f"图片 {page_idx+1} (optimized) 没有文本进行替换，使用原图。")
                    final_result_images.append(img_data_item)
                    if output_paths and page_idx < len(output_paths) and output_paths[page_idx]:
                        output_path_webp = str(Path(output_paths[page_idx]).with_suffix('.webp'))
                        if self._save_image(img_data_item, output_path_webp):
                            log.info(f"图片 {page_idx+1} (optimized) 原图已保存: {output_path_webp}")
                        else:
                            log.error(f"图片 {page_idx+1} (optimized) 保存原图失败: {output_path_webp}")
                    continue

                log.info(f"开始文本替换 for page {page_idx+1} (optimized)...")
                result_image_page = self.manga_text_replacer.process_manga_image(
                    img_data_item,
                    structured_texts_page_item, 
                    page_specific_translations, 
                    target_language=target_language,
                    inpaint_background=True
                )
                final_result_images.append(result_image_page)
                log.info(f"文本替换完成 for page {page_idx+1} (optimized)")

                if output_paths and page_idx < len(output_paths) and output_paths[page_idx]:
                    output_path_webp = str(Path(output_paths[page_idx]).with_suffix('.webp'))
                    if self._save_image(result_image_page, output_path_webp):
                        log.info(f"翻译结果已保存 for page {page_idx+1} (optimized): {output_path_webp}")
                    else:
                        log.error(f"保存翻译结果失败 for page {page_idx+1} (optimized): {output_path_webp}")
            
            return final_result_images
        except Exception as e:
            log.error(f"批量图片翻译过程中发生错误 (optimized): {e}")
            import traceback
            log.error(traceback.format_exc())
            raise RuntimeError(f"批量图片翻译失败 (optimized): {e}")

    def get_ocr_results(self,
                       image_input: Union[str, np.ndarray],
                       file_path_for_cache: Optional[str] = None,
                       page_num_for_cache: Optional[int] = None,
                       original_archive_path_for_cache: Optional[str] = None,
                       options: Optional[Dict[str, Any]] = None) -> List[OCRResult]:
        """获取指定图片的原始OCR识别结果 (结构化文本)"""
        if not self.ocr_manager or not self.ocr_manager.is_ready():
            raise RuntimeError("OCR管理器未准备就绪")

        image_data: Optional[np.ndarray] = None
        current_file_path_for_cache = file_path_for_cache

        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"图片文件不存在: {image_input}")
            try:
                image_data = cv2.imdecode(np.fromfile(image_input, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image_data is None:
                    raise ValueError(f"无法读取图片文件: {image_input}")
                if current_file_path_for_cache is None:
                    current_file_path_for_cache = image_input
            except Exception as e:
                raise ValueError(f"读取图片文件失败: {image_input}, 错误: {e}")
        elif isinstance(image_input, np.ndarray):
            image_data = image_input.copy()
        else:
            raise ValueError("image_input必须是文件路径或numpy数组")
        
        if image_data is None:
            raise RuntimeError("无法加载图片数据")

        ocr_results = self.ocr_manager.recognize_image_data_sync(
            image_data,
            file_path_for_cache=current_file_path_for_cache,
            page_num_for_cache=page_num_for_cache,
            original_archive_path=original_archive_path_for_cache,
            options=options
        )
        filtered_results = self.ocr_manager.filter_numeric_and_symbols(ocr_results)
        filtered_results = self.ocr_manager.filter_by_confidence(filtered_results, config.ocr_confidence_threshold.value)
        structured_texts = self.ocr_manager.get_structured_text(filtered_results)
        return structured_texts

    def translate_text(self, text: str, target_language: str = "zh") -> str:
        """直接翻译文本 (主要用于测试或独立文本翻译)"""
        if not self.translator:
            log.warning("翻译器未初始化，尝试根据当前配置重新初始化...")
            try:
                self._init_translator(config.translator_type.value)
                if not self.translator:
                    raise RuntimeError("翻译器仍未初始化")
            except Exception as e:
                raise RuntimeError(f"翻译器初始化失败: {e}")
        
        # Apply harmonization if manager is available
        text_to_translate = text
        if self.harmonization_manager:
            text_to_translate = self.harmonization_manager.apply_mapping_to_text(text)
            if text != text_to_translate:
                log.debug(f"文本和谐化: '{text}' -> '{text_to_translate}'")
        
        return self.translator.translate(text_to_translate, target_lang=target_language)

    def _get_original_path(self, output_path: str) -> str:
        p = Path(output_path)
        return str(p.with_name(f"{p.stem}_original{p.suffix}"))

    def _check_image_file(self, file_path: str) -> bool:
        """检查图片文件是否有效"""
        if not os.path.exists(file_path):
            log.error(f"图片文件不存在: {file_path}")
            return False
        try:
            img = cv2.imdecode(np.fromfile(file_path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if img is None:
                log.error(f"无法解码图片文件 (可能已损坏或格式不支持): {file_path}")
                return False
            return True
        except Exception as e:
            log.error(f"检查图片文件时发生错误: {file_path}, {e}")
            return False

    def _save_image(self, image: np.ndarray, file_path: str) -> bool:
        """使用imencode将图片保存为WebP格式，支持Unicode文件名。 """
        try:
            # 确保目录存在
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            # 对于WebP，通常需要有损或无损质量参数
            # OpenCV的WebP支持可能依赖于构建时的库
            # imwrite 通常处理路径编码问题更好一些，但imencode提供了更多控制
            
            # 尝试使用 imwrite，它对路径处理更健壮
            # cv2.imwrite(file_path, image, [cv2.IMWRITE_WEBP_QUALITY, 90]) # Example quality
            
            # 使用 fromfile/imdecode 的逆过程 tofile/imencode
            ext = Path(file_path).suffix.lower()
            encode_params = []
            if ext == ".webp":
                encode_params = [cv2.IMWRITE_WEBP_QUALITY, 90] # 0-100, 90 is good quality
            elif ext in [".jpg", ".jpeg"]:
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, 90]
            elif ext == ".png":
                encode_params = [cv2.IMWRITE_PNG_COMPRESSION, 3] # 0-9, 3 is default
                
            result, buf = cv2.imencode(ext, image, encode_params)
            if result:
                with open(file_path, 'wb') as f:
                    f.write(buf)
                return True
            else:
                log.error(f"图片编码失败: {file_path}")
                # Fallback to imwrite if imencode fails, though imwrite might also fail for same reasons
                # cv2.imwrite(file_path, image) # This might not handle unicode paths well on all systems
                return False
        except Exception as e:
            log.error(f"保存图片时发生错误: {file_path}, {e}")
            return False

def create_image_translator(translator_type: Optional[str] = None, **kwargs) -> ImageTranslator:
    """
    工厂函数，用于创建 ImageTranslator 实例。
    简化 ImageTranslator 的创建过程。
    """
    try:
        return ImageTranslator(translator_type=translator_type, **kwargs)
    except Exception as e:
        log.error(f"创建 ImageTranslator 实例失败: {e}")
        raise # Re-raise the exception so the caller knows it failed
