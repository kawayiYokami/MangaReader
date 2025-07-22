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


# ==================== 缓存处理器工厂 ====================

class CacheHandlerFactory:
    """缓存处理器工厂"""

    _handlers = {
        "manga_list": MangaListCacheHandler,
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
