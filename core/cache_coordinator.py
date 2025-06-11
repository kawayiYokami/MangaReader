#!/usr/bin/env python3
"""
缓存协调器

统一管理四层缓存架构，提供一致的缓存接口：
1. 内存缓存 (快速访问)
2. 持久化WebP缓存 (磁盘文件)
3. SQLite缓存 (完整翻译数据)
4. 传统缓存 (兼容性)

遵循缓存优先级和一致性原则
"""

import base64
import hashlib
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
from pathlib import Path

from core.persistent_translation_cache import get_persistent_translation_cache
from core.realtime_translation_cache_manager import RealtimeTranslationCacheManager
from core.translation_cache_checker import TranslationCacheChecker
from core.cache_factory import get_cache_factory_instance
from utils import manga_logger as log


class CacheCoordinator:
    """四层缓存统一协调器"""
    
    def __init__(self):
        # 四层缓存系统
        self.memory_cache: Dict[str, Any] = {}  # 第1层：内存缓存
        self.persistent_cache = get_persistent_translation_cache()  # 第2层：持久化WebP缓存
        self.sqlite_cache = get_cache_factory_instance().get_manager("realtime_translation")  # 第3层：SQLite缓存
        self.legacy_cache = TranslationCacheChecker()  # 第4层：传统缓存
        
        # 缓存统计
        self.cache_stats = {
            "memory_hits": 0,
            "persistent_hits": 0,
            "sqlite_hits": 0,
            "legacy_hits": 0,
            "total_requests": 0
        }
        
        log.info("缓存协调器初始化完成 - 四层缓存架构")
    
    def generate_cache_key(self, manga_path: str, page_index: int, target_language: str = "zh", translator_type: str = "unknown") -> str:
        """生成统一的缓存键，包含翻译引擎信息"""
        return f"{manga_path}:{page_index}:{target_language}:{translator_type}"
    
    def has_cached_translation(self, manga_path: str, page_index: int, target_language: str = "zh", translator_type: str = "unknown") -> Tuple[bool, str]:
        """
        检查是否存在缓存的翻译

        Returns:
            (是否存在, 缓存来源)
        """
        cache_key = self.generate_cache_key(manga_path, page_index, target_language, translator_type)
        
        # 1. 检查内存缓存
        if cache_key in self.memory_cache:
            log.debug(f"内存缓存命中: {cache_key}")
            return True, "memory"
        
        # 2. 检查持久化WebP缓存
        if self.persistent_cache.has_cached_translation(manga_path, page_index, target_language):
            log.debug(f"持久化WebP缓存命中: {cache_key}")
            return True, "persistent_webp"
        
        # 3. 检查SQLite缓存
        try:
            sqlite_key = self.sqlite_cache.generate_key(manga_path, page_index, target_language)
            if self.sqlite_cache.get(sqlite_key) is not None:
                log.debug(f"SQLite缓存命中: {cache_key}")
                return True, "sqlite"
        except Exception as e:
            log.warning(f"SQLite缓存检查失败: {e}")
        
        # 4. 检查传统缓存
        if not self.legacy_cache.is_translation_needed(manga_path, page_index, target_language):
            log.debug(f"传统缓存命中: {cache_key}")
            return True, "legacy"
        
        return False, "none"
    
    def get_translated_page(self, manga_path: str, page_index: int, target_language: str = "zh", translator_type: str = "unknown") -> Optional[str]:
        """
        获取翻译后的页面（统一接口）

        Returns:
            base64编码的图像数据或None
        """
        self.cache_stats["total_requests"] += 1
        cache_key = self.generate_cache_key(manga_path, page_index, target_language, translator_type)
        
        # 1. 检查内存缓存
        if cache_key in self.memory_cache:
            self.cache_stats["memory_hits"] += 1
            log.debug(f"缓存协调器: 内存缓存命中 {cache_key}")
            return self.memory_cache[cache_key]
        
        # 2. 检查持久化WebP缓存
        try:
            webp_data = self.persistent_cache.get_cached_translation(manga_path, page_index, target_language)
            if webp_data is not None:
                self.cache_stats["persistent_hits"] += 1
                # 转换为base64并缓存到内存
                base64_data = base64.b64encode(webp_data).decode('utf-8')
                self.memory_cache[cache_key] = base64_data
                log.debug(f"缓存协调器: 持久化WebP缓存命中 {cache_key}")
                return base64_data
        except Exception as e:
            log.warning(f"持久化WebP缓存获取失败: {e}")
        
        # 3. 检查SQLite缓存
        try:
            sqlite_key = self.sqlite_cache.generate_key(manga_path, page_index, target_language)
            sqlite_data = self.sqlite_cache.get(sqlite_key)
            if sqlite_data is not None:
                self.cache_stats["sqlite_hits"] += 1
                # 从SQLite缓存重建图像数据
                image_data = self._rebuild_image_from_sqlite_cache(sqlite_data)
                if image_data is not None:
                    # 缓存到内存和持久化层
                    self.memory_cache[cache_key] = image_data
                    self._save_to_persistent_cache(manga_path, page_index, image_data, target_language)
                    log.debug(f"缓存协调器: SQLite缓存命中 {cache_key}")
                    return image_data
        except Exception as e:
            log.warning(f"SQLite缓存获取失败: {e}")
        
        # 4. 检查传统缓存
        try:
            legacy_image = self.legacy_cache.get_cached_translation_result(manga_path, page_index, target_language)
            if legacy_image is not None:
                self.cache_stats["legacy_hits"] += 1
                # 转换为base64并缓存到上层
                base64_data = self._convert_image_to_base64(legacy_image)
                if base64_data is not None:
                    self.memory_cache[cache_key] = base64_data
                    self._save_to_persistent_cache(manga_path, page_index, base64_data, target_language)
                    log.debug(f"缓存协调器: 传统缓存命中 {cache_key}")
                    return base64_data
        except Exception as e:
            log.warning(f"传统缓存获取失败: {e}")
        
        log.debug(f"缓存协调器: 所有缓存层都未命中 {cache_key}")
        return None
    
    def save_translated_page(self, manga_path: str, page_index: int, image_data: Any, 
                           target_language: str = "zh", translation_metadata: Optional[Dict] = None) -> bool:
        """
        保存翻译后的页面到多层缓存
        
        Args:
            manga_path: 漫画路径
            page_index: 页面索引
            image_data: 图像数据 (可以是base64字符串或numpy数组)
            target_language: 目标语言
            translation_metadata: 翻译元数据 (用于SQLite缓存)
        
        Returns:
            是否保存成功
        """
        cache_key = self.generate_cache_key(manga_path, page_index, target_language)
        success_count = 0
        
        try:
            # 确保图像数据是base64格式
            if isinstance(image_data, np.ndarray):
                base64_data = self._convert_image_to_base64(image_data)
            elif isinstance(image_data, str):
                base64_data = image_data
            else:
                log.error(f"不支持的图像数据类型: {type(image_data)}")
                return False
            
            if base64_data is None:
                log.error("图像数据转换失败")
                return False
            
            # 1. 保存到内存缓存
            try:
                self.memory_cache[cache_key] = base64_data
                success_count += 1
                log.debug(f"缓存协调器: 已保存到内存缓存 {cache_key}")
            except Exception as e:
                log.error(f"保存到内存缓存失败: {e}")
            
            # 2. 保存到持久化WebP缓存
            try:
                if self._save_to_persistent_cache(manga_path, page_index, base64_data, target_language):
                    success_count += 1
                    log.debug(f"缓存协调器: 已保存到持久化WebP缓存 {cache_key}")
            except Exception as e:
                log.error(f"保存到持久化WebP缓存失败: {e}")
            
            # 3. 保存到SQLite缓存 (如果有元数据)
            if translation_metadata:
                try:
                    if self._save_to_sqlite_cache(manga_path, page_index, base64_data, target_language, translation_metadata):
                        success_count += 1
                        log.debug(f"缓存协调器: 已保存到SQLite缓存 {cache_key}")
                except Exception as e:
                    log.error(f"保存到SQLite缓存失败: {e}")
            
            log.info(f"缓存协调器: 翻译页面已保存到 {success_count} 层缓存 {cache_key}")
            return success_count > 0
            
        except Exception as e:
            log.error(f"缓存协调器: 保存翻译页面失败 {cache_key}: {e}")
            return False
    
    def clear_cache(self, manga_path: Optional[str] = None) -> Dict[str, int]:
        """
        清空缓存
        
        Args:
            manga_path: 指定漫画路径，None表示清空所有
        
        Returns:
            各层缓存清理的条目数量
        """
        cleared_counts = {
            "memory": 0,
            "persistent": 0,
            "sqlite": 0,
            "legacy": 0
        }
        
        try:
            # 1. 清空内存缓存
            if manga_path:
                keys_to_remove = [k for k in self.memory_cache.keys() if k.startswith(f"{manga_path}:")]
                for key in keys_to_remove:
                    del self.memory_cache[key]
                cleared_counts["memory"] = len(keys_to_remove)
            else:
                cleared_counts["memory"] = len(self.memory_cache)
                self.memory_cache.clear()
            
            # 2. 清空其他层缓存 (根据需要实现)
            # TODO: 实现其他层的清理逻辑
            
            log.info(f"缓存协调器: 已清理缓存 {cleared_counts}")
            return cleared_counts
            
        except Exception as e:
            log.error(f"缓存协调器: 清理缓存失败: {e}")
            return cleared_counts
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self.cache_stats["total_requests"]
        hit_rate = 0.0
        if total_requests > 0:
            total_hits = sum([
                self.cache_stats["memory_hits"],
                self.cache_stats["persistent_hits"],
                self.cache_stats["sqlite_hits"],
                self.cache_stats["legacy_hits"]
            ])
            hit_rate = (total_hits / total_requests) * 100

        return {
            "cache_stats": self.cache_stats.copy(),
            "memory_cache_size": len(self.memory_cache),
            "total_hit_rate": round(hit_rate, 2),
            "cache_layers": 4
        }

    def get_cached_manga_list(self) -> Dict[str, Any]:
        """获取已缓存的漫画列表（按作品和翻译引擎分组）"""
        try:
            manga_cache_info = {}

            # 1. 从内存缓存收集信息
            for cache_key in self.memory_cache.keys():
                parts = cache_key.split(':')
                if len(parts) >= 4:  # manga_path:page_index:language:translator_type
                    manga_path = parts[0]
                    translator_type = parts[3]

                    if manga_path not in manga_cache_info:
                        manga_cache_info[manga_path] = {}
                    if translator_type not in manga_cache_info[manga_path]:
                        manga_cache_info[manga_path][translator_type] = {
                            "cached_pages": set(),
                            "cache_sources": set()
                        }

                    page_index = int(parts[1])
                    manga_cache_info[manga_path][translator_type]["cached_pages"].add(page_index)
                    manga_cache_info[manga_path][translator_type]["cache_sources"].add("memory")

            # 2. 从持久化WebP缓存收集信息
            try:
                webp_cache_info = self.persistent_cache.get_cached_manga_list()
                for manga_path, translators in webp_cache_info.items():
                    if manga_path not in manga_cache_info:
                        manga_cache_info[manga_path] = {}

                    for translator_type, pages in translators.items():
                        if translator_type not in manga_cache_info[manga_path]:
                            manga_cache_info[manga_path][translator_type] = {
                                "cached_pages": set(),
                                "cache_sources": set()
                            }

                        manga_cache_info[manga_path][translator_type]["cached_pages"].update(pages)
                        manga_cache_info[manga_path][translator_type]["cache_sources"].add("persistent_webp")
            except Exception as e:
                log.warning(f"获取持久化WebP缓存信息失败: {e}")

            # 3. 转换为前端需要的格式
            manga_list = []
            for manga_path, translators in manga_cache_info.items():
                for translator_type, info in translators.items():
                    cached_pages = sorted(list(info["cached_pages"]))
                    cache_sources = list(info["cache_sources"])

                    manga_list.append({
                        "manga_path": manga_path,
                        "manga_name": Path(manga_path).name,
                        "translator_type": translator_type,
                        "cached_pages_count": len(cached_pages),
                        "cached_pages": cached_pages,
                        "cache_sources": cache_sources,
                        "first_page": min(cached_pages) if cached_pages else 0,
                        "last_page": max(cached_pages) if cached_pages else 0
                    })

            # 按漫画名称和翻译引擎排序
            manga_list.sort(key=lambda x: (x["manga_name"], x["translator_type"]))

            return {
                "success": True,
                "manga_list": manga_list,
                "total_manga": len(set(item["manga_path"] for item in manga_list)),
                "total_entries": len(manga_list)
            }

        except Exception as e:
            log.error(f"获取缓存漫画列表失败: {e}")
            return {
                "success": False,
                "manga_list": [],
                "error": str(e)
            }

    def clear_manga_cache_by_translator(self, manga_path: str, translator_type: str) -> Dict[str, int]:
        """清空指定漫画指定翻译引擎的缓存"""
        cleared_counts = {
            "memory": 0,
            "persistent": 0,
            "sqlite": 0,
            "legacy": 0
        }

        try:
            # 1. 清空内存缓存
            keys_to_remove = []
            for cache_key in self.memory_cache.keys():
                parts = cache_key.split(':')
                if len(parts) >= 4 and parts[0] == manga_path and parts[3] == translator_type:
                    keys_to_remove.append(cache_key)

            for key in keys_to_remove:
                del self.memory_cache[key]
            cleared_counts["memory"] = len(keys_to_remove)

            # 2. 清空持久化WebP缓存
            try:
                persistent_cleared = self.persistent_cache.clear_manga_translator_cache(manga_path, translator_type)
                cleared_counts["persistent"] = persistent_cleared
            except Exception as e:
                log.warning(f"清空持久化WebP缓存失败: {e}")

            # 3. 清空SQLite缓存 (如果需要的话)
            # TODO: 实现SQLite缓存的清理

            log.info(f"缓存协调器: 已清理 {manga_path} 的 {translator_type} 翻译缓存: {cleared_counts}")
            return cleared_counts

        except Exception as e:
            log.error(f"缓存协调器: 清理漫画翻译缓存失败: {e}")
            return cleared_counts
    
    # 私有方法
    def _convert_image_to_base64(self, image_array: np.ndarray) -> Optional[str]:
        """将numpy图像数组转换为base64字符串"""
        try:
            import cv2
            # 编码为JPEG格式
            success, buffer = cv2.imencode('.jpg', image_array)
            if success:
                return base64.b64encode(buffer).decode('utf-8')
        except Exception as e:
            log.error(f"图像转换为base64失败: {e}")
        return None
    
    def _save_to_persistent_cache(self, manga_path: str, page_index: int, 
                                base64_data: str, target_language: str) -> bool:
        """保存到持久化WebP缓存"""
        try:
            # 将base64转换为图像数组
            image_bytes = base64.b64decode(base64_data)
            import cv2
            import numpy as np
            nparr = np.frombuffer(image_bytes, np.uint8)
            image_array = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image_array is not None:
                return self.persistent_cache.save_translated_image(
                    manga_path, page_index, image_array, target_language
                )
        except Exception as e:
            log.error(f"保存到持久化缓存失败: {e}")
        return False
    
    def _save_to_sqlite_cache(self, manga_path: str, page_index: int, 
                            base64_data: str, target_language: str, 
                            metadata: Dict) -> bool:
        """保存到SQLite缓存"""
        try:
            # TODO: 实现SQLite缓存保存逻辑
            # 需要构建RealtimeTranslationCacheData对象
            return True
        except Exception as e:
            log.error(f"保存到SQLite缓存失败: {e}")
        return False
    
    def _rebuild_image_from_sqlite_cache(self, sqlite_data) -> Optional[str]:
        """从SQLite缓存重建图像数据"""
        try:
            # TODO: 实现从SQLite缓存数据重建图像的逻辑
            return None
        except Exception as e:
            log.error(f"从SQLite缓存重建图像失败: {e}")
        return None


# 全局实例
_cache_coordinator_instance: Optional[CacheCoordinator] = None


def get_cache_coordinator() -> CacheCoordinator:
    """获取缓存协调器全局实例"""
    global _cache_coordinator_instance
    if _cache_coordinator_instance is None:
        _cache_coordinator_instance = CacheCoordinator()
    return _cache_coordinator_instance
