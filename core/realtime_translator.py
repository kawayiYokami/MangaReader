#!/usr/bin/env python3
"""
实时翻译器 - 纯粹的翻译工具

新架构版本：只负责翻译，不处理缓存
"""

import numpy as np
from typing import Optional, Dict, Any
from PIL import Image

from core.image_translator import ImageTranslator
from utils import manga_logger as log


class RealtimeTranslator:
    """
    实时翻译器 - 纯粹的翻译工具

    在新的翻译工厂架构中，这个类只负责翻译，不处理任何缓存逻辑
    """

    def __init__(self):
        """初始化实时翻译器"""
        self.image_translator: Optional[ImageTranslator] = None
        log.info("实时翻译器初始化完成（纯翻译工具版本）")

    def set_translator_config(self, translator_type: str = "智谱", **kwargs):
        """设置翻译器配置"""
        try:
            log.info(f"配置翻译器: {translator_type}")
            self.image_translator = ImageTranslator(translator_type, **kwargs)

            if self.image_translator.is_ready():
                log.info(f"翻译器配置完成: {translator_type}")
                return True
            else:
                log.warning(f"翻译器配置完成但未完全准备就绪: {translator_type}")
                return False

        except Exception as e:
            log.error(f"翻译器配置失败: {e}")
            self.image_translator = None
            return False

    def is_ready(self) -> bool:
        """检查翻译器是否准备就绪"""
        return self.image_translator is not None and self.image_translator.is_ready()

    def translate_image(self, image: np.ndarray, target_language: str = "zh") -> Optional[Dict[str, Any]]:
        """
        翻译图像

        Args:
            image: 输入图像数组
            target_language: 目标语言

        Returns:
            翻译结果字典，包含translated_image等信息
        """
        if not self.is_ready():
            log.error("翻译器未准备就绪")
            return None

        try:
            log.debug("开始翻译图像")
            result = self.image_translator.translate_image(image, target_language)

            if result and result.get("translated_image") is not None:
                log.debug("图像翻译完成")
                return result
            else:
                log.warning("翻译返回空结果")
                return None

        except Exception as e:
            log.error(f"图像翻译失败: {e}")
            return None

    def translate_image_with_cache_data(self, image: np.ndarray, target_language: str = "zh",
                                      file_path_for_cache: Optional[str] = None,
                                      page_num_for_cache: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        翻译图像并返回详细的缓存数据

        Args:
            image: 输入图像数组
            target_language: 目标语言
            file_path_for_cache: 用于缓存的文件路径
            page_num_for_cache: 用于缓存的页面编号

        Returns:
            包含详细翻译数据的字典
        """
        if not self.is_ready():
            log.error("翻译器未准备就绪")
            return None

        try:
            log.debug("开始翻译图像（带缓存数据）")

            # 使用增强的翻译方法
            if hasattr(self.image_translator, 'translate_image_with_cache_data'):
                result = self.image_translator.translate_image_with_cache_data(
                    image_input=image,
                    target_language=target_language,
                    file_path_for_cache=file_path_for_cache,
                    page_num_for_cache=page_num_for_cache
                )
            else:
                # 回退到基本翻译方法
                result = self.image_translator.translate_image(image, target_language)

            if result and result.get("translated_image") is not None:
                log.debug("图像翻译完成（带缓存数据）")
                return result
            else:
                log.warning("翻译返回空结果")
                return None

        except Exception as e:
            log.error(f"图像翻译失败: {e}")
            return None

    def get_translator_status(self) -> Dict[str, Any]:
        """获取翻译器状态"""
        return {
            "is_ready": self.is_ready(),
            "translator_type": getattr(self.image_translator, 'translator_type', None) if self.image_translator else None
        }





# 全局实例
_realtime_translator_instance: Optional[RealtimeTranslator] = None


def get_realtime_translator() -> RealtimeTranslator:
    """获取实时翻译器全局实例"""
    global _realtime_translator_instance
    if _realtime_translator_instance is None:
        _realtime_translator_instance = RealtimeTranslator()
    return _realtime_translator_instance
