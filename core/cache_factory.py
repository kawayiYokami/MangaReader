# core/cache_factory.py
from typing import Literal, Union
from core.cache_interface import CacheInterface
from core.manga_cache import MangaListCacheManager
from core.ocr_cache_manager import OcrCacheManager
from core.translation_cache_manager import TranslationCacheManager
# DangerousWordCacheManager import removed

# Define a type for cache types for better type hinting
CacheType = Literal["manga_list", "ocr", "translation"] # "dangerous_word" removed

class CacheManagerFactory:
    """
    工厂类，用于创建和获取不同类型的缓存管理器实例。
    """
    _managers = {} # To store singleton instances

    def get_manager(self, cache_type: CacheType) -> CacheInterface:
        """
        获取指定类型的缓存管理器实例。
        使用单例模式确保每种类型的管理器只有一个实例。

        Args:
            cache_type: 缓存类型 ("manga_list", "ocr", "translation")

        Returns:
            CacheInterface: 对应类型的缓存管理器实例。

        Raises:
            ValueError: 如果提供了未知的缓存类型。
        """
        if cache_type not in self._managers:
            if cache_type == "manga_list":
                self._managers[cache_type] = MangaListCacheManager()
            elif cache_type == "ocr":
                self._managers[cache_type] = OcrCacheManager()
            elif cache_type == "translation":
                self._managers[cache_type] = TranslationCacheManager()
            # "dangerous_word" case removed
            else:
                # This case should ideally be caught by Literal type hinting
                # but good to have a runtime check as well.
                raise ValueError(f"未知的缓存类型: {cache_type}")

        return self._managers[cache_type]

    def close_all_managers(self) -> None:
        """
        关闭所有已创建的缓存管理器实例。
        这在应用程序退出时很有用。
        """
        for manager_type in list(self._managers.keys()): # Iterate over a copy of keys
            manager = self._managers.pop(manager_type) # Remove and get
            try:
                # All managers in this factory are expected to have a close method
                # if they implement CacheInterface properly (though CacheInterface doesn't enforce close())
                # For now, we assume they might have it.
                if hasattr(manager, 'close') and callable(manager.close):
                    manager.close()
            except Exception as e:
                # Log error, but continue closing others
                # Assuming a logger is available or print for simplicity
                print(f"关闭缓存管理器 {manager_type} 时出错: {e}")
        self._managers.clear() # Ensure the dictionary is empty

# 全局工厂实例 (可选，但方便访问)
# cache_factory = CacheManagerFactory()
# 使用时: from core.cache_factory import cache_factory
# manager = cache_factory.get_manager("ocr")

# 或者，每次需要时创建工厂实例：
# factory = CacheManagerFactory()
# manager = factory.get_manager("ocr")
# 这种方式下，close_all_managers 需要在同一个工厂实例上调用。
# 为了方便全局关闭，可以考虑将 _managers 设为类变量，
# 或者提供一个注册/注销机制。
# 对于当前应用，一个全局工厂实例可能更简单。

# 决定采用单例模式的工厂实例，方便全局调用 close_all_managers
_global_cache_factory_instance = None

def get_cache_factory_instance() -> CacheManagerFactory:
    """获取全局 CacheManagerFactory 实例"""
    global _global_cache_factory_instance
    if _global_cache_factory_instance is None:
        _global_cache_factory_instance = CacheManagerFactory()
    return _global_cache_factory_instance