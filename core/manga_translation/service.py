# file: core/manga_translation/service.py
import asyncio
import cv2
import numpy as np
import zipfile
import os
import tempfile
from pathlib import Path
from typing import List, Optional

from .processor import MangaPageProcessor
from core.core_cache.persistent_translation_cache import PersistentTranslationCache
from core.manga.data_source import DataSourceFactory
from core.config import config
import logging

class MangaTranslationService:
    """
    A stateless service to handle manga translation.
    This service orchestrates the translation process in a synchronous, blocking manner.
    It is designed to be simple, robust, and directly aligned with the ImageCompressor's architecture.
    """

    def __init__(self, page_processor: MangaPageProcessor, image_cache: PersistentTranslationCache):
        """
        Initializes the service with its dependencies.
        
        Args:
            page_processor: The processor responsible for OCR and translation of single pages.
            image_cache: The cache manager for storing and retrieving translated images.
        """
        self.processor = page_processor
        self.cache = image_cache

    def translate_manga_file(self, manga_path: str, target_language: str) -> Optional[str]:
        """
        Translates a manga archive file synchronously and returns the path to the translated zip file.

        This is a blocking operation that performs the entire workflow:
        1. Extracts images from the source archive.
        2. Processes each image (OCR, translation, text replacement).
        3. Caches the translated images.
        4. Packages the translated images into a new temporary zip file.

        Args:
            manga_path: The absolute path to the source manga archive (e.g., .zip, .cbz).
            target_language: The target language code (e.g., 'zh', 'en').

        Returns:
            The absolute path to the newly created temporary zip file if successful, otherwise None.
        """
        logging.info(f"开始同步翻译 '{manga_path}' 到 '{target_language}'。")
        task_id = Path(manga_path).name  # Use filename for logging and caching
        translator_type = config.translator_type.value
        
        # 在这个简化的同步模型中，处理器的取消事件现在由处理器自身管理，或者根本不管理。
        # 为以防万一，我们可以重置它。
        self.processor.reset()

        try:
            # 1. 创建数据源并获取页面
            data_source = DataSourceFactory.create(manga_path)
            if not data_source:
                raise ValueError(f"Could not create data source for {manga_path}")
            
            properties = data_source.get_properties()
            num_pages = properties.get('total_pages', 0) if properties else 0
            if num_pages == 0:
                logging.warning(f"数据源 {manga_path} 报告有 0 页。正在中止。")
                return None

            logging.info(f"为任务 '{task_id}' 创建了包含 {num_pages} 页的数据源。")
            image_data_list = [data_source.get_page_image_data(i) for i in range(num_pages)]
            image_arrays = [cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR) for data in image_data_list if data]
            
            # 2. 处理页面（OCR、翻译）
            logging.info(f"开始为任务 '{task_id}' 中的 {len(image_arrays)} 张图像进行页面处理。")
            # 这里使用 asyncio.run 是因为底层的处理器可能仍然是异步的
            manga_title = Path(manga_path).stem
            logging.info(f"为 '{manga_title}' 构建翻译上下文。")
            
            translated_arrays = asyncio.run(self.processor.process_pages(
                image_inputs=image_arrays,
                target_language=target_language,
                manga_title=manga_title,
                # 关键修复：直接传递完整的、真实的 manga_path 作为缓存的原始路径
                # file_paths_for_cache 在解压场景下可能指向临时文件，因此 original_archive_paths_for_cache 更可靠
                file_paths_for_cache=[manga_path] * len(image_arrays),
                page_nums_for_cache=list(range(len(image_arrays))),
                original_archive_paths_for_cache=[manga_path] * len(image_arrays)
            ))
            
            if not translated_arrays:
                logging.error(f"Page processing for '{task_id}' resulted in no translated pages.")
                return None

            # 3. 缓存结果
            logging.info(f"页面处理完成。正在为任务 '{task_id}' 缓存 {len(translated_arrays)} 个结果。")
            for i, translated_array in enumerate(translated_arrays):
                self.cache.save_translated_image(task_id, i, translated_array, target_language, translator_type)

            # 4. 打包成一个新的临时 Zip 存档
            temp_zip_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip', prefix='manga_trans_')
            logging.info(f"正在为任务 '{task_id}' 将 {len(translated_arrays)} 页打包到 {temp_zip_file.name}")
            
            with zipfile.ZipFile(temp_zip_file.name, 'w', zipfile.ZIP_DEFLATED) as zf:
                for i, image_array in enumerate(translated_arrays):
                    success, buffer = cv2.imencode('.webp', image_array)
                    if success:
                        # 使用与压缩器类似的通用命名方案
                        zf.writestr(f"page_{i:03d}.webp", buffer)
                    else:
                        logging.warning(f"为任务 '{task_id}' 将页面 {i} 编码为 WebP 格式失败。")
            
            logging.info(f"成功为任务 '{task_id}' 创建翻译后的归档文件于: {temp_zip_file.name}")
            return temp_zip_file.name

        except Exception as e:
            logging.error(f"Error in synchronous translation workflow for task '{task_id}': {e}", exc_info=True)
            return None
        finally:
            self.processor.reset()
