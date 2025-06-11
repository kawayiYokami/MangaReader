"""
实时翻译功能 API 路由层

纯API路由层，遵循严格的分层架构原则：
- web层：仅负责API路由和HTTP请求/响应处理
- service层：负责业务逻辑协调
- core层：负责具体功能实现

所有业务逻辑都在core/realtime_translation_service.py中实现
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import os

from core.realtime_translation_service import get_realtime_translation_service
from utils import manga_logger as log

router = APIRouter()

# ==================== 数据模型 ====================

class StartTranslationServiceRequest(BaseModel):
    """启动翻译服务请求模型"""
    translator_type: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None

class SetCurrentMangaRequest(BaseModel):
    """设置当前漫画请求模型"""
    manga_path: str
    current_page: int = 0

class RequestTranslationRequest(BaseModel):
    """请求翻译页面模型"""
    manga_path: str
    page_indices: List[int]
    priority: int = 10

# ==================== 服务管理API ====================

@router.get("/health")
async def realtime_translation_health():
    """实时翻译模块健康检查"""
    return {
        "status": "healthy",
        "module": "realtime_translation",
        "architecture": "service_layer_unified",
        "version": "2.0"
    }

@router.post("/start-service")
async def start_translation_service(request: StartTranslationServiceRequest):
    """启动实时翻译服务"""
    try:
        service = get_realtime_translation_service()
        result = service.start_service(
            translator_type=request.translator_type,
            api_key=request.api_key,
            model=request.model
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"API路由层: 启动翻译服务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop-service")
async def stop_translation_service():
    """停止实时翻译服务"""
    try:
        service = get_realtime_translation_service()
        result = service.stop_service()

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"API路由层: 停止翻译服务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_translation_status() -> Dict[str, Any]:
    """获取翻译状态"""
    try:
        service = get_realtime_translation_service()
        status = service.get_service_status()
        return status

    except Exception as e:
        log.error(f"API路由层: 获取翻译状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/set-current-manga")
async def set_current_manga(request: SetCurrentMangaRequest):
    """设置当前漫画和页面"""
    try:
        # 基础文件路径验证
        if not os.path.exists(request.manga_path):
            raise HTTPException(status_code=404, detail=f"漫画文件不存在: {request.manga_path}")

        service = get_realtime_translation_service()
        result = service.set_current_manga(request.manga_path, request.current_page)

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"API路由层: 设置当前漫画失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/request-translation")
async def request_translation(request: RequestTranslationRequest):
    """请求翻译指定页面"""
    try:
        # 基础文件路径验证
        if not os.path.exists(request.manga_path):
            raise HTTPException(status_code=404, detail=f"漫画文件不存在: {request.manga_path}")

        service = get_realtime_translation_service()
        result = service.request_translation(
            request.manga_path,
            request.page_indices,
            request.priority
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"API路由层: 请求翻译失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/translated-page/{manga_path:path}/{page_index}")
async def get_translated_page(manga_path: str, page_index: int):
    """获取翻译后的页面（统一接口）"""
    try:
        service = get_realtime_translation_service()
        result = service.get_translated_page(manga_path, page_index)
        return result
    except Exception as e:
        log.error(f"API路由层: 获取翻译页面失败: {e}")
        return {
            "is_translated": False,
            "image_data": None,
            "manga_path": manga_path,
            "page_index": page_index,
            "error": str(e)
        }

# ==================== 缓存管理API ====================

@router.get("/check-cache/{manga_path:path}/{page_index}")
async def check_cache_status(manga_path: str, page_index: int):
    """检查缓存状态"""
    try:
        service = get_realtime_translation_service()
        result = service.check_cache_status(manga_path, page_index)
        return result
    except Exception as e:
        log.error(f"API路由层: 检查缓存状态失败: {e}")
        return {
            "success": False,
            "manga_path": manga_path,
            "page_index": page_index,
            "has_cache": False,
            "error": str(e)
        }

@router.get("/cache/statistics")
async def get_cache_statistics():
    """获取缓存统计信息"""
    try:
        service = get_realtime_translation_service()
        stats = service.get_cache_statistics()
        return stats
    except Exception as e:
        log.error(f"API路由层: 获取缓存统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cache/clear")
async def clear_all_cache():
    """清空所有实时翻译缓存"""
    try:
        service = get_realtime_translation_service()
        result = service.clear_cache()

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"API路由层: 清空缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/check-pages-translated/{manga_path:path}")
async def check_pages_translated(manga_path: str, page_indices: str):
    """批量检查页面翻译状态"""
    try:
        # 解析页面索引
        if not page_indices:
            raise HTTPException(status_code=400, detail="page_indices参数不能为空")

        try:
            indices = [int(idx.strip()) for idx in page_indices.split(',') if idx.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="page_indices格式错误，应为逗号分隔的数字")

        if not indices:
            raise HTTPException(status_code=400, detail="page_indices不能为空")

        service = get_realtime_translation_service()

        # 批量检查每个页面的翻译状态
        results = {}
        for page_index in indices:
            cache_result = service.check_cache_status(manga_path, page_index)
            results[str(page_index)] = cache_result.get("has_cache", False)

        return {
            "success": True,
            "manga_path": manga_path,
            "results": results,
            "total_checked": len(indices)
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"API路由层: 批量检查页面翻译状态失败: {e}")
        return {
            "success": False,
            "manga_path": manga_path,
            "results": {},
            "error": str(e)
        }

# ==================== 兼容性API ====================

@router.get("/translated-page-four-layer/{manga_path:path}/{page_index}")
async def get_translated_page_four_layer_legacy(manga_path: str, page_index: int):
    """获取翻译后的页面（兼容性API，重定向到统一接口）"""
    try:
        # 重定向到新的统一API
        return await get_translated_page(manga_path, page_index)
    except Exception as e:
        log.error(f"API路由层: 兼容性API获取翻译页面失败: {e}")
        return {
            "is_translated": False,
            "image_data": None,
            "manga_path": manga_path,
            "page_index": page_index,
            "error": str(e)
        }

@router.get("/check-persistent-webp-cache/{manga_path:path}/{page_index}")
async def check_persistent_webp_cache_legacy(manga_path: str, page_index: int):
    """检查持久化WebP缓存（兼容性API）"""
    try:
        # 重定向到新的统一缓存检查API
        result = await check_cache_status(manga_path, page_index)

        # 转换为旧格式
        return {
            "success": result["success"],
            "manga_path": manga_path,
            "page_index": page_index,
            "has_cache": result["has_cache"],
            "cache_type": result.get("cache_source", "unknown")
        }
    except Exception as e:
        log.error(f"API路由层: 兼容性WebP缓存检查失败: {e}")
        return {
            "success": False,
            "manga_path": manga_path,
            "page_index": page_index,
            "has_cache": False,
            "error": str(e)
        }
