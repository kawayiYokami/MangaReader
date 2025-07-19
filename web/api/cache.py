"""
缓存管理 API - 重构版本

采用清晰的架构设计，每种缓存类型独立处理，便于维护和调试。
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
import asyncio
import json
from datetime import datetime
import logging
import os
import math

# 导入核心业务逻辑
from core.core_cache.cache_factory import get_cache_factory_instance
from core.harmonization_map_manager import get_harmonization_map_manager_instance
from core.core_cache.manga_cache import LIBRARY_KEY

log = logging.getLogger(__name__)

# ==================== 安全依赖项 ====================

async def verify_local_access(request: Request):
    """
    依赖项：只允许来自本地回环地址的请求访问。
    """
    if request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(
            status_code=403,
            detail="此功能仅限桌面应用或本地访问"
        )

# 应用安全依赖项到整个路由
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
    async def get_entries(self, page: int, page_size: int, search: Optional[str] = None, **kwargs) -> Dict[str, Any]:
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
    """漫画列表缓存处理器 - 已重构"""

    def __init__(self):
        super().__init__("manga_list")
        self.manager = get_cache_factory_instance().get_manager("manga_list")

    async def get_info(self) -> CacheInfo:
        """获取漫画列表缓存信息"""
        try:
            # 调用在 Core 层新添加的 get_manga_count 方法
            total_entries = await self.manager.get_manga_count()
            size_bytes = self.manager.get_cache_size_bytes()
            last_updated = datetime.now().isoformat()

            return CacheInfo(
                cache_type=self.cache_type,
                total_entries=total_entries,
                size_bytes=size_bytes,
                last_updated=last_updated
            )
        except Exception as e:
            self.log.error(f"获取漫画列表缓存信息失败: {e}", exc_info=True)
            return CacheInfo(
                cache_type=self.cache_type,
                total_entries=0,
                size_bytes=0,
                last_updated=datetime.now().isoformat()
            )

    async def get_entries(self, page: int, page_size: int, search: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """获取漫画列表缓存条目，在内存中进行分页和搜索"""
        try:
            # 1. 调用 Core 层方法获取所有数据
            all_manga = await self.manager.get_manga_list_for_display()
            
            # 2. 在内存中进行搜索过滤
            if search:
                query = search.lower()
                all_manga = [
                    m for m in all_manga
                    if query in m.get("title", "").lower() or query in m.get("file_path", "").lower()
                ]

            # 3. 在内存中进行分页
            total = len(all_manga)
            start = (page - 1) * page_size
            end = start + page_size
            paginated_manga = all_manga[start:end]

            # 4. 格式化当前页的条目
            entries = [self._format_manga_entry(m) for m in paginated_manga]
            
            return {
                "entries": entries,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
                "filter_applied": None
            }
        except Exception as e:
            self.log.error(f"获取漫画列表缓存条目失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"获取漫画列表缓存条目失败: {e}")

    def _format_manga_entry(self, manga: Dict[str, Any]) -> Dict[str, Any]:
        """格式化从 get_manga_list_for_display 返回的字典"""
        file_path = manga.get("file_path", "")
        
        # 格式化文件大小
        file_size = manga.get("file_size", 0)
        size_str = format_bytes(file_size) if file_size else "未知"
        
        total_pages = manga.get("total_pages", 0)
        tags_list = manga.get("tags", [])
        tags_count = len(tags_list)
        
        # last_modified 已经是 ISO 格式的字符串
        created_time = manga.get("last_modified")

        return {
            "key": file_path,
            "value": manga,
            "value_preview": f"漫画: {manga.get('title', 'N/A')} | 页数: {total_pages} | 大小: {size_str} | 标签数: {tags_count}",
            "size_bytes": file_size, # 使用真实大小
            "created_time": created_time,
            # 额外字段，用于前端显示
            "title": manga.get("title"),
            "total_pages": total_pages,
            "file_size": file_size,
            "tags_count": tags_count,
            "tags": tags_list,
            "file_type": manga.get("file_type")
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

    async def get_entries(self, page: int, page_size: int, search: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """获取OCR缓存条目"""
        try:
            all_entries = self.manager.get_all_entries_for_display() if hasattr(self.manager, 'get_all_entries_for_display') else []

            # 搜索过滤
            if search:
                query = search.lower()
                filtered_entries = []
                for entry in all_entries:
                    # 先解析 value 字段的 JSON
                    try:
                        value_data = json.loads(entry.get("value", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        value_data = {}

                    # 然后在解析后的数据和顶层键中搜索
                    cache_key_str = str(entry.get("key", "")).lower()
                    file_name_str = str(value_data.get("file_name", "")).lower()
                    page_num_str = str(value_data.get("page_num", "")).lower()

                    if query in cache_key_str or query in file_name_str or query in page_num_str:
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
        """
        使用数据库中存储的元数据格式化OCR条目，提供清晰的预览。
        """
        cache_key = entry.get("key", "unknown_key")
        value_str = entry.get("value", "{}")
        created_time = entry.get("last_updated")
        
        # 直接从entry中获取元数据
        manga_name = entry.get("manga_name")
        page_index = entry.get("page_index")

        try:
            value_data = json.loads(value_str)
            text_count = len(value_data) if isinstance(value_data, list) else 0
            
            # 构建一个清晰、人类可读的预览字符串
            if manga_name is not None and page_index is not None:
                preview = f"OCR: {manga_name} 第{page_index + 1}页 ({text_count}个文本块)"
            else:
                # 兼容旧数据或元数据缺失的情况
                preview = f"OCR: Unknown 第N/A页 ({text_count}个文本块)"
                
        except (json.JSONDecodeError, TypeError):
            value_data = {}
            preview = "无效或格式不兼容的OCR数据"

        return {
            "key": cache_key, # key 仍然需要用于删除等操作
            "value": value_data,
            "value_preview": preview,
            "size_bytes": len(value_str.encode('utf-8')),
            "created_time": created_time
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

    async def get_entries(self, page: int, page_size: int, search: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """获取翻译缓存条目"""
        try:
            all_entries = self.manager.get_all_entries_for_display() if hasattr(self.manager, 'get_all_entries_for_display') else []
            filter_sensitive = kwargs.get("filter_sensitive", False)

            # 1. 应用敏感内容筛选
            if filter_sensitive:
                all_entries = [entry for entry in all_entries if entry.get("is_sensitive", False)]

            # 2. 应用文本搜索过滤
            if search:
                query = search.lower()
                filtered_entries = []
                for entry in all_entries:
                    # 先解析 value 字段的 JSON
                    try:
                        value_data = json.loads(entry.get("value", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        value_data = {}
                    
                    # 然后在解析后的数据和顶层键中搜索
                    cache_key_str = str(entry.get("key", "")).lower()
                    original_text_str = str(value_data.get("original_text", "")).lower()
                    translated_text_str = str(value_data.get("translated_text", "")).lower()

                    if query in cache_key_str or query in original_text_str or query in translated_text_str:
                        filtered_entries.append(entry)
                all_entries = filtered_entries

            # 3. 分页
            total = len(all_entries)
            start = (page - 1) * page_size
            end = start + page_size
            page_entries = all_entries[start:end]

            # 4. 格式化条目
            entries = [self._format_translation_entry(entry) for entry in page_entries]

            return {
                "entries": entries,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
                "filter_applied": "sensitive" if filter_sensitive else None
            }
        except Exception as e:
            self.log.error(f"获取翻译缓存条目失败: {e}")
            raise HTTPException(status_code=500, detail=f"获取翻译缓存条目失败: {e}")

    def _format_translation_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """格式化翻译条目"""
        cache_key = entry.get("key", "unknown_key")
        value_str = entry.get("value", "") # value 是一个 JSON 字符串，例如 "\" translated text \""
        created_time = entry.get("last_updated")
        is_sensitive = entry.get("is_sensitive", False)

        try:
            # 翻译缓存的值现在直接是翻译后的文本字符串
            translated_text = json.loads(value_str) if value_str else ""
            if not isinstance(translated_text, str):
                # 兼容旧的字典格式
                translated_text = translated_text.get("translated_text", str(translated_text))

            # 由于缓存中只有译文，原文需要从key中解析（如果可能）
            # 这是一个简化的假设，实际可能更复杂
            original_text = cache_key
            
            original_preview = original_text[:30] + "..." if len(original_text) > 30 else original_text
            translated_preview = translated_text[:30] + "..." if len(translated_text) > 30 else translated_text
            preview = f"翻译: {original_preview} → {translated_preview}"

        except (json.JSONDecodeError, TypeError):
            translated_text = value_str # 如果解析失败，直接使用原始字符串
            original_text = cache_key
            preview = "无法解析的翻译数据"

        return {
            "key": cache_key,
            "value": translated_text, # 主值设为翻译后的文本
            "original_text": original_text, # 原文信息丢失，用key代替
            "value_preview": preview,
            "is_sensitive": is_sensitive,
            "size_bytes": len(value_str),
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

    async def get_entries(self, page: int, page_size: int, search: Optional[str] = None, **kwargs) -> Dict[str, Any]:
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
            self.manager.add_or_update_mapping(request.key, request.content)
            return {"success": True, "message": f"和谐映射已更新: {request.key[:30]}..."}
        except Exception as e:
            self.log.error(f"更新和谐映射缓存条目失败: {e}")
            return {"success": False, "message": f"更新失败: {e}"}

    async def delete_entry(self, key: str) -> Dict[str, Any]:
        """删除和谐映射缓存条目"""
        try:
            if hasattr(self.manager, 'delete_mapping'):
                self.manager.delete_mapping(key)
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

    async def get_entries(self, page: int, page_size: int, search: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """获取持久化翻译缓存条目，并按（漫画路径, 翻译器类型）聚合"""
        try:
            # 1. 从管理器获取所有原始、未分组的条目
            all_raw_entries = self.manager.get_all_entries_for_display()

            # 2. 按 (manga_path, translator_type) 进行分组
            grouped_entries = {}
            for entry in all_raw_entries:
                group_key = (entry.get("manga_path"), entry.get("translator_type"))
                if not all(group_key):
                    continue

                if group_key not in grouped_entries:
                    grouped_entries[group_key] = {
                        "manga_path": entry.get("manga_path"),
                        "manga_name": entry.get("manga_name"),
                        "translator_type": entry.get("translator_type"),
                        "page_indices": set(), # 使用集合以避免重复并提高效率
                        "last_accessed": entry.get("created_at", "1970-01-01T00:00:00")
                    }

                page_index = entry.get("page_index")
                if page_index is not None:
                    grouped_entries[group_key]["page_indices"].add(page_index)

                # 更新为最新的访问时间
                current_last_accessed = entry.get("created_at", "1970-01-01T00:00:00")
                if current_last_accessed > grouped_entries[group_key]["last_accessed"]:
                    grouped_entries[group_key]["last_accessed"] = current_last_accessed

            # 3. 将分组后的数据转换为最终的列表格式
            final_list = []
            for (manga_path, translator_type), group_data in grouped_entries.items():
                page_indices = sorted(list(group_data["page_indices"]))

                # 创建一个唯一的、稳定的复合键，用于前端操作
                composite_key = f"{manga_path}:::{translator_type}"

                final_list.append({
                    "key": composite_key,
                    "manga_path": manga_path,
                    "manga_name": group_data["manga_name"],
                    "translator_type": translator_type,
                    "cached_pages_count": len(page_indices),
                    "first_page": page_indices[0] if page_indices else -1,
                    "last_page": page_indices[-1] if page_indices else -1,
                    "last_accessed": group_data["last_accessed"],
                    "value_preview": f"漫画: {group_data['manga_name']} ({translator_type})"
                })

            # 4. 对聚合后的列表进行搜索过滤
            if search:
                query = search.lower()
                final_list = [
                    entry for entry in final_list
                    if query in entry["manga_name"].lower() or query in entry["manga_path"].lower()
                ]

            # 5. 对最终列表进行分页
            total = len(final_list)
            start = (page - 1) * page_size
            end = start + page_size
            paginated_list = final_list[start:end]

            return {
                "entries": paginated_list,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
            }

        except Exception as e:
            self.log.error(f"聚合获取持久化翻译缓存条目失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"获取缓存条目失败: {e}")



    async def clear(self) -> Dict[str, Any]:
        """清空持久化翻译缓存"""
        try:
            self.manager.clear()
            return {"success": True, "message": "持久化翻译缓存已清空"}
        except Exception as e:
            self.log.error(f"清空持久化翻译缓存失败: {e}")
            return {"success": False, "message": str(e)}

    async def delete_entry(self, key: str) -> Dict[str, Any]:
        """删除持久化翻译缓存中的单个条目（按复合键）"""
        try:
            # 解析复合键：manga_path:::translator_type
            if ":::" in key:
                manga_path, translator_type = key.split(":::", 1)
                deleted_count = self.manager.clear_manga_translator_cache(manga_path, translator_type)
                if deleted_count > 0:
                    return {"success": True, "message": f"已删除漫画 {os.path.basename(manga_path)} 的 {translator_type} 翻译缓存 ({deleted_count} 个条目)"}
                else:
                    return {"success": False, "message": "未找到相关缓存条目"}
            else:
                # 兼容旧格式：直接按漫画路径删除
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


@router.get("/{cache_type}/info", dependencies=[Depends(verify_local_access)])
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


@router.get("/{cache_type}/entries", dependencies=[Depends(verify_local_access)])
async def get_cache_entries(
    cache_type: str,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    filter_sensitive: bool = False,
    show_unlikely: bool = False
):
    """获取指定缓存类型的条目列表（分页、搜索和过滤）"""
    try:
        # 确保参数类型正确
        page = int(page) if isinstance(page, str) else page
        page_size = int(page_size) if isinstance(page_size, str) else page_size

        handler = CacheHandlerFactory.get_handler(cache_type)
        
        # 将过滤参数打包
        filter_kwargs = {
            "filter_sensitive": filter_sensitive,
            "show_unlikely": show_unlikely
        }
        
        result = await handler.get_entries(page, page_size, search, **filter_kwargs)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"获取 {cache_type} 缓存条目失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取缓存条目失败: {e}")


@router.post("/{cache_type}/refresh", dependencies=[Depends(verify_local_access)])
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


@router.post("/{cache_type}/clear", dependencies=[Depends(verify_local_access)])
async def clear_cache(cache_type: str):
    """清空指定类型的缓存"""
    try:
        handler = CacheHandlerFactory.get_handler(cache_type)
        result = await handler.clear()

        # 如果清空成功，广播事件
        if result.get("success", False):
            from core.core_cache.cache_factory import broadcast_cache_event
            await broadcast_cache_event("cleared", cache_type, {"message": result.get("message", "")})

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"清空 {cache_type} 缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空缓存失败: {e}")


@router.put("/{cache_type}/entries", dependencies=[Depends(verify_local_access)])
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


@router.delete("/{cache_type}/entries/{key}", dependencies=[Depends(verify_local_access)])
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
