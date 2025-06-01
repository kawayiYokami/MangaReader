#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
图片翻译处理模块
整合OCR识别、翻译和文本替换功能，提供简单的图片翻译接口
"""

import os
import cv2
import numpy as np
from typing import Optional, Dict, Any, Union, List
from pathlib import Path

from core.ocr_manager import OCRManager, OCRResult
from core.translator import TranslatorFactory
from core.manga_text_replacer import MangaTextReplacer, create_manga_translation_dict
from core.config import config
from utils import manga_logger as log


class ImageTranslator:
    """图片翻译器 - 提供完整的图片翻译功能"""
    
    def __init__(self, translator_type: str = "Google", **translator_kwargs):
        """
        初始化图片翻译器
        
        Args:
            translator_type: 翻译器类型 ("智谱" 或 "Google")
            **translator_kwargs: 翻译器相关参数
                - 智谱: api_key, model
                - Google: api_key (可选)
        """
        self.ocr_manager = None
        self.translator = None
        self.manga_text_replacer = None
        
        # 初始化各个组件
        self._init_ocr_manager()
        self._init_translator(translator_type, **translator_kwargs)
        self._init_manga_text_replacer()
        
        log.info(f"ImageTranslator初始化完成，使用翻译器: {translator_type}")
    
    def _init_ocr_manager(self):
        """初始化OCR管理器"""
        try:
            self.ocr_manager = OCRManager()
            self.ocr_manager.load_model()
            log.info("OCR管理器初始化成功")
        except Exception as e:
            log.error(f"OCR管理器初始化失败: {e}")
            raise RuntimeError(f"OCR管理器初始化失败: {e}")
    
    def _init_translator(self, translator_type: str, **kwargs):
        """初始化翻译器"""
        try:
            if translator_type == "智谱":
                api_key = kwargs.get('api_key') or config.zhipu_api_key.value
                model = kwargs.get('model') or config.zhipu_model.value
                if not api_key:
                    raise ValueError("智谱翻译器需要API密钥")
                self.translator = TranslatorFactory.create_translator(
                    translator_type="智谱",
                    api_key=api_key,
                    model=model
                )
            elif translator_type == "Google":
                api_key = kwargs.get('api_key') or config.google_api_key.value
                self.translator = TranslatorFactory.create_translator(
                    translator_type="Google",
                    api_key=api_key
                )
            else:
                raise ValueError(f"不支持的翻译器类型: {translator_type}，仅支持'智谱'和'Google'")
            
            log.info(f"翻译器初始化成功: {translator_type}")
        except Exception as e:
            log.error(f"翻译器初始化失败: {e}")
            raise RuntimeError(f"翻译器初始化失败: {e}")
    
    def _init_manga_text_replacer(self):
        """初始化漫画文本替换器"""
        try:
            self.manga_text_replacer = MangaTextReplacer()
            log.info("漫画文本替换器初始化成功")
        except Exception as e:
            log.error(f"漫画文本替换器初始化失败: {e}")
            raise RuntimeError(f"漫画文本替换器初始化失败: {e}")
    
    def is_ready(self) -> bool:
        """检查翻译器是否准备就绪"""
        return (self.ocr_manager and self.ocr_manager.is_ready() and 
                self.translator and self.manga_text_replacer)
    
    def translate_image(self, 
                       image_input: Union[str, np.ndarray],
                       target_language: str = "zh",
                       output_path: Optional[str] = None,
                       save_original: bool = False,
                       ocr_options: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """
        翻译图片中的文字
        
        Args:
            image_input: 输入图片路径或图片数据(numpy数组)
            target_language: 目标语言代码 ("zh", "en", "ja", "ko"等)
            output_path: 输出图片路径(可选)
            save_original: 是否保存原图副本
            ocr_options: OCR选项
            
        Returns:
            翻译后的图片数据(numpy数组)
            
        Raises:
            RuntimeError: 当组件未准备就绪或处理失败时
        """
        if not self.is_ready():
            raise RuntimeError("图片翻译器未准备就绪，请检查各组件初始化状态")
        
        # 1. 加载图片
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"图片文件不存在: {image_input}")
            
            # 处理文件路径编码问题
            try:
                # 使用imdecode直接读取，支持Unicode路径
                image_data = cv2.imdecode(np.fromfile(image_input, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image_data is None:
                    raise ValueError(f"无法读取图片文件: {image_input}")
                    
                log.info(f"已加载图片: {image_input}")
            except Exception as e:
                raise ValueError(f"读取图片文件失败: {image_input}, 错误: {e}")
                
        elif isinstance(image_input, np.ndarray):
            image_data = image_input.copy()
            log.info("已加载图片数据")
        else:
            raise ValueError("image_input必须是文件路径或numpy数组")
        
        # 保存原图副本
        if save_original and output_path:
            original_path = self._get_original_path(output_path)
            if self._save_image(image_data, original_path):
                log.info(f"原图已保存: {original_path}")
            else:
                log.warning(f"原图保存失败: {original_path}")
        
        try:
            # 2. OCR识别
            log.info("开始OCR识别...")
            ocr_results = self.ocr_manager.recognize_image_data_sync(
                image_data, options=ocr_options
            )
            
            if not ocr_results:
                log.warning("未识别到任何文本")
                return image_data
            
            log.info(f"OCR识别完成，识别到 {len(ocr_results)} 个文本区域")
            
            # 过滤纯数字和符号的文本
            ocr_results = self.ocr_manager.filter_numeric_and_symbols(ocr_results)
            
            # 过滤低置信度的 OCR 结果
            filtered_ocr_results = [
                result for result in ocr_results 
                if result.confidence >= 0.75
            ]
            
            if len(filtered_ocr_results) < len(ocr_results):
                log.info(f"过滤掉 {len(ocr_results) - len(filtered_ocr_results)} 个低置信度的文本区域")
            
            if not filtered_ocr_results:
                log.warning("过滤后没有置信度足够高的文本区域")
                return image_data
            
            # 3. 获取结构化文本
            structured_texts = self.ocr_manager.get_structured_text(filtered_ocr_results)
            log.info(f"获取到 {len(structured_texts)} 个结构化文本块")
            
            # 4. 翻译文本
            log.info("开始翻译...")
            translations = {}
            texts_to_translate = []
            original_text_map = {}  # 用于记录原文和结构化文本的对应关系
            
            # 收集需要翻译的文本
            for i, item in enumerate(structured_texts):
                full_text = item['text']
                if not full_text.strip():
                    continue
                texts_to_translate.append(full_text)
                original_text_map[full_text] = item
            
            # 根据翻译器类型选择翻译方式
            if isinstance(self.translator, TranslatorFactory.create_translator("智谱").__class__):
                # 使用智谱翻译器的批量翻译功能
                log.info(f"使用智谱翻译器批量翻译 {len(texts_to_translate)} 个文本块...")
                translated_texts = self.translator.translate_batch(texts_to_translate, target_lang=target_language)
                
                # 将翻译结果添加到映射
                for original, translated in zip(texts_to_translate, translated_texts):
                    translations[original] = translated
                    
                    # 更新相关OCR结果的翻译文本
                    item = original_text_map[original]
                    for ocr_result in item['ocr_results']:
                        ocr_result.translated_text = translated
                    
                    log.debug(f"翻译: '{original}' -> '{translated}'")
            else:
                # 使用其他翻译器逐个翻译
                for full_text in texts_to_translate:
                    try:
                        translated = self.translator.translate(full_text, target_lang=target_language)
                        translations[full_text] = translated
                        
                        # 更新相关OCR结果的翻译文本
                        item = original_text_map[full_text]
                        for ocr_result in item['ocr_results']:
                            ocr_result.translated_text = translated
                            
                        log.debug(f"翻译: '{full_text}' -> '{translated}'")
                    except Exception as e:
                        log.error(f"翻译失败: {full_text}, 错误: {e}")
                        translations[full_text] = full_text  # 翻译失败时使用原文
            
            log.info(f"翻译完成，共翻译 {len(translations)} 个文本块")
            
            # 5. 创建翻译字典，将翻译结果按原顺序排列
            translated_texts = [translations.get(item['text'], item['text']) for item in structured_texts]
            translation_dict = create_manga_translation_dict(structured_texts, translated_texts)
            
            # 6. 文本替换
            log.info("开始文本替换...")
            result_image = self.manga_text_replacer.process_manga_image(
                image_data,
                structured_texts,
                translation_dict,
                target_language=target_language,
                inpaint_background=True
            )
            
            log.info("文本替换完成")
            
            # 7. 保存结果
            if output_path:
                if self._save_image(result_image, output_path):
                    log.info(f"翻译结果已保存: {output_path}")
                else:
                    log.error(f"保存翻译结果失败: {output_path}")
            
            return result_image
            
        except Exception as e:
            log.error(f"图片翻译过程中发生错误: {e}")
            raise RuntimeError(f"图片翻译失败: {e}")
    
    def translate_image_simple(self, 
                              image_path: str,
                              output_dir: str = "output",
                              target_language: str = "zh") -> str:
        """
        简化的图片翻译接口
        
        Args:
            image_path: 输入图片路径
            output_dir: 输出目录
            target_language: 目标语言
            
        Returns:
            输出图片路径
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成输出文件名
        input_path = Path(image_path)
        output_filename = f"{input_path.stem}_translated_{target_language}{input_path.suffix}"
        output_path = os.path.join(output_dir, output_filename)
        
        # 执行翻译
        self.translate_image(
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
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            target_language: 目标语言
            image_extensions: 支持的图片扩展名
            
        Returns:
            输出文件路径列表
        """
        if image_extensions is None:
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
        
        if not os.path.exists(input_dir):
            raise FileNotFoundError(f"输入目录不存在: {input_dir}")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 查找图片文件
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
        for i, image_file in enumerate(image_files, 1):
            try:
                log.info(f"处理第 {i}/{len(image_files)} 个文件: {image_file.name}")
                output_path = self.translate_image_simple(
                    str(image_file),
                    output_dir,
                    target_language
                )
                output_paths.append(output_path)
                log.info(f"完成: {image_file.name} -> {os.path.basename(output_path)}")
            except Exception as e:
                log.error(f"处理文件 {image_file.name} 时发生错误: {e}")
                continue
        
        log.info(f"批量翻译完成，成功处理 {len(output_paths)}/{len(image_files)} 个文件")
        return output_paths
    
    def batch_translate_images_optimized(self,
                                 image_inputs: List[Union[str, np.ndarray]],
                                 output_paths: Optional[List[str]] = None,
                                 target_language: str = "zh") -> List[np.ndarray]:
        """
        优化的批量翻译功能，一次性处理所有图片的 OCR 和翻译
        
        Args:
            image_inputs: 输入图片路径或图片数据列表
            output_paths: 输出图片路径列表（可选）
            target_language: 目标语言代码
            
        Returns:
            翻译后的图片数据列表
        """
        if not self.is_ready():
            raise RuntimeError("图片翻译器未准备就绪，请检查各组件初始化状态")
        
        # 1. 加载所有图片
        images_data = []
        for img_input in image_inputs:
            if isinstance(img_input, str):
                if not os.path.exists(img_input):
                    raise FileNotFoundError(f"图片文件不存在: {img_input}")
                # 使用imdecode处理Unicode文件名
                img_data = cv2.imdecode(np.fromfile(img_input, dtype=np.uint8), cv2.IMREAD_COLOR)
                if img_data is None:
                    raise ValueError(f"无法读取图片文件: {img_input}")
            elif isinstance(img_input, np.ndarray):
                img_data = img_input.copy()
            else:
                raise ValueError("image_input必须是文件路径或numpy数组")
            images_data.append(img_data)
        
        log.info(f"已加载 {len(images_data)} 张图片")
        
        try:
            # 2. 对所有图片进行 OCR 识别
            log.info("开始批量 OCR 识别...")
            all_ocr_results = []
            all_structured_texts = []
            
            for i, img_data in enumerate(images_data):
                # OCR 识别
                ocr_results = self.ocr_manager.recognize_image_data_sync(img_data)
                if not ocr_results:
                    log.warning(f"图片 {i+1} 未识别到任何文本")
                    all_ocr_results.append([])
                    all_structured_texts.append([])
                    continue
                
                # 过滤结果
                filtered_results = self.ocr_manager.filter_numeric_and_symbols(ocr_results)
                filtered_results = [r for r in filtered_results if r.confidence >= 0.75]
                
                # 获取结构化文本
                structured_texts = self.ocr_manager.get_structured_text(filtered_results)
                
                all_ocr_results.append(filtered_results)
                all_structured_texts.append(structured_texts)
                
                log.info(f"图片 {i+1} OCR 识别完成，识别到 {len(structured_texts)} 个文本块")
            
            # 3. 收集所有需要翻译的文本
            all_texts = set()
            text_to_pages = {}  # 记录每个文本出现在哪些页面
            
            for page_idx, structured_texts in enumerate(all_structured_texts):
                for item in structured_texts:
                    text = item['text'].strip()
                    if text:
                        all_texts.add(text)
                        if text not in text_to_pages:
                            text_to_pages[text] = []
                        text_to_pages[text].append(page_idx)
            
            # 4. 批量翻译所有文本
            log.info(f"开始批量翻译 {len(all_texts)} 个唯一文本...")
            texts_to_translate = list(all_texts)
            translations = {}
            
            if isinstance(self.translator, TranslatorFactory.create_translator("智谱").__class__):
                # 使用智谱翻译器的批量翻译功能
                translated_texts = self.translator.translate_batch(texts_to_translate, target_lang=target_language)
                translations = dict(zip(texts_to_translate, translated_texts))
            else:
                # 使用其他翻译器逐个翻译
                for text in texts_to_translate:
                    try:
                        translated = self.translator.translate(text, target_lang=target_language)
                        translations[text] = translated
                    except Exception as e:
                        log.error(f"翻译失败: {text}, 错误: {e}")
                        translations[text] = text
            
            log.info("批量翻译完成")
            
            # 5. 对每页进行文本替换
            result_images = []
            for page_idx, (img_data, structured_texts) in enumerate(zip(images_data, all_structured_texts)):
                # 为当前页面创建翻译字典
                page_translations = {}
                for item in structured_texts:
                    original_text = item['text'].strip()
                    if original_text in translations:
                        page_translations[original_text] = translations[original_text]
                
                # 替换文本
                log.info(f"处理第 {page_idx + 1} 页的文本替换...")
                result_image = self.manga_text_replacer.process_manga_image(
                    img_data,
                    structured_texts,
                    page_translations,
                    target_language=target_language,
                    inpaint_background=True
                )
                result_images.append(result_image)
            
            # 6. 保存结果（如果提供了输出路径）
            if output_paths:
                if len(output_paths) != len(result_images):
                    raise ValueError("输出路径数量必须与输入图片数量相同")
                    
                for i, (result_image, output_path) in enumerate(zip(result_images, output_paths)):
                    # 使用imencode保存图片以支持Unicode文件名
                    try:
                        ext = os.path.splitext(output_path)[1]
                        _, encoded_img = cv2.imencode(ext, result_image)
                        if encoded_img is not None and encoded_img.tofile(output_path):
                            log.info(f"第 {i + 1} 页翻译结果已保存: {output_path}")
                        else:
                            log.error(f"保存第 {i + 1} 页翻译结果失败: {output_path}")
                    except Exception as e:
                        log.error(f"保存第 {i + 1} 页翻译结果时出错: {output_path} - {e}")
            
            log.info(f"批量翻译全部完成，共处理 {len(result_images)} 页")
            return result_images
            
        except Exception as e:
            log.error(f"批量翻译过程中发生错误: {e}")
            raise RuntimeError(f"批量翻译失败: {e}")
    
    def get_ocr_results(self, image_input: Union[str, np.ndarray]) -> List[OCRResult]:
        """
        仅执行OCR识别，返回识别结果
        
        Args:
            image_input: 输入图片路径或图片数据
            
        Returns:
            OCR识别结果列表
        """
        if not self.ocr_manager or not self.ocr_manager.is_ready():
            raise RuntimeError("OCR管理器未准备就绪")
        
        if isinstance(image_input, str):
            return self.ocr_manager.recognize_image_sync(image_input)
        elif isinstance(image_input, np.ndarray):
            return self.ocr_manager.recognize_image_data_sync(image_input)
        else:
            raise ValueError("image_input必须是文件路径或numpy数组")
    
    def translate_text(self, text: str, target_language: str = "zh") -> str:
        """
        翻译单个文本
        
        Args:
            text: 要翻译的文本
            target_language: 目标语言
            
        Returns:
            翻译结果
        """
        if not self.translator:
            raise RuntimeError("翻译器未准备就绪")
        
        return self.translator.translate(text, target_lang=target_language)
    
    def _get_original_path(self, output_path: str) -> str:
        """生成原图保存路径"""
        path = Path(output_path)
        return str(path.parent / f"{path.stem}_original{path.suffix}")
    
    def _check_image_file(self, file_path: str) -> bool:
        """检查图片文件是否有效

        Args:
            file_path (str): 图片文件路径

        Returns:
            bool: 是否是有效的图片文件
        """
        if not os.path.exists(file_path):
            self.log_message.emit(f"文件不存在: {file_path}")
            return False
            
        try:
            # 使用imdecode处理Unicode文件名
            img_data = np.fromfile(file_path, dtype=np.uint8)
            img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
            
            if img is None:
                self.log_message.emit(f"无法读取图片文件: {file_path}")
                return False
                
            # 检查图片尺寸
            height, width = img.shape[:2]
            file_size = os.path.getsize(file_path)
            self.log_message.emit(f"图片信息 - 路径: {file_path}, 尺寸: {width}x{height}, 大小: {file_size} 字节")
            return True
            
        except Exception as e:
            self.log_message.emit(f"检查图片文件时出错: {file_path} - {e}")
            return False
    
    def _save_image(self, image: np.ndarray, file_path: str) -> bool:
        """使用imencode保存图片，支持Unicode文件名
        
        Args:
            image: 图片数据
            file_path: 保存路径
            
        Returns:
            bool: 是否保存成功
        """
        try:
            ext = os.path.splitext(file_path)[1]
            _, encoded_img = cv2.imencode(ext, image)
            if encoded_img is not None:
                encoded_img.tofile(file_path)
                return True
            return False
        except Exception as e:
            log.error(f"保存图片失败: {e}")
            return False


def create_image_translator(translator_type: str = "Google", **kwargs) -> ImageTranslator:
    """
    创建图片翻译器的便捷函数
    
    Args:
        translator_type: 翻译器类型
        **kwargs: 翻译器参数
        
    Returns:
        ImageTranslator实例
    """
    return ImageTranslator(translator_type, **kwargs)


# 使用示例
if __name__ == "__main__":
    # 示例1: 使用Google翻译器
    translator = create_image_translator("Google")
    
    # 翻译单张图片
    # result_path = translator.translate_image_simple(
    #     "input.jpg",
    #     output_dir="output",
    #     target_language="zh"
    # )
    # print(f"翻译完成: {result_path}")
    
    # 示例2: 使用智谱翻译器
    # translator = create_image_translator(
    #     "智谱",
    #     api_key="your_api_key",
    #     model="glm-4-flash"
    # )
    
    # 示例3: 批量翻译
    # output_paths = translator.batch_translate_images(
    #     input_dir="input_images",
    #     output_dir="output_images",
    #     target_language="zh"
    # )
    # print(f"批量翻译完成，处理了 {len(output_paths)} 个文件")
    
    print("ImageTranslator模块加载完成")
