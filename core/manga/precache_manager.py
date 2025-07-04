"""
预缓存策略查询器

在V8架构中，此类职责已大幅简化。
它不再进行任何“分析”，分析逻辑已前置到 MangaManager 的扫描阶段。
现在，它只负责从 PagePolicyCacheManager 中查询已存在的缓存策略。
实际的缓存文件生成与获取，将由 MangaViewerManager 或类似的视图层管理器处理。
"""
import threading
from typing import Optional
import logging

from core.core_cache.cache_factory import get_cache_factory_instance
from core.manga.policy_constants import POLICY_CACHED, POLICY_PENDING, POLICY_NOT_REQUIRED

class PrecacheManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.logger = logging.getLogger('PrecacheManager')
            
            # 从缓存工厂获取页面策略管理器
            self.policy_manager = get_cache_factory_instance().get_manager("page_policy")
            
            self._initialized = True
            self.logger.info("预缓存管理器 (策略查询器) 初始化完成。")

    def get_page_cache_policy(self, manga_path: str, page_index: int) -> Optional[str]:
        """
        获取指定页面的缓存策略。
        
        返回 "PENDING", "CACHED", "NOT_REQUIRED", 或 None (如果策略不存在).
        """
        return self.policy_manager.get_policy(manga_path, page_index)

# 创建一个单例实例，在整个应用中共享
precache_manager = PrecacheManager()