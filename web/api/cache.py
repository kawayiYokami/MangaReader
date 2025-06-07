"""
缓存管理 API

提供缓存查看、清理、优化等功能的RESTful接口。
复用core中的缓存管理业务逻辑。
"""

from fastapi import APIRouter, HTTPException, Request
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from functools import wraps
import math
import asyncio
import os
import time
from datetime import datetime


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
    size_bytes: int # Keep internal model consistent if needed elsewhere
    created_time: Optional[str] = None
    last_accessed: Optional[str] = None

class DeleteEntryRequest(BaseModel):
    """删除缓存条目请求模型"""
    key: str

class UpdateEntryRequest(BaseModel):
    """更新缓存条目请求模型"""
    key: str
    content: Any # Content can be string or object
    is_sensitive: Optional[bool] = None # For translation cache

class AddHarmonizationRequest(BaseModel):
    original_text: str
    harmonized_text: str

class UpdateHarmonizationRequest(BaseModel):
    original_text: str
    harmonized_text: str


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
    """获取所有缓存的概览信息 (DEPRECATED? Use /stats instead)"""
    log.warning("Endpoint /api/cache/info is likely deprecated. Use /api/cache/stats.")
    try:
        factory = get_cache_factory_instance()
        cache_info = []

        # 获取各种缓存管理器的信息
        # Note: This doesn't include harmonization_map and might use old stat methods
        cache_types = ["manga_list", "ocr", "translation"]

        for cache_type in cache_types:
            try:
                manager = factory.get_manager(cache_type)

                # 获取缓存统计信息
                if hasattr(manager, 'get_stats'):
                    stats_data = manager.get_stats() # Assuming get_stats returns dict {total_entries, size_mb, last_updated}
                    cache_info.append(CacheInfo(
                        cache_type=cache_type,
                        total_entries=stats_data.get('total_entries', 0),
                        size_mb=stats_data.get('size_mb', 0.0),
                        last_updated=stats_data.get('last_updated')
                    ))
                else:
                    # 如果没有统计方法，提供基本信息
                    cache_info.append(CacheInfo(
                        cache_type=cache_type,
                        total_entries=0, # Cannot determine entries
                        size_mb=0.0 # Cannot determine size
                    ))

            except Exception as e:
                log.warning(f"获取 {cache_type} 缓存信息失败 (in /info): {e}")
                cache_info.append(CacheInfo(cache_type=cache_type, total_entries=0, size_mb=0.0)) # Add default on error
                continue

        return {"cache_info": cache_info}

    except Exception as e:
        log.error(f"获取缓存信息失败 (in /info): {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Core Cache Management API ====================

@router.get("/stats")
async def get_all_cache_stats():
    """获取所有缓存类型的统计信息（条目数和大小）"""
    try:
        factory = get_cache_factory_instance()
        # Ensure all relevant types are included
        cache_types = ["manga_list", "ocr", "translation", "harmonization_map"]
        stats = {}
        total_size_bytes = 0

        for cache_type in cache_types:
            entries = 0
            size_bytes = 0
            try:
                if cache_type == "harmonization_map":
                    harmonization_manager = get_harmonization_map_manager_instance()
                    mappings = harmonization_manager.get_all_mappings()
                    entries = len(mappings)
                    if os.path.exists(harmonization_manager.json_file_path):
                        size_bytes = os.path.getsize(harmonization_manager.json_file_path)

                else:
                    manager = factory.get_manager(cache_type)

                    # --- Corrected Entry Count Logic ---
                    if isinstance(manager, MangaListCacheManager):
                        # Specific logic for MangaList: count actual manga entries
                        cached_directories = manager.get_all_entries_for_display()
                        manga_count = 0
                        for dir_entry in cached_directories:
                            directory_path = dir_entry.get("directory_path")
                            if directory_path:
                                manga_list_in_dir = manager.get(directory_path)
                                if manga_list_in_dir:
                                    manga_count += len(manga_list_in_dir)
                        entries = manga_count
                    elif hasattr(manager, 'get_all_entries_for_display'):
                         # For OCR, Translation: Use get_all_entries_for_display length
                         display_entries = manager.get_all_entries_for_display()
                         entries = len(display_entries) if display_entries else 0
                    else:
                        # Fallback if method doesn't exist (should not happen for OCR/Translation based on paginated endpoint)
                        log.warning(f"Manager for {cache_type} lacks get_all_entries_for_display method for stats.")
                        entries = 0
                    # --- End Corrected Entry Count Logic ---

                    # --- Size Calculation Logic (keep as before) ---
                    if entries > 0:
                         if hasattr(manager, 'get_cache_size_bytes'):
                             size_bytes = await manager.get_cache_size_bytes() if asyncio.iscoroutinefunction(manager.get_cache_size_bytes) else manager.get_cache_size_bytes()
                         else:
                             # Fallback estimation might be inaccurate
                             size_bytes = entries * 1024 # Estimate: 1KB per entry
                             log.warning(f"Manager for {cache_type} lacks get_cache_size_bytes, estimating size.")
                    else:
                        size_bytes = 0
                    # --- End Size Calculation Logic ---


                # Store stats for this type
                stats[cache_type] = {"entries": entries, "size": size_bytes}
                total_size_bytes += size_bytes
                # Log calculated stats for debugging
                

            except Exception as e:
                # 添加更详细的错误日志，包括堆栈跟踪
                log.error(f"处理 {cache_type} 的统计信息时出错: {e}", exc_info=True)
                # 保留原始警告日志
                log.warning(f"获取 {cache_type} 缓存统计失败: {e}")
                stats[cache_type] = {"entries": 0, "size": 0} # 错误时设置默认值

        # Format total size for display
        def format_bytes(bytes_val):
            if bytes_val == 0: return "0 B"
            k = 1024
            sizes = ['B', 'KB', 'MB', 'GB', 'TB'] # Added TB
            i = 0
            if bytes_val > 0:
                # Use max(0, ...) to handle potential negative results from log if bytes_val is < 1
                i = min(len(sizes) - 1, max(0, int(math.log(bytes_val, k))))
            denominator = math.pow(k, i)
            if denominator == 0: return "0 B" # Avoid division by zero
            formatted_val = bytes_val / denominator
            # Show more precision for smaller units
            precision = 1 if i >= 2 else (2 if i == 1 else 0) # MB/GB/TB: 1 decimal, KB: 2 decimals, B: 0 decimals
            return f"{formatted_val:.{precision}f} {sizes[i]}"

        return {
            "stats": stats,
            "total_size": format_bytes(total_size_bytes),
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    except Exception as e:
        log.error(f"获取所有缓存统计失败: {e}")
        # Return a default structure consistent with success case
        cache_types_default = ["manga_list", "ocr", "translation", "harmonization_map"]
        return {
             "stats": {ctype: {"entries": 0, "size": 0} for ctype in cache_types_default},
             "total_size": "0 B",
             "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        # raise HTTPException(status_code=500, detail=f"获取缓存统计失败: {e}")


@router.get("/{cache_type}/entries")
async def get_cache_entries_paginated(
    cache_type: str,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None # Add search parameter
):
    """获取指定缓存类型的条目列表（分页和搜索）"""
    try:
        factory = get_cache_factory_instance()
        all_items = [] # Raw items before filtering/pagination

        # 1. Fetch all relevant items based on cache_type
        if cache_type == "harmonization_map":
            harmonization_manager = get_harmonization_map_manager_instance()
            mappings = harmonization_manager.get_all_mappings()
            # Convert dict to list of dicts for consistent processing
            all_items = [{"key": k, "value": v} for k, v in mappings.items()]
        elif cache_type == "manga_list":
            # --- Corrected logic for MangaList ---
            manager: MangaListCacheManager = factory.get_manager(cache_type)
            all_items = [] # Initialize empty list to hold all manga items
            if hasattr(manager, 'get_all_entries_for_display') and hasattr(manager, 'get'):
                cached_dirs_info = manager.get_all_entries_for_display() # Get list of {'directory_path': ..., 'last_updated': ...}
                if isinstance(cached_dirs_info, list):
                    for dir_info in cached_dirs_info:
                        dir_path = dir_info.get("directory_path")
                        if dir_path:
                            manga_list_in_dir = manager.get(dir_path) # Get the actual list of manga dicts for this dir
                            if isinstance(manga_list_in_dir, list):
                                all_items.extend(manga_list_in_dir) # Add manga from this dir to the main list
                            else:
                                log.warning(f"manager.get({dir_path}) did not return a list for manga_list cache.")
                else:
                    log.warning(f"get_all_entries_for_display for {cache_type} did not return a list.")
            else:
                log.warning(f"Manager for {cache_type} lacks get_all_entries_for_display or get method.")
            # --- End Corrected logic for MangaList ---
        else: # For OCR, Translation
            manager = factory.get_manager(cache_type)
            if hasattr(manager, 'get_all_entries_for_display'):
                all_items = manager.get_all_entries_for_display()
                if not isinstance(all_items, list): # Ensure it's a list
                    log.warning(f"get_all_entries_for_display for {cache_type} did not return a list.")
                    all_items = []
            else:
                 log.warning(f"Manager for {cache_type} lacks get_all_entries_for_display method for entries list.")
                 all_items = []

        # 2. Filter based on search query (case-insensitive)
        filtered_items = []
        if search:
            query = search.lower()
            for item in all_items:
                key_str = str(item.get("key", "")).lower() # Default key if not present
                value_repr = ""

                # Cache-type specific search logic
                if cache_type == "harmonization_map":
                    key_str = str(item.get("key", "")).lower() # Harmonization uses 'key' for original text
                    value_repr = str(item.get("value", "")).lower() # Harmonization uses 'value' for harmonized text
                elif cache_type == "translation":
                    key_str = str(item.get("cache_key", "")).lower() # Use specific cache_key
                    value_repr = str(item.get("translated_text", "")).lower()
                elif cache_type == "ocr":
                    key_str = str(item.get("cache_key", "")).lower() # Use specific cache_key
                    file_name = str(item.get("file_name", "")).lower()
                    page_num = str(item.get("page_num", "")).lower()
                    if query in file_name or query in page_num or query in key_str:
                         filtered_items.append(item)
                    continue # Skip default check
                elif cache_type == "manga_list":
                    key_str = str(item.get("file_path", "")).lower() # Manga key is file_path
                    title = str(item.get("title", "")).lower()
                    tags = str(item.get("tags", [])).lower()
                    if query in title or query in key_str or query in tags:
                        filtered_items.append(item)
                    continue # Skip default check

                # Default search: check key and value representation
                if query in key_str or (value_repr and query in value_repr):
                     filtered_items.append(item)

        else:
            filtered_items = all_items

        # 3. Paginate the filtered items
        total = len(filtered_items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = filtered_items[start:end]

        # 4. Format entries for the response
        entries_response = []
        for item in page_items:
            formatted_entry = {}
            key = item.get("key", "unknown_key") # Default fallback key
            value = item.get("value", None) # Get the raw value if present
            created_time_ts = None # Timestamp for uniform processing
            size_bytes_calc = 0

            if cache_type == "harmonization_map":
                original_text = item.get("key", "unknown_key") # Correctly get original text from item key
                harmonized_text = item.get("value", "") # Correctly get harmonized text from item value
                formatted_entry = {
                    "key": original_text,
                    "value": harmonized_text,
                    "value_preview": f"和谐映射: {original_text} → {harmonized_text}",
                    "size_bytes": len(original_text.encode('utf-8')) + len(harmonized_text.encode('utf-8')),
                    "created_time": None
                }
            elif cache_type == "manga_list":
                tags = item.get("tags", [])
                tags_str = ", ".join(tags[:3]) + (f" (+{len(tags) - 3})" if len(tags) > 3 else "")
                created_time_ts = item.get("last_modified")
                size_bytes_calc = len(str(item)) * 2 # Rough estimate
                formatted_entry = {
                    "key": item.get("file_path", "unknown_path"), # Use file_path as key
                    "value": item, # Send full manga data
                    "value_preview": f"漫画: {item.get('title', 'Unknown')} | 标签: {tags_str} | 页数: {item.get('total_pages', 0)}",
                    "size_bytes": size_bytes_calc,
                }
            elif cache_type == "ocr":
                created_time_ts = item.get("last_modified")
                size_bytes_calc = len(str(item)) * 2 # Rough estimate
                formatted_entry = {
                    "key": item.get("cache_key", key),
                    "value": item, # Send full OCR data
                    "value_preview": f"OCR: {item.get('file_name', 'Unknown')} 第{item.get('page_num', 0)}页",
                    "size_bytes": size_bytes_calc,
                }
            elif cache_type == "translation":
                original = item.get('original_text_sample', item.get('original_text', ''))
                translated = item.get('translated_text', '')
                is_sensitive = item.get('is_sensitive', False)
                original_preview = original[:30] + "..." if len(original) > 30 else original
                translated_preview = translated[:30] + "..." if len(translated) > 30 else translated
                created_time_ts = item.get("last_updated") # Use last_updated for translation
                size_bytes_calc = len(original.encode('utf-8')) + len(translated.encode('utf-8'))
                formatted_entry = {
                    "key": item.get("cache_key", key),
                    "value": translated, # Send full translated text
                    "original_text": original, # Send original text
                    "value_preview": f"翻译: {original_preview} → {translated_preview}",
                    "is_sensitive": is_sensitive,
                    "size_bytes": size_bytes_calc,
                }

            # Common time formatting
            if isinstance(created_time_ts, (int, float)):
                formatted_entry["created_time"] = datetime.fromtimestamp(created_time_ts).isoformat()
            elif created_time_ts:
                 formatted_entry["created_time"] = str(created_time_ts)
            else:
                 formatted_entry["created_time"] = None

            # Ensure essential fields are present
            if "key" not in formatted_entry: formatted_entry["key"] = "error_missing_key"
            if "value_preview" not in formatted_entry: formatted_entry["value_preview"] = "error_missing_preview"
            if "size_bytes" not in formatted_entry: formatted_entry["size_bytes"] = 0
            if "value" not in formatted_entry: formatted_entry["value"] = None # Add value field if missing

            entries_response.append(formatted_entry)

        return {
            "entries": entries_response,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
        }

    except Exception as e:
        log.error(f"获取缓存条目失败 ({cache_type}): {e}", exc_info=True) # Log traceback
        raise HTTPException(status_code=500, detail=f"获取缓存条目失败: {e}")

@router.post("/{cache_type}/refresh")
async def refresh_cache(cache_type: str):
    """刷新指定类型的缓存"""
    try:
        if cache_type == "harmonization_map":
            harmonization_manager = get_harmonization_map_manager_instance()
            harmonization_manager.reload_mappings()
            return {"success": True, "message": "和谐映射缓存已从文件重新加载"}
        else:
            factory = get_cache_factory_instance()
            manager = factory.get_manager(cache_type)
            if hasattr(manager, 'refresh'):
                result = await manager.refresh() if asyncio.iscoroutinefunction(manager.refresh) else manager.refresh()
                return {"success": True, "message": f"{cache_type} 缓存刷新完成", "result": result}
            else:
                log.info(f"{cache_type} cache does not support refresh.")
                return {"success": True, "message": f"{cache_type} 缓存不支持显式刷新"} # Considered success (no-op)

    except Exception as e:
        log.error(f"刷新缓存失败 ({cache_type}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"刷新缓存失败: {e}")

@router.post("/{cache_type}/clear") # Use POST for consistency
async def clear_specific_cache(cache_type: str):
    """清空指定类型的缓存"""
    try:
        if cache_type == "harmonization_map":
            harmonization_manager = get_harmonization_map_manager_instance()
            harmonization_manager.clear_all_mappings()
            return {"success": True, "message": "和谐映射缓存已清空"}
        else:
            factory = get_cache_factory_instance()
            manager = factory.get_manager(cache_type)
            if hasattr(manager, 'clear'):
                await manager.clear() if asyncio.iscoroutinefunction(manager.clear) else manager.clear()
                return {"success": True, "message": f"{cache_type} 缓存已清空"}
            else:
                log.warning(f"Cache manager for {cache_type} does not have a clear method.")
                return {"success": False, "message": f"{cache_type} 缓存管理器不支持清空操作。"}

    except Exception as e:
        log.error(f"清空缓存失败 ({cache_type}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"清空缓存失败: {e}")


@router.post("/{cache_type}/update")
async def update_cache_entry(cache_type: str, request: Request):
    """更新或添加缓存条目"""
    try:
        data = await request.json()

        if cache_type == "harmonization_map":
            update_req = UpdateHarmonizationRequest(**data)
            harmonization_manager = get_harmonization_map_manager_instance()
            # update_mapping should handle add/update
            success = harmonization_manager.update_mapping(update_req.original_text, update_req.harmonized_text)
            return {"success": success, "message": f"和谐映射已{'更新' if success else '更新失败'}"}

        elif cache_type == "translation":
            update_req = UpdateEntryRequest(**data)
            factory = get_cache_factory_instance()
            manager: TranslationCacheManager = factory.get_manager(cache_type)
            if hasattr(manager, 'add_or_update_entry'):
                 await manager.add_or_update_entry(
                     cache_key=update_req.key,
                     translated_text=update_req.content,
                     is_sensitive=update_req.is_sensitive
                     # Pass original_text if manager method requires it
                 )
                 return {"success": True, "message": "翻译缓存条目已更新"}
            else:
                 return {"success": False, "message": "翻译缓存管理器不支持更新"}


        else:
             # Generic handler for other types (e.g., OCR, MangaList if they support updates)
             update_req = UpdateEntryRequest(**data)
             factory = get_cache_factory_instance()
             manager = factory.get_manager(cache_type)
             if hasattr(manager, 'add_or_update_entry'):
                 # Adapt parameters as needed for the specific manager
                 await manager.add_or_update_entry(update_req.key, update_req.content)
                 return {"success": True, "message": f"{cache_type} 缓存条目已更新"}
             else:
                 return {"success": False, "message": f"{cache_type} 缓存不支持更新操作"}

    except Exception as e:
        log.error(f"更新缓存条目失败 ({cache_type}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新缓存条目失败: {e}")


@router.post("/{cache_type}/add")
async def add_cache_entry(cache_type: str, request: Request):
    """添加新的缓存条目 (primarily for harmonization map)"""
    try:
        if cache_type == "harmonization_map":
            data = await request.json()
            add_req = AddHarmonizationRequest(**data)
            harmonization_manager = get_harmonization_map_manager_instance()
            success = harmonization_manager.add_mapping(add_req.original_text, add_req.harmonized_text)
            return {"success": success, "message": f"和谐映射已{'添加' if success else '添加失败，可能已存在'}"}
        else:
            # Currently only explicit add for harmonization map
            return {"success": False, "message": f"缓存类型 {cache_type} 不支持直接添加操作，请使用更新。"}

    except Exception as e:
        log.error(f"添加缓存条目失败 ({cache_type}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"添加缓存条目失败: {e}")


@router.post("/{cache_type}/delete")
async def delete_cache_entry_post(cache_type: str, request: DeleteEntryRequest): # Use Pydantic model directly
    """删除指定的缓存条目"""
    try:
        key = request.key

        if cache_type == "harmonization_map":
            harmonization_manager = get_harmonization_map_manager_instance()
            result = harmonization_manager.delete_mapping(key)
            return {"success": result, "message": f"和谐映射条目 {'已删除' if result else '删除失败，未找到'}"}
        else:
            factory = get_cache_factory_instance()
            manager = factory.get_manager(cache_type)
            if hasattr(manager, 'delete_entry'):
                result = await manager.delete_entry(key) if asyncio.iscoroutinefunction(manager.delete_entry) else manager.delete_entry(key)
                is_success = result if isinstance(result, bool) else True # Assume success if no bool returned
                return {"success": is_success, "message": f"{cache_type} 缓存条目 {key[:30]}... {'已删除' if is_success else '删除失败'}"}
            else:
                return {"success": False, "message": f"{cache_type} 缓存不支持删除单个条目"}

    except Exception as e:
        log.error(f"删除缓存条目失败 ({cache_type}, key: {request.key}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除缓存条目失败: {e}")
