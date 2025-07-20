"""
翻译工厂 - V2 适配器
该文件现在作为新版 MangaTranslationService 的适配器，
为旧的、依赖此工厂的模块（如 viewer.py）提供兼容接口。
"""

import threading
from typing import Optional, Dict
from enum import Enum
import asyncio

# 导入新的翻译服务和它的依赖
import logging
from web.api.translation import get_manga_translation_service
from core.manga_translation.service import MangaTranslationService
from core.config import config

class PageStatus(Enum):
    """页面翻译状态枚举 (保持与旧版兼容)"""
    UNKNOWN = "unknown"
    QUEUED = "queued"
    TRANSLATING = "translating"
    TRANSLATED = "translated"
    FAILED = "failed"

class TranslationFactory:
    """
    翻译工厂 (V2 适配器)
    这是一个全局单例，它包装了新的 MangaTranslationService。
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        # 获取新翻译服务的实例
        try:
            self.service: MangaTranslationService = get_manga_translation_service()
            self._initialized = True
            logging.info("TranslationFactory (V2 Adapter) 初始化完成，已连接到 MangaTranslationService。")
        except Exception as e:
            logging.error(f"TranslationFactory (V2 Adapter) 初始化失败: {e}", exc_info=True)
            self.service = None
            self._initialized = False

    def get_translated_page(self, manga_path: str, page_index: int, **kwargs) -> Optional[bytes]:
        """
        获取翻译页面 - 通过查询新服务的持久化缓存来实现。
        这是一个同步方法。
        """
        if not self.is_service_running():
            logging.error("无法获取翻译页面，因为 MangaTranslationService 未成功初始化。")
            return None
            
        try:
            # 从 config 获取当前的翻译器类型和目标语言
            # 注意: 这是一种妥协，理想情况下这些参数应由调用者通过 kwargs 传递
            translator_type = config.translator_type.value
            target_language = config.target_language.value

            # 直接从服务的缓存中获取数据
            translated_page_bytes = self.service.cache.get_cached_translation(
                manga_path=manga_path,
                page_index=page_index,
                target_language=target_language,
                translator_type=translator_type
            )
            return translated_page_bytes
        except Exception as e:
            logging.error(f"Adapter get_translated_page 失败: {e}", exc_info=True)
            return None

    def get_page_status(self, manga_path: str, page_index: int, **kwargs) -> PageStatus:
        """
        获取页面翻译状态 - 通过查询新服务的状态来模拟。
        """
        if not self.is_service_running():
            return PageStatus.FAILED

        # 1. 直接检查缓存，如果存在，则肯定是已翻译
        # (注意：这里的缓存检查逻辑与 service.get_translated_page 中的逻辑重复，但对于状态检查是必要的)
        if self.service.cache.get_cached_translation(manga_path, page_index, "zh", "any"):
             return PageStatus.TRANSLATED

        # 2. 检查任务是否正在运行
        with self.service._active_tasks_lock:
            if manga_path in self.service._active_tasks:
                # 无法区分是排队还是翻译中，对于UI来说，都算正在处理
                return PageStatus.TRANSLATING
        
        # 3. 如果既不在缓存中，也不在运行任务中，那就是未知状态
        return PageStatus.UNKNOWN

    def is_service_running(self) -> bool:
        """检查新服务是否已成功初始化。"""
        return self.service is not None

# 全局实例获取函数
_translation_factory_instance = None
_factory_lock = threading.Lock()

def get_translation_factory() -> "TranslationFactory":
    """获取全局翻译工厂实例 (单例)"""
    global _translation_factory_instance
    if _translation_factory_instance is None:
        with _factory_lock:
            if _translation_factory_instance is None:
                _translation_factory_instance = TranslationFactory()
    return _translation_factory_instance
