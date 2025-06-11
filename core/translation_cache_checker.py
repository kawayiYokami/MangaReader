# core/translation_cache_checker.py
"""
翻译缓存检查器

负责检查翻译缓存是否存在，避免重复翻译。
"""

from typing import Optional, Dict, Any
import hashlib
import numpy as np
from pathlib import Path

from .cache_factory import get_cache_factory_instance
from .realtime_translation_cache_utils import RealtimeTranslationCacheUtils
from .manga_model import MangaLoader
from utils import manga_logger as log


class TranslationCacheChecker:
    """翻译缓存检查器"""
    
    def __init__(self):
        """初始化缓存检查器"""
        self.manga_loader = MangaLoader()
        self.cache_manager = None
        
        # 初始化缓存管理器
        try:
            self.cache_manager = get_cache_factory_instance().get_manager("realtime_translation")
        except Exception as e:
            log.warning(f"初始化实时翻译缓存管理器失败: {e}")
    
    def check_cache_exists(self, manga_path: str, page_index: int, 
                          target_language: str = "zh", 
                          force_retranslate: bool = False,
                          image_hash: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        检查翻译缓存是否存在
        
        Args:
            manga_path: 漫画路径
            page_index: 页面索引
            target_language: 目标语言
            force_retranslate: 强制重新翻译
            
        Returns:
            缓存信息字典，如果不存在则返回None
        """
        if force_retranslate or not self.cache_manager:
            return None
        
        try:
            # 加载图像计算哈希
            image_hash = self._get_image_hash(manga_path, page_index)
            if not image_hash:
                return None
            
            # 生成缓存键
            cache_key = self.cache_manager.generate_key(
                manga_path, page_index, target_language, image_hash
            )
            
            # 检查缓存
            cached_data = self.cache_manager.get(cache_key)
            if not cached_data:
                return None
            
            # 验证缓存有效性
            if self._validate_cache(cached_data, manga_path, page_index):
                log.info(f"找到有效翻译缓存: {manga_path}:{page_index}")
                return {
                    'cache_key': cache_key,
                    'cached_data': cached_data,
                    'image_hash': image_hash,
                    'is_valid': True
                }
            else:
                log.warning(f"翻译缓存已失效: {manga_path}:{page_index}")
                # 删除无效缓存
                self.cache_manager.delete(cache_key)
                return None
                
        except Exception as e:
            log.error(f"检查翻译缓存失败: {e}")
            return None
    
    def _get_image_hash(self, manga_path: str, page_index: int) -> Optional[str]:
        """获取图像哈希"""
        try:
            # 加载漫画
            manga = self.manga_loader.load_manga(manga_path)
            if not manga:
                return None
            
            # 获取页面图像
            image = self.manga_loader.get_page_image(manga, page_index)
            if image is None:
                return None
            
            # 计算哈希
            return RealtimeTranslationCacheUtils.calculate_image_hash(image)
            
        except Exception as e:
            log.error(f"获取图像哈希失败: {e}")
            return None
    
    def _validate_cache(self, cached_data, manga_path: str, page_index: int) -> bool:
        """验证缓存有效性"""
        try:
            # 加载当前图像
            manga = self.manga_loader.load_manga(manga_path)
            if not manga:
                return False
            
            current_image = self.manga_loader.get_page_image(manga, page_index)
            if current_image is None:
                return False
            
            # 使用工具类验证
            return RealtimeTranslationCacheUtils.validate_cache_data(cached_data, current_image)
            
        except Exception as e:
            log.error(f"验证缓存失败: {e}")
            return False
    
    def get_cache_statistics(self, manga_path: str) -> Dict[str, Any]:
        """获取指定漫画的缓存统计"""
        if not self.cache_manager:
            return {'total_cached_pages': 0, 'cached_pages': []}
        
        try:
            cached_pages = self.cache_manager.get_cache_by_manga(manga_path)
            
            stats = {
                'total_cached_pages': len(cached_pages),
                'cached_pages': [],
                'languages': set(),
                'total_size_bytes': 0
            }
            
            for cache_data in cached_pages:
                page_info = {
                    'page_index': cache_data.page_index,
                    'target_language': cache_data.target_language,
                    'created_at': cache_data.created_at,
                    'last_accessed': cache_data.last_accessed,
                    'access_count': cache_data.access_count,
                    'original_texts_count': len(cache_data.original_texts),
                    'translated_texts_count': len(cache_data.translated_texts)
                }
                
                stats['cached_pages'].append(page_info)
                stats['languages'].add(cache_data.target_language)
                
                # 估算大小
                if cache_data.result_image_data:
                    stats['total_size_bytes'] += len(cache_data.result_image_data)
            
            stats['languages'] = list(stats['languages'])
            
            return stats
            
        except Exception as e:
            log.error(f"获取缓存统计失败: {e}")
            return {'total_cached_pages': 0, 'cached_pages': []}
    
    def preload_cache_info(self, manga_path: str, page_range: Optional[tuple] = None) -> Dict[int, Dict[str, Any]]:
        """
        预加载缓存信息
        
        Args:
            manga_path: 漫画路径
            page_range: 页面范围 (start, end)
            
        Returns:
            页面索引到缓存信息的映射
        """
        cache_info = {}
        
        if not self.cache_manager:
            return cache_info
        
        try:
            cached_pages = self.cache_manager.get_cache_by_manga(manga_path)
            
            for cache_data in cached_pages:
                page_index = cache_data.page_index
                
                # 检查页面范围
                if page_range:
                    start, end = page_range
                    if page_index < start or page_index > end:
                        continue
                
                cache_info[page_index] = {
                    'cache_key': self.cache_manager.generate_key(
                        manga_path, page_index, cache_data.target_language, cache_data.image_hash
                    ),
                    'target_language': cache_data.target_language,
                    'image_hash': cache_data.image_hash,
                    'created_at': cache_data.created_at,
                    'last_accessed': cache_data.last_accessed,
                    'access_count': cache_data.access_count,
                    'has_result_image': cache_data.result_image_data is not None
                }
            
            return cache_info
            
        except Exception as e:
            log.error(f"预加载缓存信息失败: {e}")
            return cache_info
    
    def is_translation_needed(self, manga_path: str, page_index: int, 
                             target_language: str = "zh",
                             force_retranslate: bool = False) -> bool:
        """
        判断是否需要翻译
        
        Args:
            manga_path: 漫画路径
            page_index: 页面索引
            target_language: 目标语言
            force_retranslate: 强制重新翻译
            
        Returns:
            是否需要翻译
        """
        if force_retranslate:
            return True
        
        cache_info = self.check_cache_exists(manga_path, page_index, target_language)
        return cache_info is None
    
    def get_cached_translation_result(self, manga_path: str, page_index: int,
                                    target_language: str = "zh") -> Optional[np.ndarray]:
        """
        获取缓存的翻译结果图像
        
        Args:
            manga_path: 漫画路径
            page_index: 页面索引
            target_language: 目标语言
            
        Returns:
            翻译结果图像，如果不存在则返回None
        """
        cache_info = self.check_cache_exists(manga_path, page_index, target_language)
        if not cache_info:
            return None
        
        try:
            cached_data = cache_info['cached_data']
            if cached_data.result_image_data:
                # 解码图像数据
                translated_image = RealtimeTranslationCacheUtils.decode_result_image(
                    cached_data.result_image_data
                )
                
                if translated_image is not None:
                    # 更新访问统计
                    cached_data.access_count += 1
                    cached_data.last_accessed = RealtimeTranslationCacheUtils._get_current_time()
                    
                    # 保存更新
                    self.cache_manager.set(cache_info['cache_key'], cached_data)
                    
                    log.info(f"从缓存获取翻译结果: {manga_path}:{page_index}")
                    return translated_image
            
            return None
            
        except Exception as e:
            log.error(f"获取缓存翻译结果失败: {e}")
            return None
    
    def cleanup_invalid_cache(self, manga_path: Optional[str] = None) -> int:
        """
        清理无效缓存
        
        Args:
            manga_path: 漫画路径，None表示清理所有
            
        Returns:
            清理的缓存数量
        """
        if not self.cache_manager:
            return 0
        
        try:
            if manga_path:
                # 清理指定漫画的无效缓存
                cached_pages = self.cache_manager.get_cache_by_manga(manga_path)
                invalid_count = 0
                
                for cache_data in cached_pages:
                    if not self._validate_cache(cache_data, manga_path, cache_data.page_index):
                        cache_key = self.cache_manager.generate_key(
                            manga_path, cache_data.page_index, 
                            cache_data.target_language, cache_data.image_hash
                        )
                        self.cache_manager.delete(cache_key)
                        invalid_count += 1
                
                log.info(f"清理了 {invalid_count} 个无效缓存: {manga_path}")
                return invalid_count
            else:
                # 清理所有无效缓存
                return self.cache_manager.cleanup_missing_files()
                
        except Exception as e:
            log.error(f"清理无效缓存失败: {e}")
            return 0
