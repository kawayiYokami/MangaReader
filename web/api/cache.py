"""
缓存管理 API

提供缓存查看、清理、优化等功能的RESTful接口。
复用core中的缓存管理业务逻辑。
"""

from fastapi import APIRouter, HTTPException, Request
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from functools import wraps

# 导入核心业务逻辑
from core.cache_factory import get_cache_factory_instance
from core.manga_cache import MangaListCacheManager
from core.ocr_cache_manager import OcrCacheManager
from core.translation_cache_manager import TranslationCacheManager
from core.harmonization_map_manager import get_harmonization_map_manager_instance
from utils import manga_logger as log

# 权限控制函数
def is_local_request(request: Request) -> bool:
    """检查是否为本地访问"""
    client_ip = request.client.host
    local_ips = ['127.0.0.1', '::1', 'localhost']
    return client_ip in local_ips

def local_only(func):
    """装饰器：仅允许本地访问"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # 从参数中找到Request对象
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break

        if request and not is_local_request(request):
            raise HTTPException(status_code=403, detail="此功能仅限本地访问")

        return await func(*args, **kwargs)
    return wrapper

router = APIRouter()

# 数据模型
class CacheInfo(BaseModel):
    """缓存信息模型"""
    cache_type: str
    total_entries: int
    size_mb: float
    last_updated: Optional[str] = None

class CacheEntry(BaseModel):
    """缓存条目模型"""
    key: str
    value_preview: str
    size_bytes: int
    created_time: Optional[str] = None
    last_accessed: Optional[str] = None

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
            {"key": "harmonization_map", "name": "和谐映射", "description": "内容和谐化映射缓存"}
        ]
        
        return {"cache_types": cache_types}
        
    except Exception as e:
        log.error(f"获取缓存类型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/info")
async def get_cache_info():
    """获取所有缓存的概览信息"""
    try:
        factory = get_cache_factory_instance()
        cache_info = []
        
        # 获取各种缓存管理器的信息
        cache_types = ["manga_list", "ocr", "translation"]
        
        for cache_type in cache_types:
            try:
                manager = factory.get_manager(cache_type)
                
                # 获取缓存统计信息
                if hasattr(manager, 'get_stats'):
                    stats = manager.get_stats()
                    cache_info.append(CacheInfo(
                        cache_type=cache_type,
                        total_entries=stats.get('total_entries', 0),
                        size_mb=stats.get('size_mb', 0.0),
                        last_updated=stats.get('last_updated')
                    ))
                else:
                    # 如果没有统计方法，提供基本信息
                    cache_info.append(CacheInfo(
                        cache_type=cache_type,
                        total_entries=0,
                        size_mb=0.0
                    ))
                    
            except Exception as e:
                log.warning(f"获取 {cache_type} 缓存信息失败: {e}")
                continue
        
        return {"cache_info": cache_info}
        
    except Exception as e:
        log.error(f"获取缓存信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.delete("/{cache_type}")
@local_only
async def clear_cache(
    cache_type: str,
    http_request: Request
):
    """清空指定类型的缓存"""
    try:
        factory = get_cache_factory_instance()
        manager = factory.get_manager(cache_type)
        
        # 清空缓存
        manager.clear()
        
        return {
            "success": True,
            "message": f"{cache_type} 缓存已清空"
        }
        
    except Exception as e:
        log.error(f"清空缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/all")
@local_only
async def clear_all_caches(http_request: Request):
    """清空所有缓存"""
    try:
        factory = get_cache_factory_instance()
        cache_types = ["manga_list", "ocr", "translation"]
        
        cleared_caches = []
        failed_caches = []
        
        for cache_type in cache_types:
            try:
                manager = factory.get_manager(cache_type)
                manager.clear()
                cleared_caches.append(cache_type)
            except Exception as e:
                log.warning(f"清空 {cache_type} 缓存失败: {e}")
                failed_caches.append(cache_type)
        
        return {
            "success": len(failed_caches) == 0,
            "message": f"已清空 {len(cleared_caches)} 个缓存",
            "cleared_caches": cleared_caches,
            "failed_caches": failed_caches
        }
        
    except Exception as e:
        log.error(f"清空所有缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{cache_type}/optimize")
async def optimize_cache(cache_type: str):
    """优化指定类型的缓存"""
    try:
        factory = get_cache_factory_instance()
        manager = factory.get_manager(cache_type)
        
        # 如果缓存管理器支持优化操作
        if hasattr(manager, 'optimize'):
            result = manager.optimize()
            return {
                "success": True,
                "message": f"{cache_type} 缓存优化完成",
                "result": result
            }
        else:
            return {
                "success": False,
                "message": f"{cache_type} 缓存不支持优化操作"
            }
        
    except Exception as e:
        log.error(f"优化缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{cache_type}/stats")
async def get_cache_stats(cache_type: str):
    """获取指定缓存类型的详细统计信息"""
    try:
        factory = get_cache_factory_instance()
        manager = factory.get_manager(cache_type)

        stats = {
            "cache_type": cache_type,
            "total_entries": 0,
            "size_bytes": 0,
            "hit_rate": 0.0,
            "last_updated": None
        }

        # 如果管理器支持统计功能
        if hasattr(manager, 'get_stats'):
            manager_stats = manager.get_stats()
            stats.update(manager_stats)

        return stats

    except Exception as e:
        log.error(f"获取缓存统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 新增的缓存管理API ====================

@router.get("/stats")
async def get_all_cache_stats():
    """获取所有缓存的统计信息"""
    try:
        import os
        import time
        from datetime import datetime

        factory = get_cache_factory_instance()
        cache_types = ["manga_list", "ocr", "translation", "harmonization_map"]

        stats = {}
        total_size = 0
        last_update = None

        for cache_type in cache_types:
            try:
                if cache_type == "harmonization_map":
                    # 和谐映射缓存特殊处理
                    harmonization_manager = get_harmonization_map_manager_instance()
                    mappings = harmonization_manager.get_all_mappings()
                    entries = len(mappings)

                    # 计算JSON文件大小
                    if os.path.exists(harmonization_manager.json_file_path):
                        size_bytes = os.path.getsize(harmonization_manager.json_file_path)
                    else:
                        size_bytes = 0

                    stats[cache_type] = {
                        "entries": entries,
                        "size_bytes": size_bytes
                    }
                else:
                    manager = factory.get_manager(cache_type)

                    # 获取条目数
                    if hasattr(manager, 'get_all_entries_for_display'):
                        entries = len(manager.get_all_entries_for_display())
                    else:
                        entries = 0

                    # 估算大小（简化处理）
                    size_bytes = entries * 1024  # 假设每个条目平均1KB

                    stats[cache_type] = {
                        "entries": entries,
                        "size_bytes": size_bytes
                    }

                total_size += stats[cache_type]["size_bytes"]

            except Exception as e:
                log.warning(f"获取 {cache_type} 缓存统计失败: {e}")
                stats[cache_type] = {"entries": 0, "size_bytes": 0}

        # 格式化总大小
        def format_bytes(bytes_val):
            if bytes_val == 0:
                return "0 B"
            k = 1024
            sizes = ['B', 'KB', 'MB', 'GB']
            i = 0
            while bytes_val >= k and i < len(sizes) - 1:
                bytes_val /= k
                i += 1
            return f"{bytes_val:.1f} {sizes[i]}"

        return {
            "stats": stats,
            "total_size": format_bytes(total_size),
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    except Exception as e:
        log.error(f"获取缓存统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{cache_type}/entries")
async def get_cache_entries_paginated(
    cache_type: str,
    page: int = 1,
    page_size: int = 20
):
    """获取指定缓存类型的条目列表（分页）"""
    try:
        import os
        from datetime import datetime

        factory = get_cache_factory_instance()
        entries = []
        total = 0

        if cache_type == "harmonization_map":
            # 和谐映射缓存特殊处理
            harmonization_manager = get_harmonization_map_manager_instance()
            mappings = harmonization_manager.get_all_mappings()

            # 转换为列表以便分页
            mapping_items = list(mappings.items())
            total = len(mapping_items)

            # 分页
            start = (page - 1) * page_size
            end = start + page_size
            page_items = mapping_items[start:end]

            for original_text, harmonized_text in page_items:
                entries.append({
                    "key": original_text,
                    "value_preview": f"和谐映射: {original_text} → {harmonized_text}",
                    "size_bytes": len(original_text.encode('utf-8')) + len(harmonized_text.encode('utf-8')),
                    "created_time": None  # JSON文件没有单个条目的时间戳
                })
        else:
            manager = factory.get_manager(cache_type)

            if isinstance(manager, MangaListCacheManager):
                # 漫画列表缓存 - 显示具体漫画而不是目录
                cached_directories = manager.get_all_entries_for_display()
                all_manga_entries = []

                # 从每个目录获取所有漫画条目（参考原项目做法）
                for dir_entry in cached_directories:
                    directory_path = dir_entry.get("directory_path")
                    if directory_path:
                        manga_list_in_dir = manager.get(directory_path)
                        if manga_list_in_dir:
                            all_manga_entries.extend(manga_list_in_dir)

                total = len(all_manga_entries)

                # 分页
                start = (page - 1) * page_size
                end = start + page_size
                page_entries = all_manga_entries[start:end]

                for entry in page_entries:
                    # 处理时间格式
                    last_modified = entry.get("last_modified")
                    if isinstance(last_modified, (int, float)):
                        created_time = datetime.fromtimestamp(last_modified).isoformat()
                    else:
                        created_time = str(last_modified) if last_modified else None

                    # 格式化标签显示
                    tags = entry.get("tags", [])
                    tags_str = ", ".join(tags[:3])  # 只显示前3个标签
                    if len(tags) > 3:
                        tags_str += f" (+{len(tags) - 3}个)"

                    entries.append({
                        "key": entry.get("file_path", "unknown"),
                        "value_preview": f"漫画: {entry.get('title', 'Unknown')} | 标签: {tags_str} | 页数: {entry.get('total_pages', 0)}",
                        "size_bytes": len(str(entry)) * 2,  # 估算大小
                        "created_time": created_time
                    })

            elif isinstance(manager, OcrCacheManager):
                # OCR缓存
                all_entries = manager.get_all_entries_for_display()
                total = len(all_entries)

                # 分页
                start = (page - 1) * page_size
                end = start + page_size
                page_entries = all_entries[start:end]

                for entry in page_entries:
                    # 处理时间格式
                    last_modified = entry.get("last_modified")
                    if isinstance(last_modified, (int, float)):
                        created_time = datetime.fromtimestamp(last_modified).isoformat()
                    else:
                        created_time = str(last_modified) if last_modified else None

                    entries.append({
                        "key": entry.get("cache_key", "unknown"),
                        "value_preview": f"OCR: {entry.get('file_name', 'Unknown')} 第{entry.get('page_num', 0)}页",
                        "size_bytes": len(str(entry)) * 2,  # 估算大小
                        "created_time": created_time
                    })

            elif isinstance(manager, TranslationCacheManager):
                # 翻译缓存
                all_entries = manager.get_all_entries_for_display()
                total = len(all_entries)

                # 分页
                start = (page - 1) * page_size
                end = start + page_size
                page_entries = all_entries[start:end]

                for entry in page_entries:
                    # 使用正确的字段名
                    original = entry.get('original_text_sample', '')
                    translated = entry.get('translated_text', '')

                    # 格式化预览文本
                    original_preview = original[:30] + "..." if len(original) > 30 else original
                    translated_preview = translated[:30] + "..." if len(translated) > 30 else translated

                    # 处理时间格式 - 翻译缓存使用 last_updated 字段
                    last_updated = entry.get("last_updated")
                    if isinstance(last_updated, (int, float)):
                        created_time = datetime.fromtimestamp(last_updated).isoformat()
                    else:
                        created_time = str(last_updated) if last_updated else None

                    entries.append({
                        "key": entry.get("cache_key", "unknown"),
                        "value_preview": f"翻译: {original_preview} → {translated_preview}",
                        "size_bytes": len(str(entry)) * 2,  # 估算大小
                        "created_time": created_time
                    })

        return {
            "entries": entries,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    except Exception as e:
        log.error(f"获取缓存条目失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{cache_type}/refresh")
async def refresh_cache(cache_type: str):
    """刷新指定类型的缓存"""
    try:
        if cache_type == "harmonization_map":
            # 和谐映射缓存特殊处理
            harmonization_manager = get_harmonization_map_manager_instance()
            harmonization_manager.reload_mappings()
            return {
                "success": True,
                "message": "和谐映射缓存已从文件重新加载"
            }
        else:
            factory = get_cache_factory_instance()
            manager = factory.get_manager(cache_type)

            # 如果支持刷新操作
            if hasattr(manager, 'refresh'):
                result = manager.refresh()
                return {
                    "success": True,
                    "message": f"{cache_type} 缓存刷新完成",
                    "result": result
                }
            else:
                # 简单的刷新：重新初始化
                manager.__init__()
                return {
                    "success": True,
                    "message": f"{cache_type} 缓存已重新初始化"
                }

    except Exception as e:
        log.error(f"刷新缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{cache_type}/clear")
async def clear_specific_cache(cache_type: str):
    """清空指定类型的缓存"""
    try:
        if cache_type == "harmonization_map":
            # 和谐映射缓存特殊处理
            harmonization_manager = get_harmonization_map_manager_instance()
            harmonization_manager.clear_all_mappings()
            return {
                "success": True,
                "message": "和谐映射缓存已清空"
            }
        else:
            factory = get_cache_factory_instance()
            manager = factory.get_manager(cache_type)
            manager.clear()

            return {
                "success": True,
                "message": f"{cache_type} 缓存已清空"
            }

    except Exception as e:
        log.error(f"清空缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{cache_type}/optimize")
async def optimize_cache(cache_type: str):
    """优化指定类型的缓存"""
    try:
        if cache_type == "harmonization_map":
            # 和谐映射缓存特殊处理 - 重新加载即可
            harmonization_manager = get_harmonization_map_manager_instance()
            harmonization_manager.reload_mappings()
            return {
                "success": True,
                "message": "和谐映射缓存已优化（重新加载）"
            }
        else:
            factory = get_cache_factory_instance()
            manager = factory.get_manager(cache_type)

            # 如果支持优化操作
            if hasattr(manager, 'optimize'):
                result = manager.optimize()
                return {
                    "success": True,
                    "message": f"{cache_type} 缓存优化完成",
                    "result": result
                }
            else:
                # 简单的优化：清理无效条目
                if hasattr(manager, 'cleanup'):
                    result = manager.cleanup()
                    return {
                        "success": True,
                        "message": f"{cache_type} 缓存清理完成",
                        "result": result
                    }
                else:
                    return {
                        "success": True,
                        "message": f"{cache_type} 缓存不需要优化"
                    }

    except Exception as e:
        log.error(f"优化缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refresh-all")
async def refresh_all_caches():
    """刷新所有缓存"""
    try:
        cache_types = ["manga_list", "ocr", "translation", "harmonization_map"]

        refreshed_caches = []
        failed_caches = []

        for cache_type in cache_types:
            try:
                # 调用单个缓存的刷新API
                result = await refresh_cache(cache_type)
                if result.get("success"):
                    refreshed_caches.append(cache_type)
                else:
                    failed_caches.append(cache_type)
            except Exception as e:
                log.warning(f"刷新 {cache_type} 缓存失败: {e}")
                failed_caches.append(cache_type)

        return {
            "success": len(failed_caches) == 0,
            "message": f"已刷新 {len(refreshed_caches)} 个缓存",
            "refreshed_caches": refreshed_caches,
            "failed_caches": failed_caches
        }

    except Exception as e:
        log.error(f"刷新所有缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/optimize-all")
async def optimize_all_caches():
    """优化所有缓存"""
    try:
        cache_types = ["manga_list", "ocr", "translation", "harmonization_map"]

        optimized_caches = []
        failed_caches = []

        for cache_type in cache_types:
            try:
                # 调用单个缓存的优化API
                result = await optimize_cache(cache_type)
                if result.get("success"):
                    optimized_caches.append(cache_type)
                else:
                    failed_caches.append(cache_type)
            except Exception as e:
                log.warning(f"优化 {cache_type} 缓存失败: {e}")
                failed_caches.append(cache_type)

        return {
            "success": len(failed_caches) == 0,
            "message": f"已优化 {len(optimized_caches)} 个缓存",
            "optimized_caches": optimized_caches,
            "failed_caches": failed_caches
        }

    except Exception as e:
        log.error(f"优化所有缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clear-all")
async def clear_all_caches_new():
    """清空所有缓存"""
    try:
        cache_types = ["manga_list", "ocr", "translation", "harmonization_map"]

        cleared_caches = []
        failed_caches = []

        for cache_type in cache_types:
            try:
                # 调用单个缓存的清空API
                result = await clear_specific_cache(cache_type)
                if result.get("success"):
                    cleared_caches.append(cache_type)
                else:
                    failed_caches.append(cache_type)
            except Exception as e:
                log.warning(f"清空 {cache_type} 缓存失败: {e}")
                failed_caches.append(cache_type)

        return {
            "success": len(failed_caches) == 0,
            "message": f"已清空 {len(cleared_caches)} 个缓存",
            "cleared_caches": cleared_caches,
            "failed_caches": failed_caches
        }

    except Exception as e:
        log.error(f"清空所有缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class DeleteEntryRequest(BaseModel):
    """删除缓存条目请求模型"""
    key: str

@router.delete("/{cache_type}/entry")
async def delete_cache_entry(cache_type: str, request: DeleteEntryRequest):
    """删除指定的缓存条目"""
    try:
        key = request.key

        if cache_type == "harmonization_map":
            # 和谐映射缓存特殊处理
            harmonization_manager = get_harmonization_map_manager_instance()
            result = harmonization_manager.delete_mapping(key)
            if result:
                return {
                    "success": True,
                    "message": f"和谐映射条目已删除: {key[:30]}..."
                }
            else:
                return {
                    "success": False,
                    "message": f"删除失败，未找到映射: {key[:30]}..."
                }
        else:
            factory = get_cache_factory_instance()
            manager = factory.get_manager(cache_type)

            # 如果支持删除单个条目
            if hasattr(manager, 'delete_entry'):
                result = manager.delete_entry(key)
                return {
                    "success": True,
                    "message": f"缓存条目 {key} 已删除",
                    "result": result
                }
            else:
                return {
                    "success": False,
                    "message": f"{cache_type} 缓存不支持删除单个条目"
                }

    except Exception as e:
        log.error(f"删除缓存条目失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
