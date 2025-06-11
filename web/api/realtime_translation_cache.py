# web/api/realtime_translation_cache.py
"""
实时翻译缓存API

提供实时翻译缓存的管理接口。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os

from core.cache_factory import get_cache_factory_instance
from utils import manga_logger as log

router = APIRouter(prefix="/api/realtime-translation-cache", tags=["realtime-translation-cache"])


class CacheEntryResponse(BaseModel):
    """缓存条目响应模型"""
    cache_key: str
    manga_path: str
    manga_name: str
    page_index: int
    page_display: str
    target_language: str
    image_hash: str
    image_hash_short: str
    created_at: str
    last_accessed: str
    access_count: int
    cache_version: str


class CacheStatisticsResponse(BaseModel):
    """缓存统计响应模型"""
    total_entries: int
    language_stats: Dict[str, int]
    recent_accessed: int
    average_access_count: float
    cache_size_bytes: int


class CacheDetailResponse(BaseModel):
    """缓存详情响应模型"""
    manga_path: str
    page_index: int
    target_language: str
    image_hash: str
    image_width: int
    image_height: int
    original_texts: List[str]
    translated_texts: List[str]
    translation_mappings: Dict[str, str]
    harmonized_texts: List[str]
    harmonization_applied: bool
    text_regions_count: int
    created_at: str
    last_accessed: str
    access_count: int


class CleanupResponse(BaseModel):
    """清理响应模型"""
    deleted_count: int
    message: str


@router.get("/entries", response_model=List[CacheEntryResponse])
async def get_cache_entries():
    """获取所有缓存条目"""
    try:
        cache_manager = get_cache_factory_instance().get_manager("realtime_translation")
        entries = cache_manager.get_all_entries_for_display()
        
        return [CacheEntryResponse(**entry) for entry in entries]
        
    except Exception as e:
        log.error(f"获取缓存条目失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取缓存条目失败: {str(e)}")


@router.get("/statistics", response_model=CacheStatisticsResponse)
async def get_cache_statistics():
    """获取缓存统计信息"""
    try:
        cache_manager = get_cache_factory_instance().get_manager("realtime_translation")
        stats = cache_manager.get_cache_statistics()
        
        return CacheStatisticsResponse(**stats)
        
    except Exception as e:
        log.error(f"获取缓存统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取缓存统计失败: {str(e)}")


@router.get("/detail/{cache_key}", response_model=CacheDetailResponse)
async def get_cache_detail(cache_key: str):
    """获取缓存详情"""
    try:
        cache_manager = get_cache_factory_instance().get_manager("realtime_translation")
        cache_data = cache_manager.get(cache_key)
        
        if not cache_data:
            raise HTTPException(status_code=404, detail="缓存条目不存在")
        
        return CacheDetailResponse(
            manga_path=cache_data.manga_path,
            page_index=cache_data.page_index,
            target_language=cache_data.target_language,
            image_hash=cache_data.image_hash,
            image_width=cache_data.image_width,
            image_height=cache_data.image_height,
            original_texts=cache_data.original_texts,
            translated_texts=cache_data.translated_texts,
            translation_mappings=cache_data.translation_mappings,
            harmonized_texts=cache_data.harmonized_texts,
            harmonization_applied=cache_data.harmonization_applied,
            text_regions_count=len(cache_data.text_regions),
            created_at=cache_data.created_at,
            last_accessed=cache_data.last_accessed,
            access_count=cache_data.access_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"获取缓存详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取缓存详情失败: {str(e)}")


@router.delete("/entry/{cache_key}")
async def delete_cache_entry(cache_key: str):
    """删除指定缓存条目"""
    try:
        cache_manager = get_cache_factory_instance().get_manager("realtime_translation")
        cache_manager.delete(cache_key)
        
        return {"message": f"缓存条目 {cache_key} 已删除"}
        
    except Exception as e:
        log.error(f"删除缓存条目失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除缓存条目失败: {str(e)}")


@router.delete("/manga")
async def delete_manga_cache(manga_path: str):
    """删除指定漫画的所有缓存"""
    try:
        cache_manager = get_cache_factory_instance().get_manager("realtime_translation")
        deleted_count = cache_manager.delete_by_manga(manga_path)
        
        return {"message": f"已删除漫画 {os.path.basename(manga_path)} 的 {deleted_count} 个缓存条目"}
        
    except Exception as e:
        log.error(f"删除漫画缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除漫画缓存失败: {str(e)}")


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_missing_files():
    """清理源文件已丢失的翻译缓存"""
    try:
        cache_manager = get_cache_factory_instance().get_manager("realtime_translation")
        deleted_count = cache_manager.cleanup_missing_files()
        
        return CleanupResponse(
            deleted_count=deleted_count,
            message=f"清理完成，删除了 {deleted_count} 个丢失文件的缓存条目"
        )
        
    except Exception as e:
        log.error(f"清理缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理缓存失败: {str(e)}")


@router.delete("/clear")
async def clear_all_cache():
    """清空所有实时翻译缓存"""
    try:
        cache_manager = get_cache_factory_instance().get_manager("realtime_translation")
        cache_manager.clear()
        
        return {"message": "所有实时翻译缓存已清空"}
        
    except Exception as e:
        log.error(f"清空缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空缓存失败: {str(e)}")


@router.get("/manga/{manga_path:path}")
async def get_manga_cache_info(manga_path: str):
    """获取指定漫画的缓存信息"""
    try:
        cache_manager = get_cache_factory_instance().get_manager("realtime_translation")
        cached_pages = cache_manager.get_cache_by_manga(manga_path)
        
        cache_info = []
        for cache_data in cached_pages:
            cache_info.append({
                "page_index": cache_data.page_index,
                "page_display": f"第{cache_data.page_index + 1}页",
                "target_language": cache_data.target_language,
                "image_hash": cache_data.image_hash[:8] + "...",
                "original_texts_count": len(cache_data.original_texts),
                "translated_texts_count": len(cache_data.translated_texts),
                "created_at": cache_data.created_at,
                "last_accessed": cache_data.last_accessed,
                "access_count": cache_data.access_count
            })
        
        return {
            "manga_path": manga_path,
            "manga_name": os.path.basename(manga_path),
            "total_cached_pages": len(cache_info),
            "cached_pages": cache_info
        }
        
    except Exception as e:
        log.error(f"获取漫画缓存信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取漫画缓存信息失败: {str(e)}")


@router.get("/health")
async def cache_health():
    """缓存模块健康检查"""
    try:
        cache_manager = get_cache_factory_instance().get_manager("realtime_translation")
        stats = cache_manager.get_cache_statistics()
        
        return {
            "status": "healthy",
            "module": "realtime_translation_cache",
            "total_entries": stats["total_entries"],
            "cache_size_mb": round(stats["cache_size_bytes"] / 1024 / 1024, 2)
        }
        
    except Exception as e:
        log.error(f"缓存健康检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"缓存健康检查失败: {str(e)}")
