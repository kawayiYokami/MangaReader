"""
缓存管理 API - 重构版本

采用清晰的架构设计，每种缓存类型独立处理，便于维护和调试。
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
import asyncio
from datetime import datetime
import logging
import os
import math

# 导入核心业务逻辑
from core.cache_factory import get_cache_factory_instance
from core.harmonization_map_manager import get_harmonization_map_manager_instance

log = logging.getLogger(__name__)

router = APIRouter()

# ==================== 数据模型 ====================

class CacheInfo(BaseModel):
    """缓存信息模型"""
    cache_type: str
    total_entries: int
    size_bytes: int
    last_updated: Optional[str] = None

class CacheEntry(BaseModel):
    """缓存条目模型"""
    key: str
    value: Any
    value_preview: str
    size_bytes: int
    created_time: Optional[str] = None

class UpdateEntryRequest(BaseModel):
    """更新缓存条目请求"""
    key: str
    content: Any
    is_sensitive: Optional[bool] = None

class DeleteEntryRequest(BaseModel):
    """删除缓存条目请求"""
    key: str

# ==================== 抽象基类 ====================

class CacheHandler(ABC):
    """缓存处理器抽象基类"""
    
    def __init__(self, cache_type: str):
        self.cache_type = cache_type
        self.log = logging.getLogger(f"{__name__}.{cache_type}")
    
    @abstractmethod
    async def get_info(self) -> CacheInfo:
        """获取缓存信息"""
        pass
    
    @abstractmethod
    async def get_entries(self, page: int, page_size: int, search: Optional[str] = None) -> Dict[str, Any]:
        """获取缓存条目列表"""
        pass
    
    @abstractmethod
    async def refresh(self) -> Dict[str, Any]:
        """刷新缓存"""
        pass
    
    @abstractmethod
    async def clear(self) -> Dict[str, Any]:
        """清空缓存"""
        pass
    
    @abstractmethod
    async def update_entry(self, request: UpdateEntryRequest) -> Dict[str, Any]:
        """更新缓存条目"""
        pass
    
    @abstractmethod
    async def delete_entry(self, key: str) -> Dict[str, Any]:
        """删除缓存条目"""
        pass

# ==================== 具体实现类 ====================

class MangaListCacheHandler(CacheHandler):
    """漫画列表缓存处理器"""
    
    def __init__(self):
        super().__init__("manga_list")
        self.manager = get_cache_factory_instance().get_manager("manga_list")
    
    async def get_info(self) -> CacheInfo:
        """获取漫画列表缓存信息"""
        try:
            # 获取所有目录条目
            cached_dirs = self.manager.get_all_entries_for_display()
            total_entries = 0
            
            # 计算总漫画数量
            for dir_entry in cached_dirs:
                directory_path = dir_entry.get("directory_path")
                if directory_path:
                    manga_list = self.manager.get(directory_path)
                    if manga_list:
                        total_entries += len(manga_list)
            
            # 获取缓存大小
            size_bytes = 0
            if hasattr(self.manager, 'get_cache_size_bytes'):
                size_bytes = await self.manager.get_cache_size_bytes() if asyncio.iscoroutinefunction(self.manager.get_cache_size_bytes) else self.manager.get_cache_size_bytes()
            
            return CacheInfo(
                cache_type=self.cache_type,
                total_entries=total_entries,
                size_bytes=size_bytes,
                last_updated=datetime.now().isoformat()
            )
        except Exception as e:
            self.log.error(f"获取漫画列表缓存信息失败: {e}")
            return CacheInfo(cache_type=self.cache_type, total_entries=0, size_bytes=0)
    
    async def get_entries(self, page: int, page_size: int, search: Optional[str] = None) -> Dict[str, Any]:
        """获取漫画列表缓存条目"""
        try:
            # 获取所有漫画条目
            all_manga = []
            cached_dirs = self.manager.get_all_entries_for_display()
            
            for dir_entry in cached_dirs:
                directory_path = dir_entry.get("directory_path")
                if directory_path:
                    manga_list = self.manager.get(directory_path)
                    if manga_list:
                        all_manga.extend(manga_list)
            
            # 搜索过滤
            if search:
                query = search.lower()
                filtered_manga = []
                for manga in all_manga:
                    title = str(manga.get("title", "")).lower()
                    file_path = str(manga.get("file_path", "")).lower()
                    tags = str(manga.get("tags", [])).lower()
                    if query in title or query in file_path or query in tags:
                        filtered_manga.append(manga)
                all_manga = filtered_manga
            
            # 分页
            total = len(all_manga)
            start = (page - 1) * page_size
            end = start + page_size
            page_manga = all_manga[start:end]
            
            # 格式化条目
            entries = []
            for manga in page_manga:
                entries.append(self._format_manga_entry(manga))
            
            return {
                "entries": entries,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
            }
        except Exception as e:
            self.log.error(f"获取漫画列表缓存条目失败: {e}")
            raise HTTPException(status_code=500, detail=f"获取漫画列表缓存条目失败: {e}")
    
    def _format_manga_entry(self, manga: Dict[str, Any]) -> Dict[str, Any]:
        """格式化漫画条目"""
        file_path = manga.get("file_path", "")
        is_directory = os.path.isdir(file_path) if file_path else False
        
        # 处理dimension_variance字段
        dimension_variance = manga.get("dimension_variance")
        if is_directory:
            variance_str = "不适用"
            dimension_variance = "N/A"
        elif isinstance(dimension_variance, (int, float)):
            variance_str = f"{dimension_variance:.3f}"
        elif dimension_variance is None:
            variance_str = "未分析"
        else:
            variance_str = str(dimension_variance)
        
        # 格式化文件大小
        file_size = manga.get("file_size", 0)
        if file_size > 0:
            if file_size >= 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"
            elif file_size >= 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            else:
                size_str = f"{file_size} B"
        else:
            size_str = "未知"
        
        is_likely_manga = manga.get("is_likely_manga", "未知")
        total_pages = manga.get("total_pages", 0)
        tags = manga.get("tags", [])
        
        return {
            "key": file_path,
            "value": manga,
            "value_preview": f"漫画: {manga.get('title', 'Unknown')} | 方差: {variance_str} | 可能是漫画: {is_likely_manga} | 页数: {total_pages} | 大小: {size_str}",
            "size_bytes": len(str(manga)) * 2,
            "created_time": datetime.fromtimestamp(manga.get("last_modified", 0)).isoformat() if manga.get("last_modified") else None,
            # 额外字段
            "dimension_variance": dimension_variance,
            "is_likely_manga": is_likely_manga,
            "total_pages": total_pages,
            "file_size": file_size,
            "tags_count": len(tags)
        }
    
    async def refresh(self) -> Dict[str, Any]:
        """刷新漫画列表缓存"""
        try:
            if hasattr(self.manager, 'refresh'):
                result = await self.manager.refresh() if asyncio.iscoroutinefunction(self.manager.refresh) else self.manager.refresh()
                return {"success": True, "message": "漫画列表缓存刷新完成", "result": result}
            else:
                return {"success": True, "message": "漫画列表缓存不支持显式刷新"}
        except Exception as e:
            self.log.error(f"刷新漫画列表缓存失败: {e}")
            return {"success": False, "message": f"刷新失败: {e}"}
    
    async def clear(self) -> Dict[str, Any]:
        """清空漫画列表缓存"""
        try:
            if hasattr(self.manager, 'clear'):
                await self.manager.clear() if asyncio.iscoroutinefunction(self.manager.clear) else self.manager.clear()
                return {"success": True, "message": "漫画列表缓存已清空"}
            else:
                return {"success": False, "message": "漫画列表缓存不支持清空操作"}
        except Exception as e:
            self.log.error(f"清空漫画列表缓存失败: {e}")
            return {"success": False, "message": f"清空失败: {e}"}
    
    async def update_entry(self, request: UpdateEntryRequest) -> Dict[str, Any]:
        """更新漫画列表缓存条目"""
        return {"success": False, "message": "漫画列表缓存不支持更新操作"}
    
    async def delete_entry(self, key: str) -> Dict[str, Any]:
        """删除漫画列表缓存条目"""
        try:
            if hasattr(self.manager, 'delete_entry'):
                result = await self.manager.delete_entry(key) if asyncio.iscoroutinefunction(self.manager.delete_entry) else self.manager.delete_entry(key)
                return {"success": True, "message": f"漫画条目已删除: {key[:50]}..."}
            else:
                return {"success": False, "message": "漫画列表缓存不支持删除单个条目"}
        except Exception as e:
            self.log.error(f"删除漫画列表缓存条目失败: {e}")
            return {"success": False, "message": f"删除失败: {e}"}


class OcrCacheHandler(CacheHandler):
    """OCR缓存处理器"""

    def __init__(self):
        super().__init__("ocr")
        self.manager = get_cache_factory_instance().get_manager("ocr")

    async def get_info(self) -> CacheInfo:
        """获取OCR缓存信息"""
        try:
            entries = self.manager.get_all_entries_for_display() if hasattr(self.manager, 'get_all_entries_for_display') else []
            total_entries = len(entries) if entries else 0

            size_bytes = 0
            if hasattr(self.manager, 'get_cache_size_bytes'):
                size_bytes = await self.manager.get_cache_size_bytes() if asyncio.iscoroutinefunction(self.manager.get_cache_size_bytes) else self.manager.get_cache_size_bytes()

            return CacheInfo(
                cache_type=self.cache_type,
                total_entries=total_entries,
                size_bytes=size_bytes,
                last_updated=datetime.now().isoformat()
            )
        except Exception as e:
            self.log.error(f"获取OCR缓存信息失败: {e}")
            return CacheInfo(cache_type=self.cache_type, total_entries=0, size_bytes=0)

    async def get_entries(self, page: int, page_size: int, search: Optional[str] = None) -> Dict[str, Any]:
        """获取OCR缓存条目"""
        try:
            all_entries = self.manager.get_all_entries_for_display() if hasattr(self.manager, 'get_all_entries_for_display') else []

            # 搜索过滤
            if search:
                query = search.lower()
                filtered_entries = []
                for entry in all_entries:
                    cache_key = str(entry.get("cache_key", "")).lower()
                    file_name = str(entry.get("file_name", "")).lower()
                    page_num = str(entry.get("page_num", "")).lower()
                    if query in cache_key or query in file_name or query in page_num:
                        filtered_entries.append(entry)
                all_entries = filtered_entries

            # 分页
            total = len(all_entries)
            start = (page - 1) * page_size
            end = start + page_size
            page_entries = all_entries[start:end]

            # 格式化条目
            entries = []
            for entry in page_entries:
                entries.append(self._format_ocr_entry(entry))

            return {
                "entries": entries,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
            }
        except Exception as e:
            self.log.error(f"获取OCR缓存条目失败: {e}")
            raise HTTPException(status_code=500, detail=f"获取OCR缓存条目失败: {e}")

    def _format_ocr_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """格式化OCR条目"""
        cache_key = entry.get("cache_key", "unknown_key")
        file_name = entry.get("file_name", "Unknown")
        page_num = entry.get("page_num", 0)

        return {
            "key": cache_key,
            "value": entry,
            "value_preview": f"OCR: {file_name} 第{page_num}页",
            "size_bytes": len(str(entry)) * 2,
            "created_time": datetime.fromtimestamp(entry.get("last_modified", 0)).isoformat() if entry.get("last_modified") else None
        }

    async def refresh(self) -> Dict[str, Any]:
        """刷新OCR缓存"""
        try:
            if hasattr(self.manager, 'refresh'):
                result = await self.manager.refresh() if asyncio.iscoroutinefunction(self.manager.refresh) else self.manager.refresh()
                return {"success": True, "message": "OCR缓存刷新完成", "result": result}
            else:
                return {"success": True, "message": "OCR缓存不支持显式刷新"}
        except Exception as e:
            self.log.error(f"刷新OCR缓存失败: {e}")
            return {"success": False, "message": f"刷新失败: {e}"}

    async def clear(self) -> Dict[str, Any]:
        """清空OCR缓存"""
        try:
            if hasattr(self.manager, 'clear'):
                await self.manager.clear() if asyncio.iscoroutinefunction(self.manager.clear) else self.manager.clear()
                return {"success": True, "message": "OCR缓存已清空"}
            else:
                return {"success": False, "message": "OCR缓存不支持清空操作"}
        except Exception as e:
            self.log.error(f"清空OCR缓存失败: {e}")
            return {"success": False, "message": f"清空失败: {e}"}

    async def update_entry(self, request: UpdateEntryRequest) -> Dict[str, Any]:
        """更新OCR缓存条目"""
        return {"success": False, "message": "OCR缓存不支持更新操作"}

    async def delete_entry(self, key: str) -> Dict[str, Any]:
        """删除OCR缓存条目"""
        try:
            if hasattr(self.manager, 'delete_entry'):
                result = await self.manager.delete_entry(key) if asyncio.iscoroutinefunction(self.manager.delete_entry) else self.manager.delete_entry(key)
                return {"success": True, "message": f"OCR条目已删除: {key[:50]}..."}
            else:
                return {"success": False, "message": "OCR缓存不支持删除单个条目"}
        except Exception as e:
            self.log.error(f"删除OCR缓存条目失败: {e}")
            return {"success": False, "message": f"删除失败: {e}"}


class TranslationCacheHandler(CacheHandler):
    """翻译缓存处理器"""

    def __init__(self):
        super().__init__("translation")
        self.manager = get_cache_factory_instance().get_manager("translation")

    async def get_info(self) -> CacheInfo:
        """获取翻译缓存信息"""
        try:
            entries = self.manager.get_all_entries_for_display() if hasattr(self.manager, 'get_all_entries_for_display') else []
            total_entries = len(entries) if entries else 0

            size_bytes = 0
            if hasattr(self.manager, 'get_cache_size_bytes'):
                size_bytes = await self.manager.get_cache_size_bytes() if asyncio.iscoroutinefunction(self.manager.get_cache_size_bytes) else self.manager.get_cache_size_bytes()

            return CacheInfo(
                cache_type=self.cache_type,
                total_entries=total_entries,
                size_bytes=size_bytes,
                last_updated=datetime.now().isoformat()
            )
        except Exception as e:
            self.log.error(f"获取翻译缓存信息失败: {e}")
            return CacheInfo(cache_type=self.cache_type, total_entries=0, size_bytes=0)

    async def get_entries(self, page: int, page_size: int, search: Optional[str] = None) -> Dict[str, Any]:
        """获取翻译缓存条目"""
        try:
            all_entries = self.manager.get_all_entries_for_display() if hasattr(self.manager, 'get_all_entries_for_display') else []

            # 搜索过滤
            if search:
                query = search.lower()
                filtered_entries = []
                for entry in all_entries:
                    cache_key = str(entry.get("cache_key", "")).lower()
                    original_text = str(entry.get("original_text", "")).lower()
                    translated_text = str(entry.get("translated_text", "")).lower()
                    if query in cache_key or query in original_text or query in translated_text:
                        filtered_entries.append(entry)
                all_entries = filtered_entries

            # 分页
            total = len(all_entries)
            start = (page - 1) * page_size
            end = start + page_size
            page_entries = all_entries[start:end]

            # 格式化条目
            entries = []
            for entry in page_entries:
                entries.append(self._format_translation_entry(entry))

            return {
                "entries": entries,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
            }
        except Exception as e:
            self.log.error(f"获取翻译缓存条目失败: {e}")
            raise HTTPException(status_code=500, detail=f"获取翻译缓存条目失败: {e}")

    def _format_translation_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """格式化翻译条目"""
        cache_key = entry.get("cache_key", "unknown_key")
        original = entry.get('original_text_sample', entry.get('original_text', ''))
        translated = entry.get('translated_text', '')
        is_sensitive = entry.get('is_sensitive', False)

        original_preview = original[:30] + "..." if len(original) > 30 else original
        translated_preview = translated[:30] + "..." if len(translated) > 30 else translated

        # 处理时间戳转换
        created_time = None
        last_updated = entry.get("last_updated")
        if last_updated:
            try:
                # 如果是字符串，直接使用；如果是数字，转换为ISO格式
                if isinstance(last_updated, str):
                    created_time = last_updated
                else:
                    created_time = datetime.fromtimestamp(float(last_updated)).isoformat()
            except (ValueError, TypeError) as e:
                self.log.warning(f"无法解析时间戳 {last_updated}: {e}")
                created_time = str(last_updated)

        return {
            "key": cache_key,
            "value": translated,
            "original_text": original,
            "value_preview": f"翻译: {original_preview} → {translated_preview}",
            "is_sensitive": is_sensitive,
            "size_bytes": len(original.encode('utf-8')) + len(translated.encode('utf-8')),
            "created_time": created_time
        }

    async def refresh(self) -> Dict[str, Any]:
        """刷新翻译缓存"""
        try:
            if hasattr(self.manager, 'refresh'):
                result = await self.manager.refresh() if asyncio.iscoroutinefunction(self.manager.refresh) else self.manager.refresh()
                return {"success": True, "message": "翻译缓存刷新完成", "result": result}
            else:
                return {"success": True, "message": "翻译缓存不支持显式刷新"}
        except Exception as e:
            self.log.error(f"刷新翻译缓存失败: {e}")
            return {"success": False, "message": f"刷新失败: {e}"}

    async def clear(self) -> Dict[str, Any]:
        """清空翻译缓存"""
        try:
            if hasattr(self.manager, 'clear'):
                await self.manager.clear() if asyncio.iscoroutinefunction(self.manager.clear) else self.manager.clear()
                return {"success": True, "message": "翻译缓存已清空"}
            else:
                return {"success": False, "message": "翻译缓存不支持清空操作"}
        except Exception as e:
            self.log.error(f"清空翻译缓存失败: {e}")
            return {"success": False, "message": f"清空失败: {e}"}

    async def update_entry(self, request: UpdateEntryRequest) -> Dict[str, Any]:
        """更新翻译缓存条目"""
        try:
            if hasattr(self.manager, 'update_entry'):
                result = await self.manager.update_entry(request.key, request.content, request.is_sensitive) if asyncio.iscoroutinefunction(self.manager.update_entry) else self.manager.update_entry(request.key, request.content, request.is_sensitive)
                return {"success": True, "message": f"翻译条目已更新: {request.key[:50]}..."}
            else:
                return {"success": False, "message": "翻译缓存不支持更新操作"}
        except Exception as e:
            self.log.error(f"更新翻译缓存条目失败: {e}")
            return {"success": False, "message": f"更新失败: {e}"}

    async def delete_entry(self, key: str) -> Dict[str, Any]:
        """删除翻译缓存条目"""
        try:
            if hasattr(self.manager, 'delete_entry'):
                result = await self.manager.delete_entry(key) if asyncio.iscoroutinefunction(self.manager.delete_entry) else self.manager.delete_entry(key)
                return {"success": True, "message": f"翻译条目已删除: {key[:50]}..."}
            else:
                return {"success": False, "message": "翻译缓存不支持删除单个条目"}
        except Exception as e:
            self.log.error(f"删除翻译缓存条目失败: {e}")
            return {"success": False, "message": f"删除失败: {e}"}


class HarmonizationMapCacheHandler(CacheHandler):
    """和谐映射缓存处理器"""

    def __init__(self):
        super().__init__("harmonization_map")
        self.manager = get_harmonization_map_manager_instance()

    async def get_info(self) -> CacheInfo:
        """获取和谐映射缓存信息"""
        try:
            mappings = self.manager.get_all_mappings()
            total_entries = len(mappings)

            size_bytes = 0
            if os.path.exists(self.manager.json_file_path):
                size_bytes = os.path.getsize(self.manager.json_file_path)

            return CacheInfo(
                cache_type=self.cache_type,
                total_entries=total_entries,
                size_bytes=size_bytes,
                last_updated=datetime.now().isoformat()
            )
        except Exception as e:
            self.log.error(f"获取和谐映射缓存信息失败: {e}")
            return CacheInfo(cache_type=self.cache_type, total_entries=0, size_bytes=0)

    async def get_entries(self, page: int, page_size: int, search: Optional[str] = None) -> Dict[str, Any]:
        """获取和谐映射缓存条目"""
        try:
            mappings = self.manager.get_all_mappings()
            all_entries = [{"key": k, "value": v} for k, v in mappings.items()]

            # 搜索过滤
            if search:
                query = search.lower()
                filtered_entries = []
                for entry in all_entries:
                    original_text = str(entry.get("key", "")).lower()
                    harmonized_text = str(entry.get("value", "")).lower()
                    if query in original_text or query in harmonized_text:
                        filtered_entries.append(entry)
                all_entries = filtered_entries

            # 分页
            total = len(all_entries)
            start = (page - 1) * page_size
            end = start + page_size
            page_entries = all_entries[start:end]

            # 格式化条目
            entries = []
            for entry in page_entries:
                entries.append(self._format_harmonization_entry(entry))

            return {
                "entries": entries,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
            }
        except Exception as e:
            self.log.error(f"获取和谐映射缓存条目失败: {e}")
            raise HTTPException(status_code=500, detail=f"获取和谐映射缓存条目失败: {e}")

    def _format_harmonization_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """格式化和谐映射条目"""
        original_text = entry.get("key", "unknown_key")
        harmonized_text = entry.get("value", "")

        return {
            "key": original_text,
            "value": harmonized_text,
            "value_preview": f"和谐映射: {original_text} → {harmonized_text}",
            "size_bytes": len(original_text.encode('utf-8')) + len(harmonized_text.encode('utf-8')),
            "created_time": None
        }

    async def refresh(self) -> Dict[str, Any]:
        """刷新和谐映射缓存"""
        try:
            self.manager.reload_mappings()
            return {"success": True, "message": "和谐映射缓存已从文件重新加载"}
        except Exception as e:
            self.log.error(f"刷新和谐映射缓存失败: {e}")
            return {"success": False, "message": f"刷新失败: {e}"}

    async def clear(self) -> Dict[str, Any]:
        """清空和谐映射缓存"""
        try:
            if hasattr(self.manager, 'clear_all_mappings'):
                self.manager.clear_all_mappings()
                return {"success": True, "message": "和谐映射缓存已清空"}
            else:
                return {"success": False, "message": "和谐映射缓存不支持清空操作"}
        except Exception as e:
            self.log.error(f"清空和谐映射缓存失败: {e}")
            return {"success": False, "message": f"清空失败: {e}"}

    async def update_entry(self, request: UpdateEntryRequest) -> Dict[str, Any]:
        """更新和谐映射缓存条目"""
        try:
            self.manager.add_mapping(request.key, request.content)
            return {"success": True, "message": f"和谐映射已更新: {request.key[:30]}..."}
        except Exception as e:
            self.log.error(f"更新和谐映射缓存条目失败: {e}")
            return {"success": False, "message": f"更新失败: {e}"}

    async def delete_entry(self, key: str) -> Dict[str, Any]:
        """删除和谐映射缓存条目"""
        try:
            if hasattr(self.manager, 'remove_mapping'):
                self.manager.remove_mapping(key)
                return {"success": True, "message": f"和谐映射已删除: {key[:30]}..."}
            else:
                return {"success": False, "message": "和谐映射缓存不支持删除单个条目"}
        except Exception as e:
            self.log.error(f"删除和谐映射缓存条目失败: {e}")
            return {"success": False, "message": f"删除失败: {e}"}


class PersistentTranslationCacheHandler(CacheHandler):
    """持久化翻译缓存处理器"""

    def __init__(self):
        super().__init__("persistent_translation")
        self.manager = get_cache_factory_instance().get_manager("persistent_translation")

    async def get_info(self) -> CacheInfo:
        """获取持久化翻译缓存信息"""
        try:
            stats = self.manager.get_cache_statistics()
            return CacheInfo(
                cache_type=self.cache_type,
                total_entries=stats.get("total_entries", 0),
                size_bytes=stats.get("cache_size_bytes", 0),
                last_updated=datetime.now().isoformat()
            )
        except Exception as e:
            self.log.error(f"获取持久化翻译缓存信息失败: {e}")
            return CacheInfo(cache_type=self.cache_type, total_entries=0, size_bytes=0)

    async def get_entries(self, page: int, page_size: int, search: Optional[str] = None) -> Dict[str, Any]:
        """获取持久化翻译缓存条目"""
        try:
            all_entries = self.manager.get_all_entries_for_display()

            if search:
                query = search.lower()
                all_entries = [
                    entry for entry in all_entries
                    if query in str(entry.get("manga_name", "")).lower() or \
                       query in str(entry.get("manga_path", "")).lower()
                ]

            total = len(all_entries)
            start = (page - 1) * page_size
            end = start + page_size
            page_items = all_entries[start:end]

            formatted_entries = [self._format_entry(item) for item in page_items]

            return {
                "entries": formatted_entries,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
            }
        except Exception as e:
            self.log.error(f"获取持久化翻译缓存条目失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def _format_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """格式化条目"""
        cache_key = entry.get("cache_key", "N/A")
        manga_name = entry.get("manga_name", "N/A")
        page_display = entry.get("page_display", "N/A")

        return {
            "key": cache_key,
            "value": entry,
            "value_preview": f"漫画: {manga_name} - {page_display}",
            "size_bytes": 0, # 大小在统计信息中提供
            "created_time": entry.get("created_at"),
        }

    async def clear(self) -> Dict[str, Any]:
        """清空持久化翻译缓存"""
        try:
            self.manager.clear()
            return {"success": True, "message": "持久化翻译缓存已清空"}
        except Exception as e:
            self.log.error(f"清空持久化翻译缓存失败: {e}")
            return {"success": False, "message": str(e)}

    async def delete_entry(self, key: str) -> Dict[str, Any]:
        """删除持久化翻译缓存中的单个条目（按漫画路径）"""
        try:
            # 'key' 在这里是 manga_path
            deleted_count = self.manager.delete_by_manga(key)
            if deleted_count > 0:
                return {"success": True, "message": f"已删除漫画 {os.path.basename(key)} 的 {deleted_count} 个缓存条目"}
            else:
                return {"success": False, "message": "未找到相关缓存条目"}
        except Exception as e:
            self.log.error(f"删除持久化翻译缓存条目失败: {e}")
            return {"success": False, "message": str(e)}

    async def refresh(self) -> Dict[str, Any]:
        return {"success": True, "message": "持久化翻译缓存不支持显式刷新"}

    async def update_entry(self, request: UpdateEntryRequest) -> Dict[str, Any]:
        return {"success": False, "message": "持久化翻译缓存不支持更新单个条目"}


# ==================== 缓存处理器工厂 ====================

class CacheHandlerFactory:
    """缓存处理器工厂"""

    _handlers = {
        "manga_list": MangaListCacheHandler,
        "ocr": OcrCacheHandler,
        "translation": TranslationCacheHandler,
        "harmonization_map": HarmonizationMapCacheHandler,
        "persistent_translation": PersistentTranslationCacheHandler
    }

    @classmethod
    def get_handler(cls, cache_type: str) -> CacheHandler:
        """获取指定类型的缓存处理器"""
        if cache_type not in cls._handlers:
            raise ValueError(f"不支持的缓存类型: {cache_type}")

        handler_class = cls._handlers[cache_type]
        return handler_class()

    @classmethod
    def get_supported_types(cls) -> List[str]:
        """获取支持的缓存类型列表"""
        return list(cls._handlers.keys())


# ==================== 工具函数 ====================

def format_bytes(bytes_val: int) -> str:
    """格式化字节数为可读字符串"""
    if bytes_val == 0:
        return "0 B"

    k = 1024
    sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    if bytes_val > 0:
        i = min(len(sizes) - 1, max(0, int(math.log(bytes_val, k))))

    denominator = math.pow(k, i)
    if denominator == 0:
        return "0 B"

    formatted_val = bytes_val / denominator
    precision = 1 if i >= 2 else (2 if i == 1 else 0)
    return f"{formatted_val:.{precision}f} {sizes[i]}"


# ==================== API 路由 ====================

@router.get("/health")
async def cache_health():
    """缓存模块健康检查"""
    return {"status": "healthy", "module": "cache"}


@router.get("/types")
async def get_cache_types():
    """获取可用的缓存类型"""
    try:
        cache_types = [
            {"key": "manga_list", "name": "漫画列表", "description": "漫画文件扫描结果缓存"},
            {"key": "ocr", "name": "OCR", "description": "文字识别结果缓存"},
            {"key": "translation", "name": "翻译", "description": "翻译结果缓存"},
            {"key": "harmonization_map", "name": "和谐映射", "description": "内容和谐化映射缓存"},
            {"key": "persistent_translation", "name": "持久化翻译", "description": "按页存储的完整翻译结果缓存"}
        ]
        return {"cache_types": cache_types}
    except Exception as e:
        log.error(f"获取缓存类型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_all_cache_stats():
    """获取所有缓存类型的统计信息"""
    try:
        stats = {}
        total_size_bytes = 0

        for cache_type in CacheHandlerFactory.get_supported_types():
            try:
                handler = CacheHandlerFactory.get_handler(cache_type)
                info = await handler.get_info()
                stats[cache_type] = {
                    "entries": info.total_entries,
                    "size": info.size_bytes
                }
                total_size_bytes += info.size_bytes
            except Exception as e:
                log.error(f"获取 {cache_type} 缓存统计失败: {e}")
                stats[cache_type] = {"entries": 0, "size": 0}

        return {
            "stats": stats,
            "total_size": format_bytes(total_size_bytes),
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        log.error(f"获取所有缓存统计失败: {e}")
        cache_types_default = CacheHandlerFactory.get_supported_types()
        return {
            "stats": {ctype: {"entries": 0, "size": 0} for ctype in cache_types_default},
            "total_size": "0 B",
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }


@router.get("/{cache_type}/info")
async def get_cache_info(cache_type: str):
    """获取指定缓存类型的详细信息"""
    try:
        handler = CacheHandlerFactory.get_handler(cache_type)
        info = await handler.get_info()
        return info.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"获取 {cache_type} 缓存信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取缓存信息失败: {e}")


@router.get("/{cache_type}/entries")
async def get_cache_entries(
    cache_type: str,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None
):
    """获取指定缓存类型的条目列表（分页和搜索）"""
    try:
        # 确保参数类型正确
        page = int(page) if isinstance(page, str) else page
        page_size = int(page_size) if isinstance(page_size, str) else page_size

        handler = CacheHandlerFactory.get_handler(cache_type)
        result = await handler.get_entries(page, page_size, search)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"获取 {cache_type} 缓存条目失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取缓存条目失败: {e}")


@router.post("/{cache_type}/refresh")
async def refresh_cache(cache_type: str):
    """刷新指定类型的缓存"""
    try:
        handler = CacheHandlerFactory.get_handler(cache_type)
        result = await handler.refresh()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"刷新 {cache_type} 缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"刷新缓存失败: {e}")


@router.post("/{cache_type}/clear")
async def clear_cache(cache_type: str):
    """清空指定类型的缓存"""
    try:
        handler = CacheHandlerFactory.get_handler(cache_type)
        result = await handler.clear()

        # 如果清空成功，广播事件
        if result.get("success", False):
            from core.cache_factory import broadcast_cache_event
            await broadcast_cache_event("cleared", cache_type, {"message": result.get("message", "")})

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"清空 {cache_type} 缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空缓存失败: {e}")


@router.put("/{cache_type}/entries")
async def update_cache_entry(cache_type: str, request: UpdateEntryRequest):
    """更新指定缓存类型的条目"""
    try:
        handler = CacheHandlerFactory.get_handler(cache_type)
        result = await handler.update_entry(request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"更新 {cache_type} 缓存条目失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新缓存条目失败: {e}")


@router.delete("/{cache_type}/entries/{key}")
async def delete_cache_entry(cache_type: str, key: str):
    """删除指定缓存类型的条目"""
    try:
        handler = CacheHandlerFactory.get_handler(cache_type)
        result = await handler.delete_entry(key)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"删除 {cache_type} 缓存条目失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除缓存条目失败: {e}")
