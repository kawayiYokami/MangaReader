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
            translator_type: 翻译器类型 ("智谱", "Google", "DeepL", "百度", "MyMemory")
            **translator_kwargs: 翻译器相关参数
                - 智谱: api_key, model
                - Google: api_key (可选)
                - DeepL: api_key
                - 百度: app_id, app_key
                - MyMemory: email (可选)
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
            elif translator_type == "DeepL":
                api_key = kwargs.get('api_key') or config.deepl_api_key.value
                if not api_key:
                    raise ValueError("DeepL翻译器需要API密钥")
                self.translator = TranslatorFactory.create_translator(
                    translator_type="DeepL",
                    api_key=api_key
                )
            elif translator_type == "百度":
                app_id = kwargs.get('app_id') or config.baidu_app_id.value
                app_key = kwargs.get('app_key') or config.baidu_app_key.value
                if not app_id or not app_key:
                    raise ValueError("百度翻译器需要APP ID和APP Key")
                self.translator = TranslatorFactory.create_translator(
                    translator_type="百度",
                    app_id=app_id,
                    app_key=app_key
                )
            elif translator_type == "MyMemory":
                email = kwargs.get('email') or config.mymemory_email.value
                self.translator = TranslatorFactory.create_translator(
                    translator_type="MyMemory",
                    email=email
                )
            else:
                raise ValueError(f"不支持的翻译器类型: {translator_type}")
            
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
            image_data = cv2.imread(image_input)
            if image_data is None:
                raise ValueError(f"无法读取图片文件: {image_input}")
            log.info(f"已加载图片: {image_input}")
        elif isinstance(image_input, np.ndarray):
            image_data = image_input.copy()
            log.info("已加载图片数据")
        else:
            raise ValueError("image_input必须是文件路径或numpy数组")
        
        # 保存原图副本
        if save_original and output_path:
            original_path = self._get_original_path(output_path)
            cv2.imwrite(original_path, image_data)
            log.info(f"原图已保存: {original_path}")
        
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
            
            # 3. 获取结构化文本
            structured_texts = self.ocr_manager.get_structured_text(ocr_results)
            log.info(f"获取到 {len(structured_texts)} 个结构化文本块")
            
            # 4. 翻译文本
            log.info("开始翻译...")
            translations = {}
            translated_texts = []
            
            for item in structured_texts:
                full_text = item['text']
                if not full_text.strip():
                    translated_texts.append("")
                    continue
                
                try:
                    translated = self.translator.translate(full_text, target_lang=target_language)
                    translations[full_text] = translated
                    translated_texts.append(translated)
                    
                    # 将翻译结果应用到相关的OCR结果
                    for ocr_result in item['ocr_results']:
                        ocr_result.translated_text = translated
                        
                    log.debug(f"翻译: '{full_text}' -> '{translated}'")
                except Exception as e:
                    log.error(f"翻译失败: {full_text}, 错误: {e}")
                    translations[full_text] = full_text  # 翻译失败时使用原文
                    translated_texts.append(full_text)
            
            log.info(f"翻译完成，共翻译 {len(translations)} 个文本块")
            
            # 5. 创建翻译字典
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
                success = cv2.imwrite(output_path, result_image)
                if success:
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
